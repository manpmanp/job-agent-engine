# Job-search agent engine
# File:    engine/collect/__init__.py
# Purpose: Online collection run: query every enabled source, filter, classify, de-duplicate, add to the tracker.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.3.0
# Date:    2026-10-28

"""
./run.sh collect

1. Arbetsformedlingen JobSearch API, one query per keyword (if
   sources.jobtech is on).
2. Every named employer (if sources.employer_sites is on): its job-board
   API when the careers URL belongs to a known system (Greenhouse, Lever,
   Ashby, Workday, SmartRecruiters), otherwise the page itself, read via
   its structured JobPosting data or, failing that, its job links.
3. Each candidate is kept only if a keyword matches (title, or description
   when match_scope allows) and the location matches a configured location
   (or is remote and remote is accepted).
4. Seniority, category, work arrangement and a skills summary are set by
   rules (engine/collect/match.py) and marked as automatic in Notes.
5. Candidates already in the tracker are skipped: same (URL, Title), same
   URL, or the same employer + title from another source. Existing rows are
   never modified by collection.
6. New rows go into the tracker; the full candidate list, with
   descriptions, is saved in state/new_postings/collect_<date>.json.

Network failures are recorded per source in the checkpoint and the run
summary; the run always completes.
"""
import json
import os
import re
from datetime import date

from .. import tracker as tr
from .. import checkpoint
from . import sources, match


def _cfg(home):
    cfg = home.search_config()
    src = cfg.get("sources") or {}
    return cfg, src


def collect(home, run_date=None, only=None):
    run_date = run_date or date.today().isoformat()
    cfg, src = _cfg(home)
    keywords = cfg.get("keywords") or []
    locations = cfg.get("locations") or []
    summary = {"run_date": run_date, "candidates": 0, "kept": 0, "new": 0, "duplicates": 0, "already_tracked": 0, "repeated_in_run": 0,
               "errors": [], "by_source": {}, "skipped_agent_only": []}
    if not keywords or not locations:
        print("search is idle: add keywords and locations to inputs/search_config.json")
        return summary

    candidates = []

    if src.get("jobtech", True) and only in (None, "jobtech"):
        checkpoint.mark_phase(home, run_date, "jobtech_api", "started")
        found, err = sources.jobtech(keywords)
        candidates += found
        summary["by_source"]["Arbetsformedlingen API"] = len(found)
        if err:
            summary["errors"].append(err)
        checkpoint.mark_phase(home, run_date, "jobtech_api", "failed" if err and not found else "done",
                              f"{len(found)} candidates" + (f"; {err}" if err else ""))

    if src.get("employer_sites", True) and only in (None, "employers"):
        checkpoint.mark_phase(home, run_date, "employer_sites", "started")
        for emp in home.employers():
            name = emp["name"]
            got, errs, kinds = [], [], []
            for url in emp.get("urls", []) or [""]:
                kind, p = sources.detect_ats(url, emp.get("ats"))
                kinds.append(kind)
                if kind == "agent_only":
                    continue
                if kind == "greenhouse":
                    f, e = sources.greenhouse(p["board"], name)
                elif kind == "lever":
                    f, e = sources.lever(p["company"], name)
                elif kind == "ashby":
                    f, e = sources.ashby(p["org"], name)
                elif kind == "workday":
                    f, e = sources.workday(p["host"], p["tenant"], p["site"], name, keywords)
                elif kind == "smartrecruiters":
                    f, e = sources.smartrecruiters(p["company"], name)
                else:
                    f, e = sources.html_page(p.get("url") or url, name, keywords)
                got += f
                if e:
                    errs.append(e)
            candidates += got
            if kinds and all(k == "agent_only" for k in kinds):
                summary["skipped_agent_only"].append(name)
                continue  # left for the agent; not marked as checked
            summary["by_source"][name] = len(got)
            summary["errors"] += errs
            checkpoint.mark_checked(home, run_date, name, len(got),
                                    ("; ".join(errs) if errs else f"{len(got)} listing(s) via {', '.join(sorted(set(kinds)))}"))
        checkpoint.mark_phase(home, run_date, "employer_sites", "done")

    summary["candidates"] = len(candidates)
    rows, kept_full = _filter_and_build(cfg, home, candidates, keywords, locations, run_date)
    summary["kept"] = len(rows)

    existing = tr.read_all_rows(home.path("tracker"))
    keys = {(r.get("URL"), r.get("Title")) for r in existing}
    urls = {r.get("URL") for r in existing if r.get("URL")}
    names = {match.norm_key(r.get("Employer"), r.get("Title")) for r in existing}
    new_rows, seen_batch = [], set()
    for row, cand in rows:
        k = match.norm_key(row["Employer"], row["Title"])
        if ((row["URL"], row["Title"]) in keys or row["URL"] in urls or (cand.get("apply_url") and cand["apply_url"] in urls)
                or k in names):
            summary["duplicates"] += 1
            summary["already_tracked"] += 1
            continue
        if k in seen_batch or row["URL"] in seen_batch:
            summary["duplicates"] += 1
            summary["repeated_in_run"] += 1
            continue
        seen_batch.update([k, row["URL"]])
        new_rows.append(row)
    summary["new"] = len(new_rows)

    os.makedirs(home.path("new_postings"), exist_ok=True)
    with open(os.path.join(home.path("new_postings"), f"collect_{run_date}.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "new_rows": new_rows, "kept_candidates": kept_full}, f, indent=2, ensure_ascii=False)
    if new_rows:
        tr.update(home.path("tracker"), new_rows, seniority_cfg=cfg.get("seniority"),
                  act_asap_after_days=int(cfg.get("act_asap_after_days", 7)))
    print(f"collected {summary['candidates']} listing(s), {summary['kept']} matched, {summary['new']} new, "
          f"{summary['already_tracked']} already tracked, {summary['repeated_in_run']} found twice in this run")
    for e in summary["errors"]:
        print(f"  [source error] {e}")
    if summary["skipped_agent_only"]:
        print(f"  left for the agent (no automated access): {', '.join(summary['skipped_agent_only'])}")
    return summary


def _filter_and_build(cfg, home, candidates, keywords, locations, run_date):
    scope = cfg.get("match_scope", "title")
    exclude = cfg.get("exclude_terms") or []
    remote_ok = (cfg.get("work_arrangement") or {}).get("remote_ok", True)
    cats = cfg.get("categories") or []
    rules = cfg.get("category_rules") or {}
    prof = home.profile()
    vocab = list(cfg.get("skill_terms") or []) + list(keywords) + match.default_vocabulary()
    for g in prof.get("skills") or []:
        vocab += list(g.get("items") or [])
    out, full = [], []
    for c in candidates:
        if not c.get("title") or not c.get("url"):
            continue
        hit, where = match_keywords_for(c, keywords, scope, exclude)
        if not hit:
            continue
        loc = match.match_location(c.get("location_text"), locations, remote_ok, c.get("is_remote"))
        if loc is None:
            vague = re.match(r"^\s*\d+\s+locations?\s*$", str(c.get("location_text") or ""), re.I)
            if c.get("lead") or not c.get("location_text") or vague:
                loc = "unknown"  # leads and location-less listings are kept for confirmation
            else:
                continue
        sen = match.seniority(c["title"])
        skills = ", ".join(c.get("skills") or []) or match.skills_summary(c.get("description"), vocab)
        notes = [f"Source: {c['source']}", f"auto-collected {run_date}", f"matched {', '.join(hit)} in {where}"]
        if loc == "unknown":
            notes.append("location not stated in listing, check")
        if c.get("lead"):
            notes.append("link from careers page, open to confirm it is a live posting")
        if c.get("posted_text") and not c.get("published"):
            notes.append(f"posted: {c['posted_text']}")
        if c.get("apply_url") and c["apply_url"] != c["url"]:
            notes.append(f"apply: {c['apply_url']}")
        row = {
            "Date Found": run_date, "Title": c["title"].strip(), "Employer": c.get("employer") or "",
            "Location": c.get("location_text") or "", "Category": match.category(c["title"], c.get("description"), cats, rules),
            "Seniority Level": sen, "Announce Date": c.get("published") or "", "Deadline": c.get("deadline") or "rolling",
            "Remote/Hybrid/Onsite": match.arrangement(c.get("workplace"), c.get("location_text"), c.get("description", "")[:1500]),
            "Required Skills (summary)": skills or "not extracted, see posting", "URL": c["url"],
            "Calendar Event Added (Y/N)": "N", "CV/Cover Letter Drafted (Y/N)": "N",
            "Status": "Unverified" if c.get("lead") else "New", "Notes": "; ".join(notes),
        }
        out.append((row, c))
        full.append({**{k: v for k, v in c.items() if k != "description"}, "description": (c.get("description") or "")[:6000]})
    return out, full


def match_keywords_for(c, keywords, scope, exclude):
    desc = (c.get("description") or "") + " " + " ".join(c.get("skills") or [])
    return match.match_keywords(c.get("title"), desc, keywords, scope=scope, exclude_terms=exclude)
