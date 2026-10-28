# Job-search agent engine
# File:    engine/collect/sources.py
# Purpose: Posting sources: Arbetsformedlingen JobSearch API, Greenhouse, Lever, Ashby, Workday, SmartRecruiters, generic career pages.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
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
from . import extract

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


_DEADLINE_TEXT = re.compile(
    r"(?:posting end date|application deadline|last (?:day|date) to apply|last application date|apply (?:no later than|by)|"
    r"sista ans[oö]kningsdag(?:en)?|sista dag (?:att|f[oö]r att) s[oö]ka|ans[oö]k senast)\s*(?:is|[aä]r)?\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})",
    re.I)


def stated_deadline(text):
    """The deadline the posting text itself states ('Posting End Date
    2026-11-12', 'Sista ansökningsdag: 2026-11-30'), or ''. ATS end dates
    can differ by a day from what the employer wrote (time zones,
    exclusive end dates), so the stated date is preferred."""
    m = _DEADLINE_TEXT.search(str(text or ""))
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
                loc = ", ".join(dict.fromkeys(x for x in (wa.get("city"), wa.get("municipality"), wa.get("region"), wa.get("country")) if x))
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
                            "skills": [], "source": "Workday career site", "posted_text": j.get("postedOn") or "",
                            "_wd_host": host, "_wd_tenant": tenant, "_wd_site": site, "_wd_path": path})
            offset += 20
            if offset >= (data.get("total") or 0) or not posts:
                break
    return out, ("; ".join(errors) or None)


def workday_details(c):
    """Fills description and posted date of one Workday candidate from its
    job-detail endpoint. Returns an error string or None."""
    host, tenant, site, path = c.get("_wd_host"), c.get("_wd_tenant"), c.get("_wd_site"), c.get("_wd_path")
    if not (host and tenant and site and path):
        return None
    r, data = http.get_json(f"https://{host}/wday/cxs/{tenant}/{site}{path}")
    if data is None:
        return f"Workday details '{c.get('title')}': {r.error or 'HTTP ' + str(r.status)}"
    info = data.get("jobPostingInfo") or {}
    c["description"] = strip_html(info.get("jobDescription") or "")
    c["published"] = c.get("published") or _d(info.get("startDate") or info.get("postedOn"))
    c["deadline"] = c.get("deadline") or _d(info.get("endDate"))
    c["workplace"] = info.get("remoteType") or c.get("workplace") or ""
    if info.get("location") and not c.get("location_text"):
        c["location_text"] = info["location"]
    return None


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
ANCHOR_RE = re.compile(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>([\s\S]*?)</a>', re.I)
_jobpostings_from_jsonld = extract.jobpostings   # kept for older callers


def html_page(url, employer, keywords):
    """Career page without a known API. JSON-LD JobPosting data is used when
    present; otherwise links whose text matches a keyword become leads
    marked for confirmation."""
    r = http.get_page(url)
    if not r.ok:
        return [], f"{employer} page: {r.error or 'HTTP ' + str(r.status)}"
    page = r.text()
    out = []
    for jp in extract.jobpostings(page):
        d = extract.from_jobposting(jp, url)
        out.append({"title": d["title"], "employer": d["employer"] or employer, "location_text": d["location_text"],
                    "url": d["url"] or url, "apply_url": "", "published": d["published"], "deadline": d["deadline"],
                    "description": d["description"], "is_remote": d["is_remote"], "workplace": "",
                    "employment_type": d["employment_type"], "skills": [], "source": "Career page (structured data)"})
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


# ------------------------------------------------- confirming page leads
def confirm_lead(c):
    """Opens a link lead from a careers page and reads the posting
    (engine/collect/extract.py). Structured JobPosting data confirms it;
    page text fills the description but keeps it marked for confirmation.
    Returns an error string or None."""
    d = extract.fetch_posting(c["url"])
    if d.get("error") and not d.get("description"):
        return f"lead '{c.get('title')}': {d['error']}"
    c["description"] = d.get("description") or c.get("description") or ""
    for k_src, k_dst in (("location_text", "location_text"), ("published", "published"), ("deadline", "deadline"),
                         ("employment_type", "employment_type")):
        if d.get(k_src) and not c.get(k_dst):
            c[k_dst] = d[k_src]
    if d.get("is_remote"):
        c["is_remote"] = True
    if d.get("how", "").endswith("structured"):
        c["lead"] = False
        c["source"] = "Career page (posting page, structured data)"
        if d.get("title"):
            c["title"] = d["title"]
    elif d.get("complete"):
        c["source"] = "Career page (posting page text)"
    return None


# ------------------------------------------------- optional aggregators
# These need nothing from the candidate except search terms and places.
# JSearch and Adzuna need your own API key in inputs/secrets.json.

def _country(loc):
    return str((loc.get("country") if isinstance(loc, dict) else "") or "").strip().lower()


def _loc_name(loc):
    return loc.get("name") if isinstance(loc, dict) else str(loc)


JSEARCH_HOSTS = {
    "openwebninja": ("https://api.openwebninja.com/jsearch", lambda k: {"x-api-key": k}),
    "rapidapi": ("https://jsearch.p.rapidapi.com", lambda k: {"x-rapidapi-key": k, "x-rapidapi-host": "jsearch.p.rapidapi.com"}),
}


def _jsearch_link(j):
    """The employer's own apply link when there is one, else the publisher's."""
    opts = [o for o in (j.get("apply_options") or []) if isinstance(o, dict)]
    for o in opts:
        if o.get("is_direct") and str(o.get("apply_link") or "").startswith("http"):
            return o["apply_link"], True
    for v in (j.get("job_apply_link"), (opts[0].get("apply_link") if opts else None), j.get("job_google_link")):
        if str(v or "").startswith("http"):
            return v, False
    return "", False


def jsearch(keywords, locations, key, host="openwebninja", date_posted="month", max_pages=1):
    """Google for Jobs (LinkedIn, Indeed, company sites) through the JSearch
    API. One page = one request of your plan. Locations need a 'country'."""
    base, hdr = JSEARCH_HOSTS.get(host, JSEARCH_HOSTS["openwebninja"])
    out, errors, seen = [], [], set()
    for loc in locations:
        country = _country(loc)
        if not country:
            errors.append(f"JSearch: location '{_loc_name(loc)}' has no country, skipped")
            continue
        for kw in keywords:
            cursor = None
            for _ in range(max_pages):
                q = urllib.parse.urlencode({k: v for k, v in {"query": f"{kw} in {_loc_name(loc)}", "country": country,
                                                                "date_posted": date_posted, "cursor": cursor}.items() if v})
                r, data = http.get_json(f"{base}/search-v2?{q}", headers=hdr(key))
                if data is None:
                    errors.append(f"JSearch '{kw}' {_loc_name(loc)}: {r.error or 'HTTP ' + str(r.status)}")
                    if r.status in (401, 403, 429):
                        return out, "; ".join(errors)
                    break
                d = data.get("data") or {}
                for j in d.get("jobs") or []:
                    if not isinstance(j, dict) or not j.get("job_id") or j["job_id"] in seen:
                        continue
                    seen.add(j["job_id"])
                    link, direct = _jsearch_link(j)
                    place = str(j.get("job_location") or "").split("•")[0].strip() or ", ".join(
                        x for x in (j.get("job_city"), j.get("job_state"), j.get("job_country")) if x)
                    out.append({"title": j.get("job_title") or "", "employer": j.get("employer_name") or "",
                                "location_text": place, "url": link, "apply_url": "",
                                "published": _d(j.get("job_posted_at_datetime_utc") or j.get("job_posted_at_timestamp")),
                                "deadline": _d(j.get("job_offer_expiration_datetime_utc")),
                                "description": (j.get("job_description") or "")[:60000],
                                "is_remote": bool(j.get("job_is_remote")), "workplace": "",
                                "employment_type": str(j.get("job_employment_type") or "").lower(), "skills": [],
                                "source": f"JSearch (via {j.get('job_publisher') or 'Google for Jobs'}"
                                          f"{', employer link' if direct else ''})"})
                cursor = d.get("cursor")
                if not cursor:
                    break
    return out, ("; ".join(errors) or None)


ADZUNA_COUNTRIES = {"at", "au", "be", "br", "ca", "ch", "de", "es", "fr", "gb", "in", "it", "mx", "nl", "nz",
                    "pl", "sg", "us", "za"}


def adzuna(keywords, locations, app_id, app_key, max_days_old=30, distance_km=50):
    """Adzuna's job index. It only sends the start of each description; the
    rest is read from the posting page when it is accepted."""
    out, errors, seen = [], [], set()
    for loc in locations:
        country = _country(loc)
        if country == "uk":
            country = "gb"
        if country not in ADZUNA_COUNTRIES:
            errors.append(f"Adzuna does not cover '{_loc_name(loc)}' ({country or 'no country'})")
            continue
        for kw in keywords:
            q = urllib.parse.urlencode({"app_id": app_id, "app_key": app_key, "results_per_page": 50, "what": kw,
                                        "where": _loc_name(loc), "distance": distance_km, "max_days_old": max_days_old})
            r, data = http.get_json(f"https://api.adzuna.com/v1/api/jobs/{country}/search/1?{q}")
            if data is None:
                errors.append(f"Adzuna '{kw}' {_loc_name(loc)}: {r.error or 'HTTP ' + str(r.status)}")
                if r.status in (401, 403, 429):
                    return out, "; ".join(errors)
                continue
            for j in data.get("results") or []:
                jid = str(j.get("id") or "")
                if not jid or jid in seen:
                    continue
                seen.add(jid)
                out.append({"title": strip_html(j.get("title")), "employer": ((j.get("company") or {}).get("display_name") or ""),
                            "location_text": ((j.get("location") or {}).get("display_name") or ""),
                            "url": j.get("redirect_url") or "", "apply_url": "", "published": _d(j.get("created")),
                            "deadline": "", "description": strip_html(j.get("description")), "is_remote": False,
                            "workplace": "", "employment_type": str(j.get("contract_time") or ""), "skills": [],
                            "source": "Adzuna (description shortened by the source)"})
    return out, ("; ".join(errors) or None)


HN_API = "https://hacker-news.firebaseio.com/v0"
HN_ALGOLIA = "https://hn.algolia.com/api/v1"


def hn_item_link(i):
    return f"https://news.ycombinator.com/item?id={i}"


def _hn_title(title):
    """'Acme (YC W24) Is Hiring a Founding Engineer in Lund' in parts."""
    m = re.match(r"^(.+?)\s*\(\s*YC\s+([A-Z]\d{2})\s*\)\s*(.*)$", title or "", re.I)
    if m:
        company, rest = m.group(1).strip(), m.group(3).strip()
    else:
        m = re.match(r"^(.+?)\s+(?:is|are)\s+hiring\b(.*)$", title or "", re.I)
        company, rest = (m.group(1).strip(), "is hiring" + m.group(2)) if m else ((title or "").strip(), "")
    role = re.sub(r"^(?:is|are)\s+hiring\b[\s:\-\u2013\u2014]*", "", rest, flags=re.I)
    role = re.sub(r"^(?:an?|for)\s+", "", role, flags=re.I).strip()
    role = re.sub(r"\s+in\s+[A-Z][^()\[\]]*$", "", re.sub(r"\s*[(\[].*$", "", role)).strip()
    places = [a or b for a, b in re.findall(r"\(([^)]*)\)|\[([^\]]*)\]", rest)]
    m = re.search(r"\bin\s+([A-Z][^()\[\]]*)$", re.sub(r"\s*[(\[].*$", "", rest))
    if m:
        places.insert(0, m.group(1).strip())
    return company, role, " / ".join(p.strip() for p in places if p.strip())


def yc_jobs(limit=100):
    """YC companies' job posts on Hacker News (official HN API, no key)."""
    r, ids = http.get_json(f"{HN_API}/jobstories.json")
    if not isinstance(ids, list):
        return [], f"YC job posts: {r.error or 'HTTP ' + str(r.status)}"
    out = []
    for i in ids[:limit]:
        _, it = http.get_json(f"{HN_API}/item/{i}.json")
        if not isinstance(it, dict) or it.get("type") != "job" or it.get("dead") or it.get("deleted") or not it.get("title"):
            continue
        company, role, place = _hn_title(it["title"])
        url = it.get("url") if str(it.get("url") or "").startswith("http") else hn_item_link(i)
        out.append({"title": role or it["title"], "employer": company, "location_text": place, "url": url,
                    "apply_url": "", "published": _d(it.get("time")), "deadline": "",
                    "description": extract.html_to_text(it.get("text") or ""),
                    "is_remote": bool(re.search(r"\bremote\b", it["title"], re.I)), "workplace": "",
                    "employment_type": "", "skills": [], "source": "YC job post (Hacker News)",
                    "lead": not it.get("text")})
    return out, None


def _hn_header(text):
    first = (text or "").strip().split("\n", 1)[0]
    return [p.strip() for p in re.split(r"\s+\|\s+|\s+\u00b7\s+", first) if p.strip()]


def hn_who_is_hiring():
    """This month's 'Ask HN: Who is hiring?' posts (HN's public Algolia API,
    no key). Each top-level post is one employer; the first line is usually
    'Company | Role | Place | Remote'. Location filtering is done by the
    normal location match."""
    r, data = http.get_json(f"{HN_ALGOLIA}/search_by_date?tags=story,author_whoishiring&hitsPerPage=10")
    hits = (data or {}).get("hits") or []
    thread = next((h for h in hits if re.match(r"^ask hn: who is hiring\?", h.get("title") or "", re.I)), None)
    if not thread:
        return [], f"HN Who is hiring: {r.error or 'no thread found this month'}"
    r, t = http.get_json(f"{HN_ALGOLIA}/items/{thread['objectID']}")
    if not isinstance(t, dict):
        return [], f"HN Who is hiring: {r.error or 'HTTP ' + str(r.status)}"
    out = []
    for post in t.get("children") or []:
        if not isinstance(post, dict) or not post.get("text"):
            continue
        text = extract.html_to_text(post["text"])
        parts = _hn_header(text)
        if len(parts) < 2:
            continue
        company = re.sub(r"https?://\S+|\s*\(.*\)\s*$", "", parts[0]).strip(" -:")
        roles = [p for p in parts[1:] if re.search(r"\b(engineer|developer|architect|designer|scientist|researcher|"
                                                   r"lead|manager|intern|specialist)\b", p, re.I)]
        places = [p for p in parts[1:] if p not in roles]
        out.append({"title": " / ".join(roles) or parts[1], "employer": company,
                    "location_text": "; ".join(places), "url": hn_item_link(post.get("id")), "apply_url": "",
                    "published": _d(post.get("created_at")), "deadline": "", "description": text[:20000],
                    "is_remote": any(re.search(r"\bremote\b", p, re.I) for p in places), "workplace": "",
                    "employment_type": "", "skills": [], "source": "HN Who is hiring"})
    return out, None
