# Job-search agent engine
# File:    engine/collect/__init__.py
# Purpose: Online collection run: query every enabled source, filter, classify, de-duplicate, add to the tracker.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
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


def _secrets(home):
    p = os.path.join(home.path("inputs"), "secrets.json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


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

    # Optional aggregators (off unless switched on in search_config.sources).
    keys = _secrets(home)
    agg = []
    if src.get("jsearch") and only in (None, "aggregators", "jsearch"):
        key = keys.get("jsearch_api_key") or os.environ.get("JSEARCH_API_KEY")
        if key:
            agg.append(("JSearch", lambda: sources.jsearch(keywords, locations, key, keys.get("jsearch_host") or "openwebninja",
                                                            max_pages=int(src.get("jsearch_pages", 1)))))
        else:
            summary["errors"].append("JSearch is on but has no key (inputs/secrets.json: jsearch_api_key)")
    if src.get("adzuna") and only in (None, "aggregators", "adzuna"):
        aid, akey = keys.get("adzuna_app_id") or os.environ.get("ADZUNA_APP_ID"), keys.get("adzuna_app_key") or os.environ.get("ADZUNA_APP_KEY")
        if aid and akey:
            agg.append(("Adzuna", lambda: sources.adzuna(keywords, locations, aid, akey)))
        else:
            summary["errors"].append("Adzuna is on but has no app id/key (inputs/secrets.json: adzuna_app_id, adzuna_app_key)")
    if src.get("hn_who_is_hiring") and only in (None, "aggregators", "hn"):
        agg.append(("HN Who is hiring", sources.hn_who_is_hiring))
    if src.get("yc_jobs") and only in (None, "aggregators", "hn"):
        agg.append(("YC job posts", sources.yc_jobs))
    for name, fn in agg:
        checkpoint.mark_phase(home, run_date, name, "started")
        found, err = fn()
        candidates += found
        summary["by_source"][name] = len(found)
        if err:
            summary["errors"].append(err)
        checkpoint.mark_phase(home, run_date, name, "failed" if err and not found else "done",
                              f"{len(found)} candidates" + (f"; {err}" if err else ""))

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


def _filter_and_build(cfg, home, candidates, keywords, locations, run_date, explicit=False):
    scope = cfg.get("match_scope", "title")
    exclude = cfg.get("exclude_terms") or []
    remote_ok = (cfg.get("work_arrangement") or {}).get("remote_ok", True)
    cats = cfg.get("categories") or []
    rules = cfg.get("category_rules") or {}
    prof = home.profile()
    vocab = list(cfg.get("skill_terms") or []) + list(keywords) + match.default_vocabulary()
    srcs = cfg.get("sources") or {}
    confirm = {"left": int(srcs.get("confirm_leads_max", 25)) if srcs.get("confirm_leads", True) else 0,
               "done": 0, "errors": []}
    for g in prof.get("skills") or []:
        vocab += list(g.get("items") or [])
    out, full = [], []
    for c in candidates:
        if not c.get("title") or not c.get("url"):
            continue
        hit, where = match_keywords_for(c, keywords, scope, exclude)
        if explicit and not hit:
            hit, where = ["(none)"], "a URL you gave"
        if not hit:
            continue
        if c.get("_wd_path") and not c.get("description"):
            sources.workday_details(c)  # only for matched listings: one request each
        if c.get("lead") and confirm["left"] > 0 and str(c.get("url") or "").startswith("http"):
            confirm["left"] -= 1
            err = sources.confirm_lead(c)  # opens the posting page and reads it
            if err:
                confirm["errors"].append(err)
            else:
                confirm["done"] += 1
            hit, where = match_keywords_for(c, keywords, scope, exclude)
            if not hit:
                continue
        loc = match.match_location(c.get("location_text"), locations, remote_ok, c.get("is_remote"))
        if loc is None and explicit:
            loc = "given"
        if loc is None:
            vague = re.match(r"^\s*\d+\s+locations?\s*$", str(c.get("location_text") or ""), re.I)
            if c.get("lead") or not c.get("location_text") or vague:
                loc = "unknown"  # leads and location-less listings are kept for confirmation
            else:
                continue
        stated = sources.stated_deadline(c.get("description"))
        board_deadline = c.get("deadline") or ""
        if stated:
            c["deadline"] = stated
        sen = match.seniority(c["title"])
        skills = ", ".join(c.get("skills") or []) or match.skills_summary(c.get("description"), vocab)
        notes = [f"Source: {c['source']}", f"auto-collected {run_date}", f"matched {', '.join(hit)} in {where}"]
        if loc == "unknown":
            notes.append("location not stated in listing, check")
        if c.get("lead"):
            notes.append("link from careers page, open to confirm it is a live posting")
        if c.get("posted_text") and not c.get("published"):
            notes.append(f"posted: {c['posted_text']}")
        if stated and board_deadline and stated != board_deadline:
            notes.append(f"deadline {stated} as stated in the posting (job board says {board_deadline})")
        if tr.seniority_bucket(sen, cfg.get("seniority")) == "senior" and match.welcomes_junior(c.get("description")):
            notes.append(f"seniority flag ({sen}) may not apply: the posting says junior applicants are welcome")
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
        full.append({**{k: v for k, v in c.items() if k != "description" and not k.startswith("_")},
                     "description": (c.get("description") or "")[:6000]})
    if confirm["done"] or confirm["errors"]:
        print(f"opened {confirm['done'] + len(confirm['errors'])} link lead(s): {confirm['done']} read"
              + (f", {len(confirm['errors'])} not readable" if confirm["errors"] else ""))
    return out, full


def match_keywords_for(c, keywords, scope, exclude):
    desc = (c.get("description") or "") + " " + " ".join(c.get("skills") or [])
    return match.match_keywords(c.get("title"), desc, keywords, scope=scope, exclude_terms=exclude)


def fetch_url(home, url, add=False, render=True, employer=None, title=None):
    """'./run.sh fetch <url>': reads one posting page (extract.py), saves its
    text for tailoring and the JD snapshot, and with add=True puts it in the
    tracker even if it does not match the search filters (you chose it)."""
    from . import extract
    run_date = date.today().isoformat()
    d = extract.fetch_posting(url, render=render)
    if d.get("error") and not d.get("description"):
        print(f"could not read {url}: {d['error']}")
        return d
    c = {"title": title or d.get("title") or "", "employer": employer or d.get("employer") or "",
         "location_text": d.get("location_text") or "", "url": url, "apply_url": "",
         "published": d.get("published") or "", "deadline": d.get("deadline") or "",
         "description": d.get("description") or "", "is_remote": bool(d.get("is_remote")), "workplace": "",
         "employment_type": d.get("employment_type") or "", "skills": [], "source": f"Fetched page ({d.get('how')})"}
    stated = sources.stated_deadline(c["description"])
    print(f"read {url} ({d.get('how')}{', complete' if d.get('complete') else ', INCOMPLETE'}): "
          f"{len(c['description'])} characters")
    for k in ("title", "employer", "location_text", "deadline", "employment_type"):
        if c.get(k):
            print(f"  {k}: {c[k]}")
    if stated and stated != c["deadline"]:
        print(f"  deadline stated in the text: {stated}")
    if d.get("salary"):
        print(f"  salary: {d['salary']}")
    if not d.get("complete"):
        print(f"  note: {d.get('error')}")
    os.makedirs(home.path("new_postings"), exist_ok=True)
    p = os.path.join(home.path("new_postings"), f"fetched_{run_date}.json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        saved = {"kept_candidates": []}
    saved["kept_candidates"] = [k for k in saved.get("kept_candidates", []) if k.get("url") != url] + [
        {**c, "description": c["description"][:60000], "how": d.get("how"), "complete": d.get("complete")}]
    with open(p, "w", encoding="utf-8") as f:
        json.dump(saved, f, indent=2, ensure_ascii=False)
    print(f"  text saved in {p}")
    if add:
        if not c["title"] or not c["employer"]:
            print("  not added: title or employer unknown; pass --title and --employer")
            return d
        cfg, _ = _cfg(home)
        rows, _full = _filter_and_build(cfg, home, [c], cfg.get("keywords") or [], cfg.get("locations") or [],
                                        run_date, explicit=True)
        existing = {r.get("URL") for r in tr.read_all_rows(home.path("tracker"))}
        new = [r for r, _c in rows if r["URL"] not in existing]
        if new:
            tr.update(home.path("tracker"), new, seniority_cfg=cfg.get("seniority"),
                      act_asap_after_days=int(cfg.get("act_asap_after_days", 7)))
            print(f"  added to the tracker: {new[0]['Employer']}: {new[0]['Title']}")
        else:
            print("  already in the tracker")
    return d
