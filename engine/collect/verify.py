# Job-search agent engine
# File:    engine/collect/verify.py
# Purpose: Checks that tracked postings are still open and moves closed ones to Expired.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.3.0
# Date:    2026-10-28

"""
./run.sh verify

For every Active posting with a URL:
- Platsbanken ads: the JobSearch API says whether the ad is removed.
- Job-board APIs and ordinary pages: HTTP 404/410 means closed; a page whose
  structured data has a validThrough date in the past means closed.
- A fixed deadline that has passed means closed.
- LinkedIn/Indeed URLs are left to the agent.
- Anything that cannot be reached is not touched; it gets a note instead.

Closed postings get Status "Expired" with a note, except accepted ones
(Status "Approved..."), which only get a note so nothing you chose
disappears without you seeing it.
"""
import re
from datetime import date

from .. import tracker as tr
from . import http, sources


def _platsbanken_id(url):
    m = re.search(r"arbetsformedlingen\.se/platsbanken/annonser/(\d+)", url or "")
    return m.group(1) if m else None


def check(url):
    """'live' | 'closed:<reason>' | 'unknown:<reason>' | 'skip'"""
    if not url or not url.startswith("http"):
        return "skip"
    if "linkedin.com" in url or "indeed." in url:
        return "skip"
    ad = _platsbanken_id(url)
    if ad:
        st = sources.jobtech_ad_status(ad)
        return {"live": "live", "removed": "closed:removed from Platsbanken"}.get(st, "unknown:Platsbanken API not reachable")
    r = http.get_page(url)
    if r.status in (404, 410):
        return f"closed:HTTP {r.status}"
    if not r.ok:
        return f"unknown:{r.error or 'HTTP ' + str(r.status)}"
    page = r.text()
    for jp in sources._jobpostings_from_jsonld(page):
        vt = sources._d(jp.get("validThrough"))
        if vt and vt < date.today().isoformat():
            return f"closed:validThrough {vt}"
    if re.search(r"(no longer (available|accepting)|position (has been )?(filled|closed)|annonsen (är|har) (inte längre|tagits bort)|job not found)", page, re.I):
        return "closed:page says the posting is closed"
    return "live"


def verify(home):
    cfg = home.search_config()
    today = date.today().isoformat()
    rows = [r for r in tr.read_all_rows(home.path("tracker")) if tr.status_bucket(r.get("Status")) == "active"]
    updates, counts = [], {"checked": 0, "live": 0, "expired": 0, "unknown": 0, "skipped": 0, "noted_approved": 0}
    for r in rows:
        dl = tr.to_date(r.get("Deadline"))
        res = f"closed:deadline {dl.isoformat()} passed" if dl and dl.isoformat() < today else check(r.get("URL"))
        if res == "skip":
            counts["skipped"] += 1
            continue
        counts["checked"] += 1
        kind, _, why = res.partition(":")
        if kind == "live":
            counts["live"] += 1
            continue
        row = dict(r)
        if kind == "closed":
            if str(r.get("Status") or "").startswith("Approved"):
                row["Notes"] = f'{r.get("Notes") or ""} | {today}: looks closed ({why}), kept because accepted'.strip(" |")
                counts["noted_approved"] += 1
            else:
                row["Status"] = "Expired"
                row["Notes"] = f'{r.get("Notes") or ""} | {today}: expired ({why})'.strip(" |")
                counts["expired"] += 1
        else:
            counts["unknown"] += 1
            note = f"{today}: could not verify ({why})"
            if note in str(r.get("Notes") or ""):
                continue
            row["Notes"] = f'{r.get("Notes") or ""} | {note}'.strip(" |")
        updates.append(row)
    if counts["unknown"] >= 3 and counts["live"] == 0 and counts["expired"] == 0:
        print("network appears to be unavailable: no posting could be checked, nothing changed")
        updates = [u for u in updates if u.get("Status") == "Expired"]
    if updates:
        tr.update(home.path("tracker"), updates, seniority_cfg=cfg.get("seniority"),
                  act_asap_after_days=int(cfg.get("act_asap_after_days", 7)))
    print(f"verified {counts['checked']} posting(s): {counts['live']} live, {counts['expired']} expired, "
          f"{counts['unknown']} could not be checked, {counts['skipped']} left for the agent"
          + (f", {counts['noted_approved']} accepted posting(s) look closed" if counts["noted_approved"] else ""))
    return counts
