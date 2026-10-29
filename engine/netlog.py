# Job-search agent engine
# File:    engine/netlog.py
# Purpose: Reads state/network_log.jsonl for the app's "Network activity" report: what came in from the internet and what went out.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.4
# Date:    2026-10-29

"""
Every request the engine makes is recorded by engine/collect/http.py (and
browser renders by engine/collect/extract.py). This module summarizes them:
per purpose (job search, employer boards, web pages, AI, your online Job
Agent), how many requests, how much was sent and received, and the most
recent requests with what each one carried. Key values in addresses are
hidden in the log; headers (where API keys travel) are never recorded.
"""
import json
import os
from datetime import datetime, timedelta


def log_path(home):
    return os.path.join(os.path.dirname(home.path("notes")), "network_log.jsonl")


def read(home):
    out = []
    try:
        with open(log_path(home), "r", encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def report(home, days=30, recent=300):
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    rows = [r for r in read(home) if str(r.get("ts") or "") >= since]
    groups = {}
    for r in rows:
        g = groups.setdefault(r.get("purpose") or "Other", {"purpose": r.get("purpose") or "Other", "requests": 0,
                                                             "sent_bytes": 0, "received_bytes": 0, "hosts": set(),
                                                             "failed": 0, "last": ""})
        g["requests"] += 1
        g["sent_bytes"] += int(r.get("sent_bytes") or 0)
        g["received_bytes"] += int(r.get("received_bytes") or 0)
        g["hosts"].add(r.get("host") or "")
        g["last"] = max(g["last"], str(r.get("ts") or ""))
        if r.get("error") or not (200 <= int(r.get("status") or 0) < 400):
            g["failed"] += 1
    summary = sorted(({**g, "hosts": sorted(h for h in g["hosts"] if h)[:12], "host_count": len(g["hosts"])}
                      for g in groups.values()), key=lambda g: -g["requests"])
    return {"days": days, "total": len(rows),
            "sent_bytes": sum(g["sent_bytes"] for g in summary), "received_bytes": sum(g["received_bytes"] for g in summary),
            "summary": summary, "recent": list(reversed(rows[-recent:])), "log": log_path(home)}
