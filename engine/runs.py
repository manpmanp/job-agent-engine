# Job-search agent engine
# File:    engine/runs.py
# Purpose: Complete runs without an AI agent (weekly, daily, auto) and scheduling instructions.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.2.0
# Date:    2026-10-28

"""
./run.sh run weekly   collect -> verify -> sync -> enrich (if on) ->
                      template documents (if no candidate material) -> weekly page + summary
./run.sh run daily    sync -> template documents -> weekly page
./run.sh run auto     weekly on search_config.weekly_list.full_search_day, daily otherwise
./run.sh schedule     prints a crontab line / macOS launchd file to run 'auto' every day

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
        cv, cl = documents.template_specs(r, home.profile(), style)
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
    note = None
    if mode == "weekly":
        s = collect(home)
        v = verify_mod.verify(home)
        lines.append(f"collect: {s['candidates']} listings, {s['new']} new, {s['duplicates']} already tracked")
        lines.append(f"verify: {v['expired']} expired, {v['unknown']} not checkable")
        if s["errors"]:
            lines.append("source errors: " + "; ".join(s["errors"][:10]))
        if s["skipped_agent_only"]:
            lines.append("left for the agent: " + ", ".join(s["skipped_agent_only"]))
        note = (f"Automatic weekly run {today.isoformat()}: {s['new']} new posting(s)"
                + (", some sources failed (see notes)" if s["errors"] else "") + ".")
    res = decisions.apply(home, seniority_cfg=cfg.get("seniority"))
    lines.append(f"sync: {res.get('applied', 0)} decision(s) applied")
    if mode == "weekly":
        e = enrich_mod.enrich(home)
        if e.get("reviewed"):
            lines.append(f"enrich: {e['reviewed']} reviewed")
    t = _templates_if_needed(home)
    if t:
        lines.append(f"templates: {t}")
    if mode == "weekly" or res.get("applied") or t:
        webpage.generate(home, weekly_note=note)
        if mode == "weekly" and (cfg.get("weekly_list") or {}).get("summary_markdown", True):
            weekly.weekly_summary(home, note=note)
    if mode == "weekly":
        lines.append(checkpoint.report(home, today.isoformat()).splitlines()[0])
    weekly.append_note(home, "\n".join(lines))
    print("\n".join(lines))


def schedule_text(home):
    runner = os.path.join(REPO_DIR, "run.sh")
    log = os.path.join(os.path.dirname(home.path("notes")), "run.log")
    path = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
    cron = f'2 8 * * * PATH={path} "{runner}" --home "{home.root}" run auto >> "{log}" 2>&1'
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>local.job-agent-engine</string>
  <key>ProgramArguments</key><array>
    <string>{runner}</string><string>--home</string><string>{home.root}</string><string>run</string><string>auto</string>
  </array>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>{path}</string></dict>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>2</integer></dict>
  <key>StandardOutPath</key><string>{log}</string>
  <key>StandardErrorPath</key><string>{log}</string>
</dict></plist>"""
    return (
        "Run the engine every day at 08:02 ('auto' does the full weekly pass on your full_search_day and a sync on other days).\n\n"
        "Linux / macOS with cron, add this line with 'crontab -e':\n\n"
        f"{cron}\n\n"
        "macOS launchd (also runs after the Mac wakes if 08:02 was missed): save as\n"
        "~/Library/LaunchAgents/local.job-agent-engine.plist, then run\n"
        "launchctl load ~/Library/LaunchAgents/local.job-agent-engine.plist\n\n"
        f"{plist}\n\n"
        "run.sh uses the engine's own .venv for Python. If node lives elsewhere on your machine,\n"
        "add its folder to PATH above (see 'which node').\n"
    )


if __name__ == "__main__":
    sys.exit("use ./run.sh run <weekly|daily|auto>")
