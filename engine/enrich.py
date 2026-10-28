# Job-search agent engine
# File:    engine/enrich.py
# Purpose: Optional AI review of auto-collected postings through the Anthropic API (category, seniority, arrangement, skills, fit).
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.3.0
# Date:    2026-10-28

"""
./run.sh enrich

Optional. Runs only when an Anthropic API key is available (environment
variable ANTHROPIC_API_KEY, or inputs/secrets.json {"anthropic_api_key":
"..."}) and search_config.enrichment.enabled is true. Without a key the
rule-based values from collection stay as they are.

For each auto-collected posting not yet reviewed, the model receives the
title, employer, location and description, the configured categories and
seniority policy, and returns category, seniority, work arrangement, a
skills summary and a one-line fit note. The candidate profile is sent only
if enrichment.send_profile is true (default false), because that sends
personal data to the API.

Costs are per use on your own API account; enrichment.max_per_run (default
25) caps a run.
"""
import json
import os
from datetime import date

from . import tracker as tr
from .collect import http

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-5-5"
MARK = "AI-reviewed"


def api_key(home):
    k = os.environ.get("ANTHROPIC_API_KEY")
    if k:
        return k
    p = os.path.join(home.path("inputs"), "secrets.json")
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return (json.load(f) or {}).get("anthropic_api_key") or None
        except ValueError:
            return None
    return None


def status(home):
    cfg = (home.search_config().get("enrichment") or {})
    if not cfg.get("enabled"):
        return False, "optional: set search_config.enrichment.enabled and provide an Anthropic API key"
    if not api_key(home):
        return False, "enabled, but no API key (ANTHROPIC_API_KEY or inputs/secrets.json)"
    return True, f"model {cfg.get('model') or DEFAULT_MODEL}, profile {'sent' if cfg.get('send_profile') else 'not sent'}"


def _descriptions(home):
    d, out = home.path("new_postings"), {}
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if f.startswith("collect_") and f.endswith(".json"):
            try:
                with open(os.path.join(d, f), "r", encoding="utf-8") as fh:
                    for c in json.load(fh).get("kept_candidates", []):
                        out[c.get("url")] = c.get("description") or ""
            except (ValueError, OSError):
                continue
    return out


def _prompt(row, desc, cfg, profile_summary):
    sen = cfg.get("seniority") or {}
    return (
        "You classify one job posting for a job-search tracker. Use only the information given. "
        "Answer with a single JSON object and nothing else, with keys: "
        '"category" (exactly one of the list), "seniority" (one of the levels), '
        '"arrangement" (Remote, Hybrid, Onsite or Not stated), "skills" (comma-separated, max 10, taken from the posting), '
        '"fit" (one short sentence; if no candidate summary is given, describe the role level and focus instead).\n\n'
        f"Categories: {json.dumps(cfg.get('categories') or [])}\n"
        f"Seniority levels: {json.dumps(sen.get('levels') or [])}\n"
        f"Preferred seniority: {json.dumps(sen.get('preferred') or [])}\n"
        + (f"Candidate summary: {profile_summary}\n" if profile_summary else "")
        + f"\nTitle: {row.get('Title')}\nEmployer: {row.get('Employer')}\nLocation: {row.get('Location')}\n"
        f"Description:\n{(desc or '')[:5000]}"
    )


def _profile_summary(home):
    p = home.profile()
    parts = []
    if p.get("summary"):
        parts.append(p["summary"])
    for e in (p.get("experience") or [])[:4]:
        parts.append(f"{e.get('title')} at {e.get('organization')}")
    for g in p.get("skills") or []:
        parts.append(", ".join(g.get("items") or []))
    lvl = (p.get("preferences") or {}).get("own_seniority_level")
    if lvl:
        parts.append(f"own level: {lvl}")
    return "; ".join(x for x in parts if x)[:1500]


def enrich(home):
    on, why = status(home)
    if not on:
        print(f"enrichment off: {why}")
        return {"reviewed": 0}
    cfg = home.search_config()
    ecfg = cfg.get("enrichment") or {}
    model = ecfg.get("model") or DEFAULT_MODEL
    limit = int(ecfg.get("max_per_run", 25))
    key = api_key(home)
    descs = _descriptions(home)
    prof = _profile_summary(home) if ecfg.get("send_profile") else ""
    todo = [r for r in tr.read_all_rows(home.path("tracker"))
            if tr.status_bucket(r.get("Status")) == "active" and "auto-collected" in str(r.get("Notes") or "")
            and MARK not in str(r.get("Notes") or "")][:limit]
    updates, failed = [], 0
    for r in todo:
        resp, data = http.post_json(API_URL, {
            "model": model, "max_tokens": 500,
            "messages": [{"role": "user", "content": _prompt(r, descs.get(r.get("URL")), cfg, prof)}],
        }, headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
        try:
            text = "".join(b.get("text", "") for b in (data or {}).get("content", []) if b.get("type") == "text")
            j = json.loads(text[text.index("{"): text.rindex("}") + 1])
        except (ValueError, AttributeError):
            failed += 1
            if resp.status in (401, 403):
                print("enrichment stopped: the API key was rejected")
                break
            continue
        row = dict(r)
        if j.get("category") in (cfg.get("categories") or []):
            row["Category"] = j["category"]
        if j.get("seniority"):
            row["Seniority Level"] = str(j["seniority"])
        if j.get("arrangement") in ("Remote", "Hybrid", "Onsite", "Not stated"):
            row["Remote/Hybrid/Onsite"] = j["arrangement"]
        if j.get("skills"):
            row["Required Skills (summary)"] = str(j["skills"])[:400]
        row["Notes"] = f'{r.get("Notes") or ""} | {MARK} {date.today().isoformat()}: {str(j.get("fit") or "")[:300]}'.strip(" |")
        updates.append(row)
    if updates:
        tr.update(home.path("tracker"), updates, seniority_cfg=cfg.get("seniority"),
                  act_asap_after_days=int(cfg.get("act_asap_after_days", 7)))
    print(f"enriched {len(updates)} posting(s)" + (f", {failed} failed" if failed else ""))
    return {"reviewed": len(updates), "failed": failed}
