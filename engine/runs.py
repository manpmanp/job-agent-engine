# Job-search agent engine
# File:    engine/runs.py
# Purpose: Complete runs without an AI agent (weekly, daily, auto) and scheduling instructions.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
# Date:    2026-10-28

"""
./run.sh run weekly   collect -> verify -> sync -> enrich (if on) ->
                      template documents (if no candidate material) -> weekly page + summary
./run.sh run daily    sync -> template documents -> weekly page
./run.sh run auto     weekly on search_config.weekly_list.full_search_day, daily otherwise
./run.sh schedule     installs or shows the daily run (engine/schedule.py)

These runs need no AI agent. An agent, when used, adds what the engine
cannot do on its own (LinkedIn and Indeed through its own tools, judgement
on unclear postings, and full tailoring from your material).
"""
import os
import sys
from datetime import date

from . import decisions, documents, weekly, checkpoint
from . import enrich as enrich_mod
from .collect import collect, verify as verify_mod
from .home import REPO_DIR


def _templates_if_needed(home):
    caps = home.capabilities()
    pend = decisions.approved_pending(home)
    if not pend:
        return 0
    if caps["tailoring_full"][0]:
        print(f"{len(pend)} accepted posting(s) wait for tailored documents (full mode: done by the agent, see AGENT_PROMPT.md)")
        return 0
    style = home.document_style()
    n = 0
    for r in pend:
        names = documents.filenames_for(r)
        target = os.path.join(home.path("cv_out"), "TEMPLATE_" + names["cv"])
        if os.path.exists(target) or os.path.exists(os.path.splitext(target)[0] + ".md"):
            continue
        cfg = home.search_config()
        cv, cl = documents.template_specs(r, home.profile(), style,
                                          description=documents.saved_description(home, r.get("URL")),
                                          vocabulary=list(cfg.get("skill_terms") or []) + list(cfg.get("keywords") or []))
        documents.render(cv, target, style=style)
        documents.render(cl, os.path.join(home.path("cl_out"), "TEMPLATE_" + names["cl"]), style=style)
        n += 1
    if n:
        print(f"template documents written for {n} accepted posting(s)")
    return n


def run(home, mode="auto"):
    from .cli import ensure_state
    from . import webpage
    ensure_state(home)
    cfg = home.search_config()
    today = date.today()
    if mode == "auto":
        day = str((cfg.get("weekly_list") or {}).get("full_search_day", "Monday")).lower()
        mode = "weekly" if today.strftime("%A").lower() == day else "daily"
    lines = [f"run {mode} {today.isoformat()}"]
    from .profile import Intake
    scan = Intake(home).scan_intake_folders()
    if scan["imported"]:
        lines.append(f"intake: {len(scan['imported'])} new document(s) imported from inputs/intake/ "
                     "(the agent turns them into profile entries)")
    note = None
    from . import cloud_sync
    online = cloud_sync.connected(home)
    if online:
        cs = cloud_sync.pull(home, log=lambda m: lines.append(m))
        if not cs.get("ok"):
            lines.append("online search not reachable; nothing fetched this time")
    if mode == "weekly" and online and not (cfg.get("cloud") or {}).get("local_collect"):
        note = f"Weekly run {today.isoformat()}: postings come from your online search."
    elif mode == "weekly":
        s = collect(home)
        v = verify_mod.verify(home)
        lines.append(f"collect: {s['candidates']} listings, {s['kept']} matched, {s['new']} new, "
                     f"{s.get('already_tracked', 0)} already tracked, {s.get('repeated_in_run', 0)} found twice")
        lines.append(f"verify: {v['expired']} expired, {v['unknown']} not checkable")
        if s["errors"]:
            lines.append("source errors: " + "; ".join(s["errors"][:10]))
        if s["skipped_agent_only"]:
            lines.append("left for the agent: " + ", ".join(s["skipped_agent_only"]))
        note = (f"Automatic weekly run {today.isoformat()}: {s['new']} new posting(s)"
                + (", some sources failed (see notes)" if s["errors"] else "") + ".")
    res = decisions.apply(home, seniority_cfg=cfg.get("seniority"))
    if online and res.get("applied"):
        cloud_sync.pull(home, log=lambda m: None)   # sends the new decisions online
    lines.append(f"sync: {res.get('applied', 0)} decision(s) applied")
    if mode == "weekly":
        e = enrich_mod.enrich(home)
        if e.get("reviewed"):
            lines.append(f"enrich: {e['reviewed']} reviewed")
    t = _templates_if_needed(home)
    if t:
        lines.append(f"templates: {t}")
    webpage.generate(home, weekly_note=note)
    if mode == "weekly" and (cfg.get("weekly_list") or {}).get("summary_markdown", True):
        weekly.weekly_summary(home, note=note)
    if mode == "weekly":
        lines.append(checkpoint.report(home, today.isoformat()).splitlines()[0])
    lines.append(f"page: {home.path('weekly_html')}")
    weekly.append_note(home, "\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit("use ./run.sh run <weekly|daily|auto>")
