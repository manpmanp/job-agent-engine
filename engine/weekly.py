# Job-search agent engine
# File:    engine/weekly.py
# Purpose: Search plan, posting inbox and the weekly summary.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.3.0
# Date:    2026-10-28

"""
Search plan, posting inbox and the weekly compilation.

The search itself is carried out by the agent (an LLM with web/browser
tools, following agent/AGENT_PROMPT.md). The engine gives it the plan from the
user's search config and takes the results back as plain JSON rows:

    ./run.sh plan                       print the search plan
    ./run.sh add-postings found.json    merge found rows into the tracker
    ./run.sh weekly ["note"]            weekly page + weekly summary
"""
import json
import os
from datetime import date

from . import tracker as tr
from .webpage import compute_action

REQUIRED_ROW_FIELDS = ("Title", "Employer", "URL")


def search_plan(home):
    cfg = home.search_config()
    caps = home.capabilities()
    lines = ["# Search plan", ""]
    if not caps["search"][0]:
        lines += [f"Search service is idle: {caps['search'][1]}.",
                  "The weekly list and decision sync still run on what is already in the tracker."]
        return "\n".join(lines)
    locs = cfg["locations"]
    loc_names = [l["name"] if isinstance(l, dict) else str(l) for l in locs]
    lines += ["## Keywords (one keyword + one location per query)"] + [f"- {k}" for k in cfg["keywords"]]
    lines += ["", "## Locations (priority order)"]
    for l in locs:
        if isinstance(l, dict):
            extra = ", ".join(f"{k}: {v}" for k, v in l.items() if k != "name" and v not in (None, "", []))
            lines.append(f"- {l['name']}" + (f" ({extra})" if extra else ""))
        else:
            lines.append(f"- {l}")
    if cfg.get("max_commute"):
        lines.append(f"- Maximum commute: {cfg['max_commute']} (flag unverified commute times, do not assume)")
    wa = cfg.get("work_arrangement") or {}
    lines.append(f"- Work arrangement accepted: " + ", ".join(k.replace("_ok", "") for k, v in wa.items() if v))
    if cfg.get("roles_description"):
        lines += ["", "## Roles", cfg["roles_description"]]
    lines += ["", "## Categories (exactly one per posting)"] + [f"- {c}" for c in cfg.get("categories", [])]
    sen = cfg.get("seniority") or {}
    lines += ["", "## Seniority",
              f"- Preferred: {', '.join(sen.get('preferred', []))}",
              f"- Flag as likely too senior (do not discard): {', '.join(sen.get('flag_as_too_senior', []))}",
              f"- Flag as likely too junior: {', '.join(sen.get('flag_as_too_junior', []))}"]
    src = cfg.get("sources") or {}
    lines += ["", "## Sources to use"] + [f"- {k}" for k, v in src.items() if v is True]
    for s in src.get("extra_sites", []) or []:
        lines.append(f"- {s}")
    lines += ["", "## Credible confirmation only from"] + [f"- {s}" for s in cfg.get("credible_sources", [])]
    lines.append(f"Not sufficient on their own: {', '.join(cfg.get('non_credible_examples', []))}")
    emps = home.employers()
    if emps:
        lines += ["", f"## Named employers ({len(emps)}) - check each, record with './run.sh checkpoint employer'"]
        for e in emps:
            lines.append(f"- {e['name']}: {', '.join(e.get('urls', []))}" + (f"  ({e['note']})" if e.get("note") else ""))
    log = home.path("rejection_log")
    if os.path.exists(log):
        lines += ["", f"## Soft context: past rejection reasons in {os.path.relpath(log, home.root)} (mention matches, never silently drop)"]
    return "\n".join(lines)


def add_postings(home, json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        rows = json.load(f)
    if isinstance(rows, dict):
        rows = rows.get("postings", [])
    today = date.today().isoformat()
    good, bad = [], []
    for r in rows:
        missing = [k for k in REQUIRED_ROW_FIELDS if not r.get(k)]
        if missing:
            bad.append((r.get("Title") or "?", missing))
            continue
        r = {k: v for k, v in r.items() if k in tr.ROW_FIELDS}
        r.setdefault("Date Found", today)
        r.setdefault("Seniority Level", "Not stated")
        r.setdefault("Deadline", "rolling")
        good.append(r)
    existing = {(r.get("URL"), r.get("Title")) for r in tr.read_all_rows(home.path("tracker"))}
    new = [r for r in good if (r["URL"], r["Title"]) not in existing]
    cfg = home.search_config()
    tr.update(home.path("tracker"), good, seniority_cfg=cfg.get("seniority"),
              act_asap_after_days=int(cfg.get("act_asap_after_days", 7)))
    for t, m in bad:
        print(f"skipped '{t}': missing {', '.join(m)}")
    print(f"{len(new)} new posting(s), {len(good) - len(new)} update(s) to tracked postings")
    return {"new": len(new), "updated": len(good) - len(new), "skipped": len(bad)}


def weekly_summary(home, note=None):
    cfg = home.search_config()
    rows = tr.read_all_rows(home.path("tracker"))
    active = [r for r in rows if tr.status_bucket(r.get("Status")) == "active"]
    found = [d for d in (tr.to_date(r.get("Date Found")) for r in active) if d]
    newest = max(found) if found else None
    new = [r for r in active if newest and tr.to_date(r.get("Date Found")) == newest]
    undecided = [r for r in active if not str(r.get("Status") or "").startswith("Approved")]
    approved = [r for r in active if str(r.get("Status") or "").startswith("Approved")]
    pending_docs = [r for r in approved if str(r.get("CV/Cover Letter Drafted (Y/N)") or "N").upper() != "Y"]
    urgent = [r for r in active if compute_action(r.get("Deadline"), tr.to_date(r.get("Announce Date")),
                                                  int(cfg.get("act_asap_after_days", 7)))]
    sen = cfg.get("seniority")

    def line(r):
        flag = {"senior": " [likely too senior]", "junior": " [likely too junior]"}.get(tr.seniority_bucket(r.get("Seniority Level"), sen), "")
        return f"- {r.get('Employer')}: {r.get('Title')} ({r.get('Location') or '?'}){flag} {r.get('URL') or ''}".rstrip()

    today = date.today().isoformat()
    out = [f"# Weekly job list, {today}", ""]
    if note:
        out += [f"_{note}_", ""]
    out += [f"Active: {len(active)}. New in latest search ({newest or 'none'}): {len(new)}. "
            f"Awaiting a decision: {len(undecided)}. Accepted: {len(approved)} ({len(pending_docs)} waiting for documents). "
            f"Flagged to act soon: {len(urgent)}.", ""]
    if new:
        out += ["## New in the latest search", ""]
        by_cat = {}
        for r in new:
            by_cat.setdefault(r.get("Category") or "Uncategorized", []).append(r)
        for cat in sorted(by_cat):
            out += [f"### {cat}"] + [line(r) for r in by_cat[cat]] + [""]
    if urgent:
        out += ["## Act soon"] + [line(r) for r in urgent] + [""]
    if pending_docs:
        out += ["## Accepted, documents not yet generated"] + [line(r) for r in pending_docs] + [""]
    d = home.path("weekly_summary")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"weekly_{today}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out).rstrip() + "\n")
    print(f"wrote {path}")
    return path


def append_note(home, text):
    p = home.path("notes")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(f"\n=== {date.today().isoformat()} ===\n{text.strip()}\n")
