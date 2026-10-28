# Job-search agent engine
# File:    engine/formserver.py
# Purpose: Local web server for the input forms: saves straight into the agent home and imports documents from the intake folders.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.3.0
# Date:    2026-10-28

"""
./run.sh --setup     (or ./run.sh form)

Serves forms/candidate_form.html on http://127.0.0.1:<port>/ and opens it
in the browser. Served this way, the form can:
- load and save inputs/search_config.json directly,
- load the current profile and submit the candidate form as an intake,
- list inputs/intake/cv and inputs/intake/cl and import new documents
  (the Update button).

Safety: the server listens on 127.0.0.1 only, accepts API calls only with a
random per-session token (so other web pages cannot call it), checks the
Host header, and stops with Ctrl+C. Nothing is sent anywhere else.
"""
import json
import os
import secrets
import tempfile
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from .home import REPO_DIR, _strip_help
from .profile import Intake

FORM = os.path.join(REPO_DIR, "forms", "candidate_form.html")
MAX_BODY = 2_000_000


def _make_handler(home, token, port_holder):
    intake = Intake(home)

    class Handler(BaseHTTPRequestHandler):
        server_version = "job-agent-form/1"

        def log_message(self, fmt, *a):  # keep the terminal quiet
            pass

        # ------------------------------------------------------- helpers
        def _host_ok(self):
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in ("127.0.0.1", "localhost")

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, indent=1).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", f"{ctype}; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self):
            return self._host_ok() and secrets.compare_digest(self.headers.get("X-Agent-Token", ""), token)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                raise ValueError("request too large")
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

        def _info(self):
            caps = home.capabilities()
            return {
                "home": home.root,
                "intake": intake.folder_listing(),
                "sources": [{k: e.get(k) for k in ("id", "kind", "submitted_at", "from_file", "note")}
                            for e in intake.sources()],
                "search_ready": caps["search"][0],
                "tailoring": "full" if caps["tailoring_full"][0] else "template",
            }

        # --------------------------------------------------------- routes
        def do_GET(self):
            if not self._host_ok():
                return self._send(403, {"error": "bad host"})
            if self.path in ("/", "/index.html"):
                with open(FORM, "r", encoding="utf-8") as f:
                    page = f.read()
                inject = f'<script>window.JOB_AGENT_API = {json.dumps({"token": token})};</script>\n</head>'
                return self._send(200, page.replace("</head>", inject, 1).encode("utf-8"), "text/html")
            if not self._authorized():
                return self._send(403, {"error": "missing or wrong token"})
            if self.path == "/api/info":
                return self._send(200, self._info())
            if self.path == "/api/search_config":
                p = home.path("search_config")
                data = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
                return self._send(200, _strip_help(data))
            if self.path == "/api/profile":
                return self._send(200, {k: v for k, v in home.profile().items() if not k.startswith("_")})
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._authorized():
                return self._send(403, {"error": "missing or wrong token"})
            try:
                body = self._body()
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            if self.path == "/api/search_config":
                p = home.path("search_config")
                current = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
                current.update({k: v for k, v in body.items() if not k.startswith("_")})
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(current, f, indent=2, ensure_ascii=False)
                return self._send(200, {"saved": p, "search_ready": home.capabilities()["search"][0]})
            if self.path == "/api/profile":
                fd, tmp = tempfile.mkstemp(prefix="profile_form_", suffix=".json")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(body, f, ensure_ascii=False)
                try:
                    intake.add_data("form", tmp)
                finally:
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
                conflicts = [c for c in json.load(open(intake.conflicts_path, encoding="utf-8")) if not c.get("resolved")] \
                    if os.path.exists(intake.conflicts_path) else []
                return self._send(200, {"saved": intake.profile_path, "open_conflicts": len(conflicts)})
            if self.path == "/api/intake/scan":
                res = intake.scan_intake_folders()
                return self._send(200, {"result": res, "info": self._info()})
            return self._send(404, {"error": "not found"})

    return Handler


def serve(home, port=8765, open_browser=True):
    token = secrets.token_urlsafe(24)
    httpd, chosen = None, None
    for p in range(port, port + 20):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", p), _make_handler(home, token, None))
            chosen = p
            break
        except OSError:
            continue
    if httpd is None:
        raise SystemExit(f"no free port between {port} and {port + 19}")
    url = f"http://127.0.0.1:{chosen}/"
    print(f"input forms for agent home {home.root}")
    print(f"open {url} (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
