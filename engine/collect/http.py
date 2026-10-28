# Job-search agent engine
# File:    engine/collect/http.py
# Purpose: Polite HTTP client for collectors: identification, per-host delay, robots.txt, retries.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.3.0
# Date:    2026-10-28

"""
All network access of the engine goes through this module, so the rules are
in one place:

- identifies itself with a User-Agent naming the engine,
- waits at least DELAY seconds between requests to the same host,
- checks robots.txt before fetching ordinary web pages (not for documented
  public APIs, which exist to be called),
- retries once on timeouts and 5xx, never on 4xx,
- never raises to the caller: every call returns a Response with .ok,
  .status and .error, so one failing source never stops a run.

Tests replace `transport` with a function returning canned responses.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

from .. import __version__

USER_AGENT = f"job-agent-engine/{__version__} (personal job-search tool; reads public job postings)"
DELAY = 1.0
TIMEOUT = 25
RETRY_WAIT = 2

_last_hit = {}
_robots = {}


class Response:
    def __init__(self, status=0, body=b"", error=None, url=""):
        self.status, self.body, self.error, self.url = status, body, error, url

    @property
    def ok(self):
        return 200 <= self.status < 300 and self.error is None

    def text(self):
        return self.body.decode("utf-8", errors="replace") if isinstance(self.body, bytes) else str(self.body)

    def json(self):
        try:
            return json.loads(self.text())
        except ValueError:
            return None


def _urllib_transport(method, url, headers, data):
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return Response(r.status, r.read(), None, r.geturl())
    except urllib.error.HTTPError as e:
        return Response(e.code, e.read() if hasattr(e, "read") else b"", None, url)
    except Exception as e:  # network down, DNS, TLS, timeout
        return Response(0, b"", f"{type(e).__name__}: {e}", url)


transport = _urllib_transport


def _polite_wait(url):
    host = urllib.parse.urlsplit(url).netloc
    last = _last_hit.get(host)
    if last is not None:
        wait = DELAY - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
    _last_hit[host] = time.time()


def robots_allowed(url):
    parts = urllib.parse.urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    rp = _robots.get(base)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        r = request("GET", base + "/robots.txt", check_robots=False)
        if r.status == 200:
            rp.parse(r.text().splitlines())
        else:
            rp.parse([])  # no robots.txt, or unreachable: allowed
        _robots[base] = rp
    return rp.can_fetch(USER_AGENT, url)


def request(method, url, headers=None, body=None, check_robots=False):
    if check_robots and not robots_allowed(url):
        return Response(0, b"", "disallowed by robots.txt", url)
    h = {"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.9, */*;q=0.5"}
    h.update(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8") if not isinstance(body, (bytes, str)) else (body.encode() if isinstance(body, str) else body)
        h.setdefault("Content-Type", "application/json")
    for attempt in (1, 2):
        _polite_wait(url)
        r = transport(method, url, h, data)
        if r.error is None and r.status < 500:
            return r
        if attempt == 2:
            return r
        time.sleep(RETRY_WAIT)
    return r


def get_json(url, headers=None):
    r = request("GET", url, headers)
    return r, (r.json() if r.ok else None)


def post_json(url, body, headers=None):
    r = request("POST", url, headers, body)
    return r, (r.json() if r.ok else None)


def get_page(url):
    """Ordinary web page: robots.txt is respected."""
    return request("GET", url, {"Accept": "text/html,application/xhtml+xml"}, check_robots=True)
