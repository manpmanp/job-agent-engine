# Job-search agent engine
# File:    engine/collect/sources.py
# Purpose: Posting sources: Arbetsformedlingen JobSearch API, Greenhouse, Lever, Ashby, Workday, SmartRecruiters, generic career pages.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.2.0
# Date:    2026-10-28

"""
Every source returns a list of *candidates* (plain dicts) and an error
string or None. A candidate:

    {"title", "employer", "location_text", "url", "apply_url", "published",
     "deadline", "description", "is_remote", "workplace", "employment_type",
     "skills", "source"}

Only public, documented job-posting endpoints are called. Sites that do not
allow automated access (LinkedIn, Indeed) are not collected here; the AI
agent covers them read-only through its own tools.
"""
import json
import re
import urllib.parse
from datetime import date, datetime, timedelta, timezone

from . import http
from .match import strip_html

JOBTECH_SEARCH = "https://jobsearch.api.jobtechdev.se/search"
JOBTECH_AD = "https://jobsearch.api.jobtechdev.se/ad/"


def _d(s):
    """ISO-ish date or epoch ms -> 'YYYY-MM-DD' or ''."""
    if s in (None, ""):
        return ""
    if isinstance(s, (int, float)):
        return datetime.fromtimestamp(s / 1000 if s > 1e11 else s, timezone.utc).date().isoformat()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(s))
    return m.group(1) if m else ""


# --------------------------------------------------------------- JobTech / AF
def jobtech(keywords, max_per_keyword=200):
    """Arbetsformedlingen Platsbanken via the open JobSearch API (no key)."""
    out, errors = [], []
    for kw in keywords:
        offset = 0
        while offset < max_per_keyword:
            q = urllib.parse.urlencode({"q": kw, "limit": 100, "offset": offset})
            r, data = http.get_json(f"{JOBTECH_SEARCH}?{q}")
            if data is None:
                errors.append(f"JobSearch '{kw}': {r.error or 'HTTP ' + str(r.status)}")
                break
            hits = data.get("hits", []) or []
            for h in hits:
                if h.get("removed"):
                    continue
                wa = h.get("workplace_address") or {}
                loc = ", ".join(x for x in (wa.get("city"), wa.get("municipality"), wa.get("region"), wa.get("country")) if x)
                desc = (h.get("description") or {}).get("text") or ""
                model = ((h.get("workplace_model") or {}).get("label") or "")
                skills = [s.get("label") for s in ((h.get("must_have") or {}).get("skills") or []) if s.get("label")]
                out.append({
                    "title": h.get("headline") or "", "employer": (h.get("employer") or {}).get("name") or "",
                    "location_text": loc, "url": h.get("webpage_url") or "",
                    "apply_url": (h.get("application_details") or {}).get("url") or "",
                    "published": _d(h.get("publication_date")), "deadline": _d(h.get("application_deadline")),
                    "description": desc, "is_remote": "distans" in model.lower() or "remote" in model.lower(),
                    "workplace": model, "employment_type": ((h.get("employment_type") or {}).get("label") or ""),
                    "skills": skills, "source": "Arbetsformedlingen (JobSearch API)", "source_id": h.get("id"),
                })
            total = ((data.get("total") or {}).get("value")) or 0
            offset += 100
            if offset >= total or not hits:
                break
    return out, ("; ".join(errors) or None)


def jobtech_ad_status(ad_id):
    """'live' | 'removed' | 'unknown'"""
    r, data = http.get_json(JOBTECH_AD + urllib.parse.quote(str(ad_id)))
    if r.status in (404, 410):
        return "removed"
    if data is None:
        return "unknown"
    return "removed" if data.get("removed") else "live"


# ------------------------------------------------------------- ATS detection
def detect_ats(url, explicit=None):
    """Returns (kind, params) for a careers URL, e.g. ('greenhouse', {'board': 'x'})."""
    if explicit:
        return explicit.get("type"), explicit
    if not url or url.startswith(("indeed:", "linkedin:")) or "linkedin.com" in url or "indeed." in url:
        return "agent_only", {}
    p = urllib.parse.urlsplit(url)
    host, parts = p.netloc.lower(), [x for x in p.path.split("/") if x]
    if host.endswith("greenhouse.io") and parts:
        return "greenhouse", {"board": parts[0]}
    if host == "jobs.lever.co" and parts:
        return "lever", {"company": parts[0]}
    if host == "jobs.ashbyhq.com" and parts:
        return "ashby", {"org": parts[0]}
    if host.endswith("myworkdayjobs.com"):
        site = [x for x in parts if not re.match(r"^[a-z]{2}-[A-Z]{2}$", x) and x not in ("job", "wday", "cxs")]
        if site:
            return "workday", {"host": host, "tenant": host.split(".")[0], "site": site[0]}
    if host in ("jobs.smartrecruiters.com", "careers.smartrecruiters.com") and parts:
        return "smartrecruiters", {"company": parts[0]}
    return "html", {"url": url}


def greenhouse(board, employer):
    r, data = http.get_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true")
    if data is None:
        return [], f"Greenhouse '{board}': {r.error or 'HTTP ' + str(r.status)}"
    out = []
    for j in data.get("jobs", []) or []:
        loc = (j.get("location") or {}).get("name") or ""
        locs = [loc] + [o.get("location") or o.get("name") or "" for o in (j.get("offices") or [])]
        locs = list(dict.fromkeys(x for x in locs if x))
        out.append({"title": j.get("title") or "", "employer": employer, "location_text": "; ".join(locs),
                    "url": j.get("absolute_url") or "", "apply_url": j.get("absolute_url") or "",
                    "published": _d(j.get("first_published") or j.get("updated_at")), "deadline": "",
                    "description": strip_html(j.get("content")), "is_remote": "remote" in loc.lower(),
                    "workplace": "", "employment_type": "", "skills": [], "source": "Greenhouse job board"})
    return out, None


def lever(company, employer):
    r, data = http.get_json(f"https://api.lever.co/v0/postings/{company}?mode=json")
    if data is None:
        return [], f"Lever '{company}': {r.error or 'HTTP ' + str(r.status)}"
    out = []
    for j in data if isinstance(data, list) else []:
        c = j.get("categories") or {}
        locs = c.get("allLocations") or [c.get("location") or ""]
        out.append({"title": j.get("text") or "", "employer": employer, "location_text": "; ".join(x for x in locs if x),
                    "url": j.get("hostedUrl") or "", "apply_url": j.get("applyUrl") or "",
                    "published": _d(j.get("createdAt")), "deadline": "",
                    "description": j.get("descriptionPlain") or strip_html(j.get("description")),
                    "is_remote": str(j.get("workplaceType") or "").lower() == "remote",
                    "workplace": str(j.get("workplaceType") or ""), "employment_type": c.get("commitment") or "",
                    "skills": [], "source": "Lever job board"})
    return out, None


def ashby(org, employer):
    r, data = http.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{org}")
    if data is None:
        return [], f"Ashby '{org}': {r.error or 'HTTP ' + str(r.status)}"
    out = []
    for j in data.get("jobs", []) or []:
        if j.get("isListed") is False:
            continue
        locs = [j.get("location") or ""] + [s.get("location") or "" for s in (j.get("secondaryLocations") or [])]
        out.append({"title": j.get("title") or "", "employer": employer, "location_text": "; ".join(x for x in locs if x),
                    "url": j.get("jobUrl") or "", "apply_url": j.get("applyUrl") or "",
                    "published": _d(j.get("publishedAt")), "deadline": "",
                    "description": j.get("descriptionPlain") or strip_html(j.get("descriptionHtml")),
                    "is_remote": bool(j.get("isRemote")), "workplace": j.get("workplaceType") or "",
                    "employment_type": j.get("employmentType") or "", "skills": [], "source": "Ashby job board"})
    return out, None


def _workday_posted(s):
    s = str(s or "").lower()
    today = date.today()
    if "today" in s:
        return today.isoformat()
    if "yesterday" in s:
        return (today - timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\+?\s*day", s)
    if m and "+" not in s:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    return ""


def workday(host, tenant, site, employer, keywords):
    out, errors, seen = [], [], set()
    api = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    for kw in keywords:
        offset = 0
        while offset < 100:
            r, data = http.post_json(api, {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": kw})
            if data is None:
                errors.append(f"Workday '{tenant}/{site}' '{kw}': {r.error or 'HTTP ' + str(r.status)}")
                break
            posts = data.get("jobPostings", []) or []
            for j in posts:
                path = j.get("externalPath") or ""
                if not path or path in seen:
                    continue
                seen.add(path)
                out.append({"title": j.get("title") or "", "employer": employer, "location_text": j.get("locationsText") or "",
                            "url": f"https://{host}/{site}{path}", "apply_url": f"https://{host}/{site}{path}",
                            "published": _workday_posted(j.get("postedOn")), "deadline": "",
                            "description": "", "is_remote": False, "workplace": "", "employment_type": "",
                            "skills": [], "source": "Workday career site", "posted_text": j.get("postedOn") or ""})
            offset += 20
            if offset >= (data.get("total") or 0) or not posts:
                break
    return out, ("; ".join(errors) or None)


def smartrecruiters(company, employer):
    out, offset = [], 0
    while offset < 500:
        r, data = http.get_json(f"https://api.smartrecruiters.com/v1/companies/{company}/postings?limit=100&offset={offset}")
        if data is None:
            return out, f"SmartRecruiters '{company}': {r.error or 'HTTP ' + str(r.status)}"
        items = data.get("content", []) or []
        for j in items:
            loc = j.get("location") or {}
            lt = ", ".join(x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x)
            out.append({"title": j.get("name") or "", "employer": employer, "location_text": lt,
                        "url": f"https://jobs.smartrecruiters.com/{company}/{j.get('id')}", "apply_url": "",
                        "published": _d(j.get("releasedDate")), "deadline": "", "description": "",
                        "is_remote": bool(loc.get("remote")), "workplace": "", "employment_type": "",
                        "skills": [], "source": "SmartRecruiters"})
        offset += 100
        if offset >= (data.get("totalFound") or 0) or not items:
            break
    return out, None


# ------------------------------------------------------------ generic pages
JSONLD_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>', re.I)
ANCHOR_RE = re.compile(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>([\s\S]*?)</a>', re.I)


def _jobpostings_from_jsonld(page_html):
    found = []

    def walk(o):
        if isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            t = o.get("@type")
            if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
                found.append(o)
            for k in ("@graph", "itemListElement", "item"):
                if k in o:
                    walk(o[k])
    for block in JSONLD_RE.findall(page_html):
        try:
            walk(json.loads(block.strip()))
        except ValueError:
            continue
    return found


def _jsonld_location(jp):
    locs = jp.get("jobLocation") or []
    locs = locs if isinstance(locs, list) else [locs]
    parts = []
    for l in locs:
        a = (l or {}).get("address") or {}
        if isinstance(a, str):
            parts.append(a)
        else:
            parts.append(", ".join(x for x in (a.get("addressLocality"), a.get("addressRegion"), a.get("addressCountry") if isinstance(a.get("addressCountry"), str) else (a.get("addressCountry") or {}).get("name")) if x))
    return "; ".join(p for p in parts if p)


def html_page(url, employer, keywords):
    """Career page without a known API. JSON-LD JobPosting data is used when
    present; otherwise links whose text matches a keyword become leads
    marked for confirmation."""
    r = http.get_page(url)
    if not r.ok:
        return [], f"{employer} page: {r.error or 'HTTP ' + str(r.status)}"
    page = r.text()
    out = []
    for jp in _jobpostings_from_jsonld(page):
        org = jp.get("hiringOrganization") or {}
        out.append({"title": jp.get("title") or "", "employer": (org.get("name") if isinstance(org, dict) else "") or employer,
                    "location_text": _jsonld_location(jp), "url": jp.get("url") or url, "apply_url": "",
                    "published": _d(jp.get("datePosted")), "deadline": _d(jp.get("validThrough")),
                    "description": strip_html(jp.get("description")),
                    "is_remote": str(jp.get("jobLocationType") or "").upper() == "TELECOMMUTE",
                    "workplace": "", "employment_type": str(jp.get("employmentType") or ""), "skills": [],
                    "source": "Career page (structured data)"})
    if out:
        return out, None
    from .match import match_keywords
    seen = set()
    for href, text in ANCHOR_RE.findall(page):
        label = strip_html(text)
        if not label or len(label) > 160:
            continue
        hit, _ = match_keywords(label, "", keywords, scope="title")
        if not hit:
            continue
        full = urllib.parse.urljoin(r.url or url, href)
        if full in seen:
            continue
        seen.add(full)
        out.append({"title": label, "employer": employer, "location_text": "", "url": full, "apply_url": "",
                    "published": "", "deadline": "", "description": "", "is_remote": False, "workplace": "",
                    "employment_type": "", "skills": [], "source": "Career page (link, unconfirmed)", "lead": True})
    return out, None
