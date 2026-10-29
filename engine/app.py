# Job-search agent engine
# File:    engine/app.py
# Purpose: The local app: one browser interface for every operation (status, search, postings, documents, setup, schedule).
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
# Date:    2026-10-28

"""
Started by the launchers (launchers/start.py, or the double-click files) or with
'./run.sh app'. Serves engine/web/app.html on http://127.0.0.1:<port>/ and the
search-setup and profile form on /form.

Safety: listens on 127.0.0.1 only, accepts API calls only with a random
per-session token injected into the page (other web pages cannot call it),
checks the Host header, serves files only from the agent home's output
folder, and runs one background job at a time so the tracker is never
written twice at once.

Long operations (search, fetch, templates, AI drafts) run as background
jobs; their output is streamed to the page. Engine commands run as
separate processes ('python -m engine.cli ...'), exactly as in the terminal.
"""
import base64
import io
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from datetime import date, datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit, parse_qs

from . import __version__, decisions, documents, tracker as tr, schedule as sched
from .home import REPO_DIR, WEB_DIR, DEFAULTS_DIR, _strip_help
from .profile import Intake

APP_HTML = os.path.join(WEB_DIR, "app.html")
FORM = os.path.join(WEB_DIR, "form.html")
MAX_BODY = 25_000_000
UPLOAD_EXT = {".pdf", ".docx", ".txt", ".md"}
SECRET_KEYS = ("anthropic_api_key", "jsearch_api_key", "jsearch_host", "adzuna_app_id", "adzuna_app_key")


# --------------------------------------------------------------- jobs
class Jobs:
    """One background job at a time; its output lines are kept for the page."""

    def __init__(self):
        self.lock = threading.Lock()
        self.current = None
        self.n = 0

    def busy(self):
        return bool(self.current and not self.current["done"])

    def _new(self, label):
        self.n += 1
        self.current = {"id": self.n, "label": label, "lines": [], "done": False, "ok": None,
                        "started": datetime.now().isoformat(timespec="seconds"), "result": None}
        return self.current

    def run_cli(self, home, label, args, after=None):
        with self.lock:
            if self.busy():
                return None
            job = self._new(label)
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--cli", "--home", home.root] + args
        else:
            cmd = [sys.executable, "-m", "engine.cli", "--home", home.root] + args
        env = dict(os.environ, PYTHONPATH=REPO_DIR + os.pathsep + os.environ.get("PYTHONPATH", ""),
                   PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")

        def work():
            try:
                p = subprocess.Popen(cmd, cwd=REPO_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace")
                for line in p.stdout:
                    job["lines"].append(line.rstrip("\n"))
                job["ok"] = p.wait() == 0
            except Exception as e:
                job["lines"].append(f"could not start: {e}")
                job["ok"] = False
            if after:
                try:
                    after(job)
                except Exception as e:
                    job["lines"].append(f"[after] {e}")
            job["done"] = True
        threading.Thread(target=work, daemon=True).start()
        return job

    def run_fn(self, label, fn):
        """fn(log) -> result; log(str) appends a line."""
        with self.lock:
            if self.busy():
                return None
            job = self._new(label)

        def work():
            try:
                job["result"] = fn(lambda s: job["lines"].append(str(s)))
                job["ok"] = True
            except Exception as e:
                job["lines"].append(f"failed: {type(e).__name__}: {e}")
                job["ok"] = False
            job["done"] = True
        threading.Thread(target=work, daemon=True).start()
        return job


# ------------------------------------------------------------- helpers
def _read_json(p, default):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write_json(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def _iso(v):
    d = tr.to_date(v)
    return d.isoformat() if d else (str(v) if v not in (None, "") else "")


def _secrets_path(home):
    return os.path.join(home.path("inputs"), "secrets.json")


def _open_in_os(path):
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    elif os.name == "nt":
        os.startfile(path)  # noqa: S606 (local file chosen by the app)
    else:
        subprocess.Popen(["xdg-open", path])


def _docs_for(home, row):
    names = documents.filenames_for(row)
    out = []
    for kind, folder in (("cv", "cv_out"), ("cl", "cl_out"), ("jd", "jd_out")):
        base = os.path.splitext(names[kind])[0]
        for prefix in ("", "TEMPLATE_"):
            for ext in (".docx", ".md", ".pdf", ".html"):
                p = os.path.join(home.path(folder), prefix + base + ext)
                if os.path.exists(p):
                    out.append({"kind": kind, "template": bool(prefix), "name": os.path.basename(p),
                                "rel": os.path.relpath(p, home.root)})
    return out


def _last_notes(home, n=14):
    """The latest run entries of the notes file ('=== date ===' blocks), newest first."""
    p = home.path("notes")
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return []
    blocks = re.split(r"\n(?==== \d{4}-\d{2}-\d{2} ===)", text)[1:]
    out = []
    for b in reversed(blocks):
        for line in b.strip().splitlines():
            if line.strip():
                out.append(line.rstrip())
        if len(out) >= n:
            break
    return out[:n]


# -------------------------------------------------------------- server
def _make_handler(home, token, jobs, httpd_ref):
    intake = Intake(home)

    class Handler(BaseHTTPRequestHandler):
        server_version = "job-agent-app/1"

        def log_message(self, fmt, *a):
            pass

        # ---------------------------------------------------- plumbing
        def _host_ok(self):
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in ("127.0.0.1", "localhost")

        def _send(self, code, body, ctype="application/json", extra=None):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(code)
            if "charset" not in ctype and (ctype.startswith("text/") or ctype == "application/json"):
                ctype += "; charset=utf-8"
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self, query=None):
            t = self.headers.get("X-Agent-Token", "") or ((query or {}).get("t") or [""])[0]
            return self._host_ok() and secrets.compare_digest(t, token)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                raise ValueError("request too large")
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

        def _page(self, path, extra_js=""):
            with open(path, "r", encoding="utf-8") as f:
                page = f.read()
            inject = (f'<script>window.JOB_AGENT_API = {json.dumps({"token": token})};{extra_js}</script>\n</head>')
            return self._send(200, page.replace("</head>", inject, 1).encode("utf-8"), "text/html; charset=utf-8",
                              {"Content-Security-Policy": "default-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'self'"})

        # ---------------------------------------------------- data
        def _status(self):
            caps = home.capabilities()
            rows = tr.read_all_rows(home.path("tracker"))
            active = [r for r in rows if tr.status_bucket(r.get("Status")) == "active"]
            pending = decisions.approved_pending(home)
            new = [r for r in active if not str(r.get("Status") or "").startswith(("Approved", "Rejected"))]
            on, sdesc = sched.status(home)
            from . import ai_docs, cloud_sync
            return {
                "cloud": cloud_sync.settings(home),
                "version": __version__, "home": home.root, "today": date.today().isoformat(),
                "capabilities": {k: {"on": v[0], "why": v[1]} for k, v in caps.items()},
                "counts": {"active": len(active), "undecided": len(new), "accepted_waiting": len(pending),
                           "rejected": sum(1 for r in rows if tr.status_bucket(r.get("Status")) == "rejected"),
                           "expired": sum(1 for r in rows if tr.status_bucket(r.get("Status")) == "expired")},
                "schedule": {"on": on, "text": sdesc},
                "api_key": bool(ai_docs.api_key(home)),
                "awaiting_extraction": [{"id": e["id"], "file": e.get("from_file") or e.get("original")}
                                        for e in ai_docs.awaiting_extraction(home)],
                "open_conflicts": [dict(c, n=i + 1) for i, c in enumerate(_read_json(intake.conflicts_path, []) or [])
                                   if not c.get("resolved")],
                "recent": _last_notes(home),
                "job": jobs.current,
                "search_day": (home.search_config().get("weekly_list") or {}).get("full_search_day", "Monday"),
            }

        def _postings(self):
            cfg = home.search_config()
            from . import conventions
            cat = conventions.catalogue(home)
            picks = conventions.choices(home)

            def written_for(r):
                try:
                    c = conventions.for_row(home, r, cfg, cat, picks)
                    return {"summary": conventions.summary(c), "type": c["type"], "market": c["market"],
                            "auto_type": c["auto"]["type"], "auto_market": c["auto"]["market"]}
                except Exception:
                    return None
            out = []
            for r in tr.read_all_rows(home.path("tracker")):
                key = f"{r.get('URL') or ''}||{r.get('Title') or ''}"
                announce = tr.to_date(r.get("Announce Date"))
                from .webpage import compute_action
                out.append({
                    "key": key, "title": r.get("Title") or "", "employer": r.get("Employer") or "",
                    "location": r.get("Location") or "", "category": r.get("Category") or "",
                    "seniority": r.get("Seniority Level") or "", "senior_bucket": tr.seniority_bucket(r.get("Seniority Level"), cfg.get("seniority")),
                    "announced": _iso(r.get("Announce Date")), "deadline": _iso(r.get("Deadline")),
                    "found": _iso(r.get("Date Found")), "arrangement": r.get("Remote/Hybrid/Onsite") or "",
                    "skills": r.get("Required Skills (summary)") or "", "url": r.get("URL") or "",
                    "status": r.get("Status") or "", "bucket": tr.status_bucket(r.get("Status")),
                    "notes": r.get("Notes") or "", "drafted": str(r.get("CV/Cover Letter Drafted (Y/N)") or "N").upper() == "Y",
                    "urgent": compute_action(r.get("Deadline"), announce, int(cfg.get("act_asap_after_days", 7))),
                    "docs": _docs_for(home, r), "written_for": written_for(r),
                })
            reasons = cfg.get("rejection_reasons") or []
            return {"postings": out, "rejection_reasons": reasons}

        def _row(self, key):
            for r in tr.read_all_rows(home.path("tracker")):
                if f"{r.get('URL') or ''}||{r.get('Title') or ''}" == key:
                    return r
            return None

        def _decide(self, body):
            key, d = body.get("key") or "", body.get("decision")
            row = self._row(key)
            if row is None:
                return 404, {"error": "posting not found"}
            if jobs.busy():
                return 409, {"error": "a job is running; try again when it has finished"}
            path = home.path("decisions")
            data = _read_json(path, {}) or {}
            ts = datetime.now().isoformat(timespec="seconds")
            if d == "undo":
                data.pop(key, None)
                _write_json(path, data)
                latest = os.path.join(home.path("sync_logs"), "latest_state.json")
                st = _read_json(latest, {}) or {}
                if key in st:
                    st.pop(key)
                    _write_json(latest, st)
                r = dict(row, Status="New")
                r["Notes"] = f'{row.get("Notes") or ""} | Decision undone in the app ({ts})'.strip(" |")
                tr.update(home.path("tracker"), [r], seniority_cfg=home.search_config().get("seniority"))
                return 200, {"ok": True}
            if d not in ("accepted", "rejected"):
                return 400, {"error": "decision must be accepted, rejected or undo"}
            entry = {"decision": d, "ts": ts}
            if d == "rejected":
                entry["reasons"] = [str(x) for x in (body.get("reasons") or [])] or ["Not specified"]
                entry["note"] = str(body.get("note") or "")[:500]
            data[key] = entry
            _write_json(path, data)
            buf = io.StringIO()
            from contextlib import redirect_stdout
            with redirect_stdout(buf):
                decisions.apply(home, seniority_cfg=home.search_config().get("seniority"))
            return 200, {"ok": True, "log": buf.getvalue().strip()}

        def _settings_get(self):
            sec = _read_json(_secrets_path(home), {}) or {}
            cfg = home.search_config()
            return {"secrets": {k: bool(sec.get(k)) for k in SECRET_KEYS},
                    "jsearch_host": sec.get("jsearch_host") or "openwebninja",
                    "sources": cfg.get("sources") or {}, "enrichment": cfg.get("enrichment") or {},
                    "documents": cfg.get("documents") or {}}

        def _settings_post(self, body):
            sec = _read_json(_secrets_path(home), {}) or {}
            for k, v in (body.get("secrets") or {}).items():
                if k in SECRET_KEYS:
                    if v is None or v == "":
                        continue
                    if v == "__clear__":
                        sec.pop(k, None)
                    else:
                        sec[k] = str(v).strip()
            _write_json(_secrets_path(home), sec)
            try:
                os.chmod(_secrets_path(home), 0o600)
            except OSError:
                pass
            p = home.path("search_config")
            cur = _read_json(p, {}) or {}
            for k in ("sources", "enrichment", "documents"):
                if isinstance(body.get(k), dict):
                    merged = dict(cur.get(k) or home.search_config().get(k) or {})
                    merged.update(body[k])
                    cur[k] = merged
            _write_json(p, cur)
            return self._settings_get()

        def _upload(self, body):
            kind = body.get("kind") if body.get("kind") in ("cv", "cl") else "cv"
            name = os.path.basename(str(body.get("name") or "document"))
            name = re.sub(r"[^\w.\- ]", "_", name)[:120]
            if os.path.splitext(name)[1].lower() not in UPLOAD_EXT:
                return 400, {"error": "only .pdf, .docx, .txt or .md files"}
            raw = base64.b64decode(body.get("data") or "")
            folder = home.path("intake_cv" if kind == "cv" else "intake_cl")
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, name), "wb") as f:
                f.write(raw)
            res = intake.scan_intake_folders()
            return 200, {"result": res}

        # ---------------------------------------------------- routes
        def do_GET(self):
            if not self._host_ok():
                return self._send(403, {"error": "bad host"})
            u = urlsplit(self.path)
            q = parse_qs(u.query)
            if u.path in ("/", "/index.html"):
                return self._page(APP_HTML)
            if u.path == "/form":
                return self._page(FORM, "window.JOB_AGENT_EMBEDDED = true;")
            if u.path == "/api/ping":
                return self._send(200, {"app": "job-agent-engine", "home": home.root})
            if u.path == "/file":
                if not self._authorized(q):
                    return self._send(403, {"error": "missing or wrong token"})
                rel = (q.get("p") or [""])[0]
                full = os.path.realpath(os.path.join(home.root, rel))
                out_root = os.path.realpath(os.path.join(home.root, "output"))
                if not full.startswith(out_root + os.sep) or not os.path.isfile(full):
                    return self._send(404, {"error": "not found"})
                with open(full, "rb") as f:
                    data = f.read()
                ext = os.path.splitext(full)[1].lower()
                ctype = {".pdf": "application/pdf", ".html": "text/html; charset=utf-8", ".md": "text/plain; charset=utf-8",
                         ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}.get(ext, "application/octet-stream")
                disp = "inline" if ext in (".pdf", ".md") else "attachment"
                return self._send(200, data, ctype, {"Content-Disposition": f'{disp}; filename="{os.path.basename(full)}"'})
            if not self._authorized(q):
                return self._send(403, {"error": "missing or wrong token"})
            if u.path == "/api/status":
                return self._send(200, self._status())
            if u.path == "/api/postings":
                return self._send(200, self._postings())
            if u.path == "/api/job":
                return self._send(200, {"job": jobs.current})
            if u.path == "/api/settings":
                return self._send(200, self._settings_get())
            if u.path == "/api/employers":
                return self._send(200, _read_json(home.path("employers"), {"mode": "extend", "employers": []}) or {})
            if u.path == "/api/writing":
                from . import conventions
                return self._send(200, conventions.editor_data(home))
            if u.path == "/api/job_sites":
                return self._send(200, _read_json(os.path.join(DEFAULTS_DIR, "job_sites.json"), {}) or {})
            if u.path == "/api/cloud":
                from . import cloud_sync
                return self._send(200, cloud_sync.settings(home))
            if u.path == "/api/documents/prompt":
                from . import ai_docs
                row = self._row((q.get("key") or [""])[0])
                if row is None:
                    return self._send(404, {"error": "posting not found"})
                return self._send(200, {"prompt": ai_docs.tailor_prompt(home, row)})
            if u.path == "/api/profile/prompt":
                from . import ai_docs
                sid = (q.get("id") or [""])[0]
                e = next((x for x in ai_docs.awaiting_extraction(home) if x["id"] == sid), None)
                if e is None:
                    return self._send(404, {"error": "document not found"})
                return self._send(200, {"prompt": ai_docs.profile_prompt(home, ai_docs.source_text(home, e), e.get("kind", "cv").upper())})
            # used by the input form
            if u.path == "/api/info":
                caps = home.capabilities()
                return self._send(200, {"home": home.root, "intake": intake.folder_listing(),
                                        "sources": [{k: e.get(k) for k in ("id", "kind", "submitted_at", "from_file", "note")}
                                                    for e in intake.sources()],
                                        "search_ready": caps["search"][0],
                                        "tailoring": "full" if caps["tailoring_full"][0] else "template"})
            if u.path == "/api/search_config":
                return self._send(200, _strip_help(_read_json(home.path("search_config"), {}) or {}))
            if u.path == "/api/profile":
                return self._send(200, {k: v for k, v in home.profile().items() if not k.startswith("_")})
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._authorized():
                return self._send(403, {"error": "missing or wrong token"})
            try:
                body = self._body()
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            u = urlsplit(self.path)
            p = u.path
            busy = lambda: self._send(409, {"error": "another job is running"})
            if p == "/api/decision":
                code, res = self._decide(body)
                return self._send(code, res)
            if p == "/api/employers":
                emps = []
                for e in body.get("employers") or []:
                    name = str((e or {}).get("name") or "").strip()[:120]
                    urls = [str(x).strip() for x in (e.get("urls") or []) if re.match(r"^(https?://|indeed:|linkedin:)", str(x).strip())][:5]
                    if name:
                        emps.append({"name": name, "urls": urls})
                cur = _read_json(home.path("employers"), {}) or {}
                cur.update({"mode": cur.get("mode") or "extend", "employers": emps})
                _write_json(home.path("employers"), {k: v for k, v in cur.items() if not k.startswith("_")})
                from . import cloud_sync
                if cloud_sync.connected(home):   # the online search uses the same list
                    url, hdr = cloud_sync._auth(home)
                    from .collect import http as _h
                    _h.post_json(f"{url}/api/sync/config", {"employers": {"mode": "override", "employers": emps}}, headers=hdr)
                return self._send(200, {"saved": len(emps)})
            if p == "/api/cloud":
                from . import cloud_sync
                try:
                    return self._send(200, cloud_sync.configure(home, body.get("url"), body.get("token")))
                except ValueError as e:
                    return self._send(400, {"error": str(e)})
            if p == "/api/cloud/pull":
                job = jobs.run_cli(home, "Fetch from your online search", ["cloud", "pull"])
                return self._send(200, {"job": job}) if job else busy()
            if p == "/api/run":
                from . import cloud_sync
                if cloud_sync.connected(home):
                    ok, msg = cloud_sync.start_search(home)
                    job = jobs.run_cli(home, "Search online and fetch", ["cloud", "pull"])
                    if job:
                        job["lines"].append(msg)
                    return self._send(200, {"job": job}) if job else busy()
                mode = body.get("mode") if body.get("mode") in ("weekly", "daily", "auto") else "weekly"
                job = jobs.run_cli(home, {"weekly": "Search now", "daily": "Refresh", "auto": "Today's run"}[mode], ["run", mode])
                return self._send(200, {"job": job}) if job else busy()
            if p == "/api/verify":
                job = jobs.run_cli(home, "Check postings are open", ["verify"])
                return self._send(200, {"job": job}) if job else busy()
            if p == "/api/fetch":
                url = str(body.get("url") or "").strip()
                if not re.match(r"^https?://", url):
                    return self._send(400, {"error": "give a web address starting with http:// or https://"})
                args = ["fetch", url] + (["--add"] if body.get("add", True) else [])
                for k in ("employer", "title"):
                    if body.get(k):
                        args += [f"--{k}", str(body[k])]
                job = jobs.run_cli(home, "Add a posting", args)
                return self._send(200, {"job": job}) if job else busy()
            if p == "/api/documents/template":
                row = self._row(body.get("key") or "")
                if row is None:
                    return self._send(404, {"error": "posting not found"})
                job = jobs.run_cli(home, "Template documents", ["tailor", "template", body["key"]])
                return self._send(200, {"job": job}) if job else busy()
            if p == "/api/documents/ai":
                from . import ai_docs
                row = self._row(body.get("key") or "")
                if row is None:
                    return self._send(404, {"error": "posting not found"})

                def work(log):
                    log(f"writing documents for {row.get('Employer')}: {row.get('Title')} with {ai_docs._model(home)} ...")
                    ans = ai_docs.ask(home, ai_docs.tailor_prompt(home, row))
                    res = ai_docs.apply_tailor_answer(home, row, ans)
                    for x in res["problems"]:
                        log(f"problem: {x}")
                    for f in res["files"]:
                        log(f"wrote {f}")
                    if res["report"]:
                        log("report: " + res["report"])
                    if res["problems"] and not res["files"]:
                        raise RuntimeError("the draft did not pass the checks; nothing was written")
                    return res
                job = jobs.run_fn("AI draft", work)
                return self._send(200, {"job": job}) if job else busy()
            if p == "/api/documents/answer":
                from . import ai_docs
                row = self._row(body.get("key") or "")
                if row is None:
                    return self._send(404, {"error": "posting not found"})
                try:
                    res = ai_docs.apply_tailor_answer(home, row, body.get("answer") or "")
                except ValueError as e:
                    return self._send(400, {"error": f"could not read the answer: {e}"})
                return self._send(200, res)
            if p == "/api/profile/ai":
                from . import ai_docs
                e = next((x for x in ai_docs.awaiting_extraction(home) if x["id"] == body.get("id")), None)
                if e is None:
                    return self._send(404, {"error": "document not found"})

                def work(log):
                    log(f"reading {e.get('from_file') or e['id']} into your profile ...")
                    ans = ai_docs.ask(home, ai_docs.profile_prompt(home, ai_docs.source_text(home, e), e.get("kind", "cv").upper()), 8000)
                    ai_docs.apply_profile_answer(home, ans, e["id"])
                    log("profile updated")
                job = jobs.run_fn("Read CV into profile", work)
                return self._send(200, {"job": job}) if job else busy()
            if p == "/api/profile/answer":
                from . import ai_docs
                try:
                    ai_docs.apply_profile_answer(home, body.get("answer") or "", body.get("id"))
                except ValueError as e:
                    return self._send(400, {"error": f"could not read the answer: {e}"})
                return self._send(200, {"ok": True})
            if p == "/api/conflicts/resolve":
                if body.get("choice") not in ("keep-new", "keep-previous"):
                    return self._send(400, {"error": "choice must be keep-new or keep-previous"})
                try:
                    intake.resolve(int(body.get("n")), body.get("choice"))
                except Exception as e:
                    return self._send(400, {"error": str(e)})
                return self._send(200, {"ok": True})
            if p == "/api/intake/upload":
                code, res = self._upload(body)
                return self._send(code, res)
            if p == "/api/settings":
                return self._send(200, self._settings_post(body))
            if p == "/api/writing":
                from . import conventions
                try:
                    return self._send(200, conventions.save_type(home, str(body.get("type") or ""), body.get("data")))
                except (ValueError, TypeError) as e:
                    return self._send(400, {"error": str(e)})
            if p == "/api/writing/posting":
                from . import conventions
                row = self._row(body.get("key") or "")
                if row is None:
                    return self._send(404, {"error": "posting not found"})
                conventions.set_choice(home, body["key"], body.get("type") or None, body.get("market") or None)
                c = conventions.for_row(home, row)
                return self._send(200, {"summary": conventions.summary(c), "type": c["type"], "market": c["market"]})
            if p == "/api/schedule":
                ok, msg = (sched.install if body.get("on") else sched.remove)(home)
                on, desc = sched.status(home)
                return self._send(200 if ok else 500, {"ok": ok, "message": msg, "on": on, "text": desc})
            if p == "/api/open":
                rel = str(body.get("rel") or "output")
                full = os.path.realpath(os.path.join(home.root, rel))
                if not full.startswith(os.path.realpath(home.root)):
                    return self._send(403, {"error": "outside the agent home"})
                _open_in_os(full if os.path.exists(full) else home.root)
                return self._send(200, {"ok": True})
            if p == "/api/quit":
                threading.Thread(target=lambda: (time.sleep(0.3), httpd_ref[0].shutdown()), daemon=True).start()
                return self._send(200, {"ok": True})
            # used by the input form
            if p == "/api/search_config":
                path = home.path("search_config")
                current = _read_json(path, {}) or {}
                current.update({k: v for k, v in body.items() if not k.startswith("_")})
                _write_json(path, current)
                return self._send(200, {"saved": path, "search_ready": home.capabilities()["search"][0]})
            if p == "/api/profile":
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
                conflicts = [c for c in _read_json(intake.conflicts_path, []) if not c.get("resolved")]
                return self._send(200, {"saved": intake.profile_path, "open_conflicts": len(conflicts)})
            if p == "/api/intake/scan":
                return self._send(200, {"result": intake.scan_intake_folders(), "info": None})
            return self._send(404, {"error": "not found"})

    return Handler


def find_running(port_from=8765, span=20, home_root=None):
    """Port of an app already running on this machine for this agent home
    (any home when home_root is None), or None. An app for another folder
    is left alone; the new one takes the next free port."""
    import urllib.request
    want = os.path.realpath(home_root) if home_root else None
    for p in range(port_from, port_from + span):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{p}/api/ping", timeout=0.4) as r:
                info = json.loads(r.read().decode())
                if info.get("app") == "job-agent-engine" and (want is None or os.path.realpath(info.get("home") or "") == want):
                    return p
        except Exception:
            continue
    return None


def serve(home, port=8765, open_browser=True, path="/"):
    token = secrets.token_urlsafe(24)
    jobs = Jobs()
    ref = [None]
    httpd, chosen = None, None
    for p in range(port, port + 20):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", p), _make_handler(home, token, jobs, ref))
            chosen = p
            break
        except OSError:
            continue
    if httpd is None:
        raise SystemExit(f"no free port between {port} and {port + 19}")
    ref[0] = httpd
    sched.refresh(home)
    url = f"http://127.0.0.1:{chosen}{path}"
    print(f"Job agent is running for {home.root}")
    print(f"Open {url}  (keep this window open; close it or press Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        print("stopped")
