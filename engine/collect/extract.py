# Job-search agent engine
# File:    engine/collect/extract.py
# Purpose: Reads one job posting page: structured JobPosting data, else the page's main text, else a browser render.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
# Date:    2026-10-28

"""
fetch_posting(url) -> dict with title, employer, location_text, deadline,
published, employment_type, salary, is_remote, description, text, how, url,
complete, error.

Order, from cheapest to most expensive:

1. "structured": the schema.org JobPosting most job sites embed for search
   engines (JSON-LD; an object, a list or an @graph; descriptions that arrive
   as escaped HTML are unescaped twice).
2. "page": the page's main text (<main>, <article>, [role=main], else
   <body>) with navigation, headers, footers, forms and scripts removed;
   block elements on their own lines, list items as "- ".
3. "browser": when the page has less than MIN_CHARS of text it was most
   likely built in the browser. If a headless browser is available it is
   rendered and read again, waiting for the load event and a quiet network
   (at most 2 requests in flight for 0.5 s), because client-rendered pages
   read too early come back blank. Playwright is used when installed,
   otherwise Chrome/Chromium with --dump-dom.

The method of steps 1-2 follows Dossier's posting fetch
(github.com/AienTech/dossier, AGPL-3.0); the wait rule of step 3 follows
PixelRAG's renderer (github.com/StarTrail-org/PixelRAG, Apache-2.0). Both are
reimplemented here; no code was copied.

Page text is third-party data: it is stored and shown, never followed as
instructions.
"""
import html as _html
import json
import os
import re
import shutil
import subprocess
from html.parser import HTMLParser

from . import http

MIN_CHARS = 200
MAX_TEXT = 60_000
BROWSER_TIMEOUT = 45

JSONLD_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>', re.I)

BLOCK = {"p", "div", "section", "article", "main", "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6",
         "tr", "table", "br", "hr", "dl", "dt", "dd", "blockquote", "pre", "header", "footer"}
NOISE = {"script", "style", "noscript", "template", "svg", "nav", "header", "footer", "aside", "form",
         "iframe", "button", "select", "dialog"}
VOID = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}


# ----------------------------------------------------------- HTML -> text
class _Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.children, self.parent = tag, dict(attrs or {}), [], parent


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root")
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = _Node(tag, attrs, self.cur)
        self.cur.children.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(_Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def _parse(page):
    t = _Tree()
    try:
        t.feed(page or "")
        t.close()
    except Exception:  # malformed markup: use what was parsed
        pass
    return t.root


def _find(node, pred):
    for c in node.children:
        if isinstance(c, _Node):
            if pred(c):
                return c
            hit = _find(c, pred)
            if hit is not None:
                return hit
    return None


def _text_of(node, drop_noise=True):
    lines, line = [], []

    def flush():
        s = re.sub(r"\s+", " ", "".join(line)).strip()
        if s:
            lines.append(s)
        line.clear()

    def walk(n):
        if isinstance(n, str):
            line.append(n)
            return
        if drop_noise and n.tag in NOISE:
            return
        block = n.tag in BLOCK
        if block:
            flush()
        if n.tag == "li":
            line.append("- ")
        for c in n.children:
            walk(c)
        if block:
            flush()

    walk(node)
    flush()
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def html_to_text(fragment):
    """Readable text from HTML, also from HTML that arrives escaped
    (&lt;p&gt;...), as in many JSON-LD descriptions."""
    text = _text_of(_parse(str(fragment or "")), drop_noise=False)
    if re.search(r"</?(p|li|ul|br|div|strong)\b", text, re.I):
        text = _text_of(_parse(_html.unescape(text)), drop_noise=False)
    return text


def main_text(page):
    root = _parse(page)
    for pred in (lambda n: n.tag == "main", lambda n: n.tag == "article",
                 lambda n: n.attrs.get("role") == "main", lambda n: n.tag == "body"):
        hit = _find(root, pred)
        if hit is not None:
            t = _text_of(hit)
            if len(t) >= MIN_CHARS or hit.tag == "body":
                return t
    return _text_of(root)


# ------------------------------------------------------- JSON-LD postings
def jobpostings(page):
    found = []

    def walk(o):
        if isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            t = o.get("@type")
            if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
                found.append(o)
            for k in ("@graph", "itemListElement", "item", "mainEntity"):
                if k in o:
                    walk(o[k])
    for block in JSONLD_RE.findall(page or ""):
        try:
            walk(json.loads(block.strip()))
        except ValueError:
            try:  # some sites put raw newlines or trailing commas in JSON-LD
                walk(json.loads(re.sub(r",\s*([}\]])", r"\1", block.strip().replace("\n", " "))))
            except ValueError:
                continue
    return found


def _s(v):
    return v.strip() if isinstance(v, str) else (str(v) if isinstance(v, (int, float)) else "")


def _name(v):
    return _s(v) or (_s(v.get("name")) if isinstance(v, dict) else "")


def jsonld_location(jp):
    locs = jp.get("jobLocation") or []
    out = []
    for l in (locs if isinstance(locs, list) else [locs]):
        a = (l or {}).get("address") if isinstance(l, dict) else None
        if isinstance(a, str):
            out.append(a.strip())
        elif isinstance(a, dict):
            out.append(", ".join(x for x in (_s(a.get("addressLocality")), _s(a.get("addressRegion")),
                                             _name(a.get("addressCountry"))) if x))
    seen = []
    for x in out:
        if x and x not in seen:
            seen.append(x)
    return "; ".join(seen)


def salary_of(v):
    """'EUR 75000-90000 per year' from a schema.org MonetaryAmount."""
    if not isinstance(v, dict):
        return _s(v)
    amt = v.get("value") if isinstance(v.get("value"), dict) else {}
    rng = "-".join(x for x in (_s(amt.get("minValue")), _s(amt.get("maxValue"))) if x) or _s(amt.get("value")) or _s(v.get("value"))
    if not rng:
        return ""
    unit = _s(amt.get("unitText")).lower()
    return " ".join(x for x in (_s(v.get("currency")), rng, f"per {unit}" if unit else "") if x)


def _date(v):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", _s(v))
    return m.group(1) if m else ""


def from_jobposting(jp, fallback_url=""):
    et = jp.get("employmentType")
    et = ", ".join(_s(x) for x in et) if isinstance(et, list) else _s(et)
    remote = "TELECOMMUTE" in json.dumps(jp.get("jobLocationType") or "").upper()
    return {
        "title": _s(jp.get("title")), "employer": _name(jp.get("hiringOrganization")),
        "location_text": jsonld_location(jp) or ("Remote" if remote else ""),
        "url": _s(jp.get("url")) or fallback_url,
        "published": _date(jp.get("datePosted")), "deadline": _date(jp.get("validThrough")),
        "employment_type": et.lower().replace("_", " "), "salary": salary_of(jp.get("baseSalary")),
        "is_remote": remote, "description": html_to_text(_s(jp.get("description")))[:MAX_TEXT],
    }


# ---------------------------------------------------------------- browser
def browser_available():
    try:
        import playwright.sync_api  # noqa: F401
        return "playwright"
    except Exception:
        pass
    return "chrome" if _chrome() else None


def _chrome():
    for c in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        p = shutil.which(c)
        if p:
            return p
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    return mac if os.path.exists(mac) else None


def render_dom(url, timeout=BROWSER_TIMEOUT):
    """The page's HTML after client-side rendering, or (None, error).
    Playwright: load event + network idle. Chrome: --dump-dom with a
    virtual time budget, which lets scripts and requests settle."""
    if not http.robots_allowed(url):
        return None, "disallowed by robots.txt"
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            try:
                pg = b.new_page(user_agent=http.USER_AGENT)
                pg.goto(url, wait_until="load", timeout=timeout * 1000)
                try:
                    pg.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass  # long-polling pages never go quiet; use what is there
                return pg.content(), None
            finally:
                b.close()
    except ImportError:
        pass
    except Exception as e:
        return None, f"browser render failed: {type(e).__name__}: {e}"
    chrome = _chrome()
    if not chrome:
        return None, "no headless browser (install Playwright or Chrome)"
    try:
        r = subprocess.run([chrome, "--headless", "--disable-gpu", "--no-first-run", f"--user-agent={http.USER_AGENT}",
                            "--virtual-time-budget=15000", "--dump-dom", url],
                           capture_output=True, timeout=timeout)
        if r.returncode == 0 and r.stdout:
            return r.stdout.decode("utf-8", errors="replace"), None
        return None, f"browser render failed (exit {r.returncode})"
    except Exception as e:
        return None, f"browser render failed: {type(e).__name__}: {e}"


# ---------------------------------------------------------------- posting
def read_html(page, url=""):
    """Posting fields from a page's HTML (steps 1-2)."""
    for jp in jobpostings(page):
        d = from_jobposting(jp, url)
        if len(d["description"]) >= MIN_CHARS or d["title"]:
            d["how"] = "structured"
            d["text"] = posting_text(d)
            d["complete"] = len(d["description"]) >= MIN_CHARS
            return d
    text = main_text(page)[:MAX_TEXT]
    title = ""
    m = re.search(r"<title[^>]*>([\s\S]*?)</title>", page or "", re.I)
    if m:
        title = re.sub(r"\s+", " ", _html.unescape(m.group(1))).strip()
    d = {"title": title, "employer": "", "location_text": "", "url": url, "published": "", "deadline": "",
         "employment_type": "", "salary": "", "is_remote": False, "description": text, "how": "page",
         "complete": len(text) >= MIN_CHARS}
    d["text"] = text
    return d


def posting_text(d):
    """The posting as a person would paste it: employer and title, facts, then the description."""
    facts = [x for x in (d.get("location_text"), "Remote" if d.get("is_remote") and "remote" not in str(d.get("location_text")).lower() else "",
                         d.get("employment_type"), d.get("salary"),
                         f"Apply by {d['deadline']}" if d.get("deadline") else "") if x]
    head = ": ".join(x for x in (d.get("employer"), d.get("title")) if x)
    return "\n\n".join(x for x in (head, " | ".join(facts), d.get("description")) if x)


def fetch_posting(url, render=True):
    """Fetches and reads one posting page. Never raises."""
    r = http.get_page(url)
    if not r.ok:
        return {"url": url, "complete": False, "how": "", "text": "", "description": "",
                "error": r.error or f"HTTP {r.status}", "status": r.status}
    ctype = (r.content_type or "").lower()
    if ctype and not re.search(r"text/html|application/xhtml\+xml|text/plain", ctype):
        return {"url": url, "complete": False, "how": "", "text": "", "description": "",
                "error": f"not a web page ({ctype.split(';')[0]})", "status": r.status}
    d = read_html(r.text(), r.url or url)
    d["status"], d["error"] = r.status, None
    if not d["complete"] and render and browser_available():
        dom, err = render_dom(r.url or url)
        if dom:
            d2 = read_html(dom, r.url or url)
            if len(d2.get("description", "")) > len(d.get("description", "")):
                d2["how"] = "browser+" + d2["how"]
                d2["status"], d2["error"] = r.status, None
                d = d2
        elif err:
            d["render_error"] = err
    if not d["complete"]:
        d["error"] = ("no posting text on the page: it is probably built in the browser"
                      + ("" if browser_available() else "; install Playwright or Chrome to render it")
                      if not d.get("render_error") else d["render_error"])
    return d
