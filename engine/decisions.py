# Job-search agent engine
# File:    engine/decisions.py
# Purpose: Applies Accept/Reject decisions from the weekly page to the tracker.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.3.0
# Date:    2026-10-28

"""
Applies Accept/Reject decisions made on the weekly page to the tracker.

The page stores decisions in the browser (localStorage key
'jobAgentDecisions', keyed by "<URL>||<Title>") and its "Sync decisions"
button writes them to the decisions file in the agent home:

    {
      "https://example.com/job/1||FPGA Engineer": {"decision": "accepted", "ts": "..."},
      "https://example.com/job/2||Senior ASIC Designer": {
          "decision": "rejected", "reasons": ["Seniority level mismatch"], "note": "", "ts": "..."}
    }

Syncing is always a pull: nothing happens until './run.sh sync' (or the
agent) reads the file. The full payload is diffed against the state of the
last sync (sync_logs/latest_state.json), so only new or changed decisions
are applied; re-syncing the same file is a no-op.

accepted -> Status "Approved - ready for tailored documents"
rejected -> Status "Rejected: <reason1>; <reason2>", row moves to the
            Rejected sheet, one line per reason in the rejection log.
"""
import csv
import json
import os
from datetime import datetime, date, timezone

from . import tracker as tr

REJECTION_LOG_FIELDS = ["Date", "Employer", "Title", "Category", "Seniority Level", "Location", "Reason", "Note", "URL"]
APPROVED_STATUS = "Approved - ready for tailored documents"


def _comparable(d):
    return {k: v for k, v in (d or {}).items() if k != "ts"}


def diff_decisions(current, previous):
    return {k: d for k, d in current.items()
            if previous.get(k) is None or _comparable(previous.get(k)) != _comparable(d)}


def apply(home, decisions_path=None, seniority_cfg=None):
    decisions_path = decisions_path or home.path("decisions")
    if not os.path.exists(decisions_path):
        print(f"no decisions file at {decisions_path} - nothing to sync (click 'Sync decisions' on the weekly page first)")
        return {"applied": 0, "new_or_changed": 0}
    with open(decisions_path, "r", encoding="utf-8") as f:
        try:
            decisions = json.load(f) or {}
        except ValueError:
            print(f"[warn] {decisions_path} is not valid JSON - nothing applied")
            return {"applied": 0, "new_or_changed": 0}
    if not decisions:
        print("decisions file is empty - nothing to apply")
        return {"applied": 0, "new_or_changed": 0}

    log_dir = home.path("sync_logs")
    os.makedirs(log_dir, exist_ok=True)
    latest_path = os.path.join(log_dir, "latest_state.json")
    previous = {}
    if os.path.exists(latest_path):
        with open(latest_path, "r", encoding="utf-8") as f:
            previous = json.load(f) or {}

    to_process = diff_decisions(decisions, previous)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S_%fZ")
    with open(os.path.join(log_dir, f"sync_{stamp}.json"), "w", encoding="utf-8") as f:
        json.dump({"synced_at_utc": stamp, "total_decisions_in_payload": len(decisions),
                   "new_or_changed_count": len(to_process), "new_or_changed": to_process}, f, indent=2)

    if not to_process:
        print("no new or changed decisions since the last sync - nothing to apply")
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(decisions, f, indent=2)
        return {"applied": 0, "new_or_changed": 0}

    rows = tr.read_all_rows(home.path("tracker"))
    by_key = {(r.get("URL"), r.get("Title")): r for r in rows}
    updated, rejections, skipped = [], [], []
    today = date.today().isoformat()

    for key_str, d in to_process.items():
        if "||" not in key_str:
            continue
        url, title = key_str.split("||", 1)
        row = by_key.get((url, title))
        if row is None:
            skipped.append(title)
            continue
        row = dict(row)
        ts = d.get("ts", "")
        if d.get("decision") == "accepted":
            row["Status"] = APPROVED_STATUS
            row["Notes"] = f'{row.get("Notes") or ""} | Accepted via weekly page ({ts})'.strip(" |")
            updated.append(row)
        elif d.get("decision") == "rejected":
            reasons = d.get("reasons") or ([d["reason"]] if d.get("reason") else ["Not specified"])
            note = d.get("note", "")
            joined = "; ".join(reasons)
            row["Status"] = f"Rejected: {joined}"
            row["Notes"] = f'{row.get("Notes") or ""} | Rejected via weekly page ({ts}): {joined}{" - " + note if note else ""}'.strip(" |")
            updated.append(row)
            for reason in reasons:
                rejections.append({"Date": today, "Employer": row.get("Employer"), "Title": row.get("Title"),
                                   "Category": row.get("Category"), "Seniority Level": row.get("Seniority Level"),
                                   "Location": row.get("Location"), "Reason": reason, "Note": note, "URL": row.get("URL")})

    if updated:
        tr.update(home.path("tracker"), updated, seniority_cfg=seniority_cfg)
    if rejections:
        log = home.path("rejection_log")
        exists = os.path.exists(log) and os.path.getsize(log) > 0
        with open(log, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=REJECTION_LOG_FIELDS)
            if not exists:
                w.writeheader()
            w.writerows(rejections)
    for t in skipped:
        print(f"skip (not in tracker): {t}")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(decisions, f, indent=2)
    print(f"applied {len(updated)} decision(s), logged {len(rejections)} rejection reason(s)")
    return {"applied": len(updated), "new_or_changed": len(to_process), "rejection_lines": len(rejections), "skipped": skipped}


def approved_pending(home):
    """Rows accepted but without documents yet."""
    return [r for r in tr.read_all_rows(home.path("tracker"))
            if str(r.get("Status") or "").startswith("Approved")
            and str(r.get("CV/Cover Letter Drafted (Y/N)") or "N").strip().upper() != "Y"]
