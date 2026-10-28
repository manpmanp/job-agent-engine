# Job-search agent engine
# File:    engine/checkpoint.py
# Purpose: Per-run search checkpoints and named-employer coverage report.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.3.0
# Date:    2026-10-28

"""
Run checkpoints for the full weekly search.

A search run is long and can be interrupted. Progress is written to disk
phase by phase and employer by employer, so an interrupted run leaves an
inspectable trail, and coverage against the named-employer list is a
mechanical diff rather than something the agent has to remember.

    ./run.sh checkpoint phase 2026-11-02 indeed started
    ./run.sh checkpoint phase 2026-11-02 indeed done "4 new"
    ./run.sh checkpoint employer 2026-11-02 "Example Corp" 0 "nothing open"
    ./run.sh checkpoint report 2026-11-02
"""
import json
import os
from datetime import datetime, timezone


def _path(home, run_date):
    return os.path.join(home.path("search_progress"), f"{run_date}.json")


def _load(home, run_date):
    p = _path(home, run_date)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"run_date": run_date, "started_at": datetime.now(timezone.utc).isoformat(),
            "phases": {}, "employers_checked": {}}


def _save(home, run_date, data):
    os.makedirs(home.path("search_progress"), exist_ok=True)
    data["last_updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(_path(home, run_date), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def mark_phase(home, run_date, phase, status, note=""):
    data = _load(home, run_date)
    data["phases"][phase] = {"status": status, "note": note, "at": datetime.now(timezone.utc).isoformat()}
    _save(home, run_date, data)


def mark_checked(home, run_date, employer, found=0, note=""):
    data = _load(home, run_date)
    data["employers_checked"][employer] = {"found": int(found), "note": note, "at": datetime.now(timezone.utc).isoformat()}
    _save(home, run_date, data)


def coverage(home, run_date):
    names = [e["name"] for e in home.employers()]
    checked = set(_load(home, run_date).get("employers_checked", {}))
    return len([n for n in names if n in checked]), len(names), [n for n in names if n not in checked]


def report(home, run_date):
    data = _load(home, run_date)
    done, total, missing = coverage(home, run_date)
    lines = [f"Run {run_date}: {done}/{total} named employers checked.", "Phases:"]
    for name, info in data.get("phases", {}).items():
        lines.append(f"  {name}: {info['status']} {('(' + info['note'] + ')') if info.get('note') else ''}")
    if missing:
        lines.append(f"Not checked this run ({len(missing)}):")
        lines += [f"  - {m}" for m in missing]
    elif total:
        lines.append("All named employers checked.")
    return "\n".join(lines)


def latest_run(home):
    d = home.path("search_progress")
    if not os.path.isdir(d):
        return None
    runs = sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json"))
    return runs[-1] if runs else None
