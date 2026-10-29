# Job-search agent engine
# File:    engine/collect/http.py
# Purpose: Polite HTTP client for collectors: identification, per-host delay, robots.txt, retries.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
# Date:    2026-10-28

"""
All network access of the engine goes through this module, so the rules are
in one place:

- identifies itself with a User-Agent naming the engine,
- waits at least DELAY seconds between requests to the same host,
- checks robots.txt (RFC 9309) before fetching ordinary web pages (not for
  documented public APIs, which exist to be called): the longest matching
  rule wins, Allow wins a tie, '*' and a final '$' are supported; a missing
  file allows everything, while 401/403/429 or an unreachable site mean
  "not now"; answers are kept for a day,
- fetches pages only from public addresses (no localhost or private
  networks, also after redirects), at most MAX_BYTES, and decodes them in the
  charset the server names,
- retries once on timeouts and 5xx, never on 4xx,
- never raises to the caller: every call returns a Response with .ok,
  .status and .error, so one failing source never stops a run.

Tests replace `transport` with a function returning canned responses.
"""
import ipaddress
import os
import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from .. import __version__

USER_AGENT = f"job-agent-engine/{__version__} (personal job-search tool; reads public job postings)"
ROBOTS_TOKEN = "job-agent-engine"
DELAY = 1.0
TIMEOUT = 25
RETRY_WAIT = 2
MAX_BYTES = 4 * 1024 * 1024
ROBOTS_TTL = 24 * 3600

_last_hit = {}
_robots = {}


class Response:
    def __init__(self, status=0, body=b"", error=None, url="", content_type=""):
        self.status, self.body, self.error, self.url = status, body, error, url
        self.content_type = content_type

    @property
    def ok(self):
        return 200 <= self.status < 300 and self.error is None

    def text(self):
        if not isinstance(self.body, bytes):
            return str(self.body)
        m = re.search(r"charset=[\"']?([\w-]+)", self.content_type or "", re.I)
        try:
            return self.body.decode(m.group(1) if m else "utf-8", errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")

    def json(self):
        try:
            return json.loads(self.text())
        except ValueError:
            return None


def _ssl_context():
    """Certificates are checked against the operating system's trust store
    (macOS Keychain, Windows certificate store, Linux system CAs) through
    'truststore', the same store your browser uses. This also works on
    networks that inspect HTTPS with their own certificate (university or
    company networks, VPNs, antivirus) and in the packaged apps. Fallbacks:
    certifi's list, then Python's own. SSL_CERT_FILE is honoured as usual."""
    if os.environ.get("SSL_CERT_FILE"):
        return ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"]), "SSL_CERT_FILE"
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT), "system trust store"
    except Exception:
        pass
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where()), "certifi"
    except Exception:
        return ssl.create_default_context(), "python default"


SSL_CONTEXT, SSL_SOURCE = _ssl_context()


def _explain(e):
    msg = f"{type(e).__name__}: {e}"
    if "CERTIFICATE_VERIFY_FAILED" in msg:
        return (msg + " (the site's certificate is not trusted on this computer, checked against "
                f"{SSL_SOURCE}; if your network inspects HTTPS, its certificate must be trusted by the system)")
    return msg


def _urllib_transport(method, url, headers, data):
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=SSL_CONTEXT) as r:
            body = r.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                return Response(0, b"", f"response larger than {MAX_BYTES // 1024 // 1024} MB", r.geturl())
            return Response(r.status, body, None, r.geturl(), r.headers.get("Content-Type", ""))
    except urllib.error.HTTPError as e:
        return Response(e.code, e.read() if hasattr(e, "read") else b"", None, url)
    except Exception as e:  # network down, DNS, TLS, timeout
        return Response(0, b"", _explain(e), url)


transport = _urllib_transport


def _polite_wait(url):
    host = urllib.parse.urlsplit(url).netloc
    last = _last_hit.get(host)
    if last is not None:
        wait = DELAY - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
    _last_hit[host] = time.time()


# ------------------------------------------------------------- robots.txt
def parse_robots(text, token=ROBOTS_TOKEN):
    """Rules for `token`: the groups naming it, else the '*' groups
    (RFC 9309 2.2.1). Returns a list of (allow, pattern)."""
    groups, cur, last_agent = [], None, False
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        m = re.match(r"^([A-Za-z-]+)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1).lower(), m.group(2).strip()
        if key == "user-agent":
            if cur is None or not last_agent:
                cur = {"agents": [], "rules": []}
                groups.append(cur)
            cur["agents"].append(value.lower())
            last_agent = True
            continue
        last_agent = False
        if cur is not None and key in ("allow", "disallow") and value:
            cur["rules"].append((key == "allow", value))
    own = [g for g in groups if token.lower() in g["agents"]]
    chosen = own or [g for g in groups if "*" in g["agents"]]
    return [r for g in chosen for r in g["rules"]]


def _pattern(p):
    anchored = p.endswith("$")
    body = ".*".join(re.escape(x) for x in (p[:-1] if anchored else p).split("*"))
    return re.compile("^" + body + ("$" if anchored else ""))


def robots_allow(rules, path):
    """Longest matching rule wins, Allow on a tie (RFC 9309 2.2.2).
    rules: list of (allow, pattern), or "all" / "none"."""
    if rules == "all" or path == "/robots.txt":
        return True
    if rules == "none":
        return False
    best = None
    for allow, pat in rules:
        if _pattern(pat).match(path):
            if best is None or len(pat) > len(best[1]) or (len(pat) == len(best[1]) and allow):
                best = (allow, pat)
    return True if best is None else best[0]


def robots_allowed(url):
    parts = urllib.parse.urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    known = _robots.get(base)
    if known is None or time.time() - known[1] > ROBOTS_TTL:
        r = request("GET", base + "/robots.txt", check_robots=False)
        if r.ok:
            rules = parse_robots(r.text())
        elif 400 <= r.status < 500 and r.status not in (401, 403, 429):
            rules = "all"   # no robots.txt: nothing is off limits
        else:
            rules = "none"  # refused, failing or unreachable: not now
        _robots[base] = (rules, time.time())
        known = _robots[base]
    return robots_allow(known[0], (parts.path or "/") + (("?" + parts.query) if parts.query else ""))


# -------------------------------------------------------- public addresses
def is_public_host(host):
    """False for localhost, private, link-local and reserved addresses, and
    for names that resolve to one. Pages are only fetched from public hosts."""
    host = (host or "").strip("[]").rstrip(".").lower()
    if not host or host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        addrs = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            addrs = [ipaddress.ip_address(a[4][0].split("%")[0]) for a in socket.getaddrinfo(host, None)]
        except (socket.gaierror, UnicodeError, ValueError):
            return True  # unresolvable here: the request itself will fail
    return all(a.is_global and not a.is_multicast for a in addrs)


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
    """Ordinary web page: public hosts only, robots.txt is respected."""
    parts = urllib.parse.urlsplit(url or "")
    if parts.scheme not in ("http", "https") or parts.username or parts.password:
        return Response(0, b"", "not a web address", url)
    if transport is _urllib_transport and not is_public_host(parts.hostname):
        return Response(0, b"", "address on a private or local network, not fetched", url)
    r = request("GET", url, {"Accept": "text/html,application/xhtml+xml"}, check_robots=True)
    if r.url and r.url != url and transport is _urllib_transport and not is_public_host(urllib.parse.urlsplit(r.url).hostname):
        return Response(0, b"", "redirected to a private or local network, not fetched", r.url)
    return r
