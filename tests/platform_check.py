#!/usr/bin/env python3
# Job-search agent engine
# File:    tests/platform_check.py
# Purpose: Drives a real Job Agent (packaged app or source folder) through the app's API on this system and writes what it saw, so macOS, Windows and Linux can be compared side by side.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.5
# Date:    2026-10-29

"""
    python tests/platform_check.py --mode app --cmd '["dist/JobAgent.exe"]' --out platform-windows-app.json

Starts Job Agent on a copy of the fictional demo folder, then, through the
same API the page uses: reads status, postings, job sites, writing style,
network log and the update and uninstall plans; saves job sites and a
per-posting writing type; makes template documents in a background job
(a child process, as when you click the button); switches the daily run on
and off (launchd, Task Scheduler or cron); and closes the page to check
that the app stops by itself. Everything that does not depend on the system
(paths, times, the token) is left out of the result file, so the files of
the three systems must be equal; tests/platform_compare.py checks that.
"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def kill_tree(proc):
    """The source launcher runs the app in a child process: stop both."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        import signal
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except OSError:
            proc.kill()


def call(base, token, path, body=None, tab=""):
    req = urllib.request.Request(base + path, method="GET" if body is None else "POST",
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"X-Agent-Token": token, "X-Agent-Tab": tab, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:         # an answer with an error code still has a JSON body
        raw = e.read()
    return json.loads(raw.decode() or "{}") if raw else {}


def wait_job(base, token, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        job = call(base, token, "/api/job").get("job") or {}
        if job.get("done"):
            return job
        time.sleep(1)
    raise SystemExit("job did not finish")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", required=True, help="JSON list: how to start Job Agent")
    ap.add_argument("--mode", required=True, choices=["app", "source"])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cmd = json.loads(a.cmd)

    home = os.path.join(tempfile.mkdtemp(prefix="jae-platform-"), "home")
    demo = os.path.join(ROOT, "docs", "demo", "home")
    if not os.path.isdir(demo):                # the fictional demo folder is built, not stored
        subprocess.run([sys.executable, "-m", "engine.cli", "demo"], cwd=ROOT, check=True, capture_output=True)
    shutil.copytree(demo, home)
    log = open(os.path.join(os.path.dirname(home), "app.log"), "w")
    port = free_port()
    proc = subprocess.Popen(cmd + ["--home", home, "--cli", "app", "--no-browser", "--port", str(port)],
                            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, **({} if os.name == "nt" else {"start_new_session": True}))
    base = f"http://127.0.0.1:{port}"
    for _ in range(240):                       # the first start of a source folder installs its packages
        try:
            with urllib.request.urlopen(base + "/api/ping", timeout=2) as r:
                info = json.loads(r.read().decode())
            if os.path.realpath(info.get("home") or "") != os.path.realpath(home):
                raise SystemExit(f"another Job Agent answers on port {port}")
            break
        except Exception:
            if proc.poll() is not None:
                raise SystemExit("Job Agent exited at start:\n" + open(log.name).read())
            time.sleep(1)
    page = urllib.request.urlopen(base + "/", timeout=10).read().decode()
    token = re.search(r'"token":\s*"([^"]+)"', page).group(1)
    out = {"mode": a.mode, "system": platform.system()}

    try:
        st = call(base, token, "/api/status")
        out["status"] = {"counts": st["counts"], "capabilities": {k: bool(v.get("on")) for k, v in st["capabilities"].items()},
                         "version": st.get("version")}
        posts = call(base, token, "/api/postings")["postings"]
        out["postings"] = sorted([p["title"], p["employer"], p["bucket"], (p.get("written_for") or {}).get("type"),
                                  (p.get("written_for") or {}).get("market"), len(p.get("docs") or [])] for p in posts)
        sites = call(base, token, "/api/job_sites")
        out["job_sites"] = {"countries": len(sites["countries"]), "sites": sum(len(c["sites"]) for c in sites["countries"].values())}
        call(base, token, "/api/search_config", {"job_sites": {"countries": ["SE", "DK"], "skip": [], "custom": []}})
        out["job_sites_saved"] = call(base, token, "/api/search_config").get("job_sites")
        w = call(base, token, "/api/writing")
        out["writing_types"] = sorted(w["types"])
        acc = [p for p in posts if p["status"].startswith("Approved")]
        if acc:
            r = call(base, token, "/api/writing/posting", {"key": acc[0]["key"], "type": "postdoc", "market": "us"})
            out["writing_choice"] = r["summary"]
            call(base, token, "/api/writing/posting", {"key": acc[0]["key"]})
            job = call(base, token, "/api/documents/template", {"key": acc[0]["key"]})["job"]
            done = wait_job(base, token)
            out["template_job"] = {"ok": done.get("ok"), "made": sorted(re.sub(r"_[0-9]+\.", ".", os.path.basename(l.strip()))
                                                                        for l in done.get("lines", []) if l.strip().endswith((".docx", ".md")))}
            files = sorted(os.listdir(os.path.join(home, "output", "CV")))
            out["cv_files"] = files
        out["reset_parts"] = [p["key"] for p in call(base, token, "/api/reset")["parts"]]
        plan = " | ".join(call(base, token, "/api/uninstall")["plan"])
        out["uninstall_plan"] = {"daily_runs": "daily run" in plan, "settings_file": "settings file" in plan,
                                 "program": "the app:" in plan or "private Python" in plan, "keeps_your_folder": "kept: your job-search folder" in plan}
        out["network_ok"] = "summary" in call(base, token, "/api/network")
        on = call(base, token, "/api/schedule", {"on": True})
        off = call(base, token, "/api/schedule", {"on": False})
        out["schedule"] = {"on": [on.get("ok"), on.get("on")], "off": [off.get("ok"), off.get("on")],
                           "message_on": on.get("message", "").split(",")[0]}
        # Close the page: the app must stop by itself, a few seconds later.
        call(base, token, "/api/alive", {}, tab="page1")
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/bye?t={token}&tab=page1", data=b"", method="POST"), timeout=10)
        t0 = time.time()
        stopped = False
        while time.time() - t0 < 40:            # the app (child of the launcher in a source folder) no longer answers
            try:
                urllib.request.urlopen(base + "/api/ping", timeout=2).read()
                time.sleep(0.5)
            except Exception:
                stopped = True
                break
        for _ in range(20):                     # and its process ends
            if proc.poll() is not None:
                break
            time.sleep(0.5)
        out["stops_after_tab_closed"] = stopped and proc.poll() is not None
    finally:
        kill_tree(proc)
        log.close()
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False, sort_keys=True)
    print(json.dumps(out, indent=1, ensure_ascii=False, sort_keys=True))
    if not out.get("stops_after_tab_closed") or not (out.get("template_job") or {}).get("ok", True):
        print("app log:\n" + open(log.name, encoding="utf-8", errors="replace").read())
        sys.exit(1)


if __name__ == "__main__":
    main()
