# Job-search agent engine
# File:    engine/maintenance.py
# Purpose: Update and uninstall, the same way on macOS, Windows and Linux, for the packaged apps and for a source folder.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.5
# Date:    2026-10-29

"""
Update
    packaged app: reads the newest release on GitHub, downloads the file for
    this system (dmg, Setup.exe or tar.gz), installs it over the current app
    and starts the new one. Source folder: 'git pull' (the launchers install
    changed packages on the next start).

Uninstall
    removes every daily run Job Agent installed (launchd, cron, Task
    Scheduler; for all job-search folders), the launcher's settings file
    (~/.job-agent-engine.json), the source folder's private Python (.venv)
    and the headless browser it installed, and the app itself (macOS: the
    .app bundle; Linux: ~/.local/bin/job-agent and its menu entry; Windows:
    the installer's own uninstaller). Your job-search folder is only removed
    when you ask for it. The source folder itself is only removed with
    remove_engine.

Both are used by the app (Settings > Update and uninstall), by
'./run.sh update' and './run.sh uninstall', and by the update/uninstall
shortcuts each package ships.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

from . import __version__
from .collect import http
from .home import REPO_DIR

REPO = "manpmanp/job-agent-engine"
LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSETS = {"darwin": "JobAgent-macOS.dmg", "win32": "JobAgent-Windows-Setup.exe", "linux": "JobAgent-Linux.tar.gz"}
SETTINGS = os.path.join(os.path.expanduser("~"), ".job-agent-engine.json")
DEFAULT_HOME = os.path.join(os.path.expanduser("~"), "JobAgent")
LINUX_BIN = os.path.join(os.path.expanduser("~"), ".local", "bin", "job-agent")
LINUX_DESKTOP = os.path.join(os.path.expanduser("~"), ".local", "share", "applications", "job-agent.desktop")


# ------------------------------------------------------------------ where am I
def platform_key():
    return "darwin" if sys.platform == "darwin" else "win32" if os.name == "nt" else "linux"


def kind():
    """'app' for the packaged apps, 'source' for a folder run with run.sh or the launchers."""
    return "app" if getattr(sys, "frozen", False) else "source"


def app_location():
    """The installed app: the .app bundle (macOS), the program folder
    (Windows) or the program file (Linux); None for a source folder."""
    if kind() != "app":
        return None
    exe = os.path.realpath(sys.executable)
    if platform_key() == "darwin":
        m = re.search(r"^(.*?\.app)/Contents/MacOS/", exe)
        return m.group(1) if m else exe
    if platform_key() == "win32":
        return os.path.dirname(exe)
    return exe


def _origin():
    r = subprocess.run(["git", "-C", REPO_DIR, "remote", "get-url", "origin"], capture_output=True, text=True)
    url = (r.stdout or "").strip()
    return re.sub(r"^git@github\.com:", "https://github.com/", url) or f"https://github.com/{REPO}"


def _after_exit_windows(cmd_line):
    """cmd line that waits about 3 seconds (until this app has closed) and then runs cmd_line."""
    return ["cmd", "/c", f"ping -n 4 127.0.0.1 >nul & {cmd_line}"]


def _version_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3]) or (0,)


def homes(extra=None):
    """Job-search folders this computer knows of."""
    out = []
    try:
        with open(SETTINGS, "r", encoding="utf-8") as f:
            h = (json.load(f) or {}).get("home")
            if h:
                out.append(h)
    except (OSError, ValueError):
        pass
    for h in (extra, DEFAULT_HOME, os.path.join(REPO_DIR, "my_agent") if kind() == "source" else None):
        if h and os.path.isdir(h):
            out.append(h)
    seen, res = set(), []
    for h in out:
        r = os.path.realpath(os.path.expanduser(h))
        if r not in seen:
            seen.add(r)
            res.append(r)
    return res


# ------------------------------------------------------------------ update
def check(log=None):
    """{"current", "latest", "newer", "kind", "url", "error"}"""
    res = {"current": __version__, "kind": kind(), "latest": None, "newer": False, "url": f"https://github.com/{REPO}/releases"}
    if kind() == "source":
        r = subprocess.run(["git", "-C", REPO_DIR, "fetch", "--quiet", "origin"], capture_output=True, text=True)
        http.log_event("GET", _origin(), 200 if r.returncode == 0 else 0, 0, 0, sent="git fetch: a check for new changes (nothing about you)",
                       purpose="Update (GitHub)", error=None if r.returncode == 0 else r.stderr.strip()[:200])
        if r.returncode != 0:
            res["error"] = "git fetch failed: " + (r.stderr.strip() or "is this a git folder?")
            return res
        behind = subprocess.run(["git", "-C", REPO_DIR, "rev-list", "--count", "HEAD..@{u}"], capture_output=True, text=True)
        n = int(behind.stdout.strip() or 0) if behind.returncode == 0 else 0
        res.update({"latest": f"{n} new change(s) on GitHub" if n else "up to date", "newer": n > 0})
        return res
    with http.sending("a check for a newer version (nothing about you)"):
        r, data = http.get_json(LATEST, headers={"Accept": "application/vnd.github+json"})
    if not data:
        res["error"] = r.error or f"GitHub answered HTTP {r.status}"
        return res
    tag = str(data.get("tag_name") or "")
    res["latest"] = tag.lstrip("v")
    res["newer"] = _version_tuple(tag) > _version_tuple(__version__)
    res["url"] = data.get("html_url") or res["url"]
    asset = next((a for a in data.get("assets") or [] if a.get("name") == ASSETS[platform_key()]), None)
    res["download"] = asset.get("browser_download_url") if asset else None
    return res


def _download(url, dest, log):
    """Streams a release file to disk (not size-limited like page reads)."""
    req = urllib.request.Request(url, headers={"User-Agent": http.USER_AGENT})
    got = 0
    with urllib.request.urlopen(req, timeout=60, context=http.SSL_CONTEXT) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        last = time.time()
        while True:
            chunk = r.read(1024 * 256)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if time.time() - last > 2:
                log(f"  downloaded {got // 1048576} of {max(total, got) // 1048576} MB")
                last = time.time()
    http.log_event("GET", url, 200, 0, got, sent="the new version's file (nothing about you)", purpose="Update (GitHub release)")
    return got


def _detached(cmd):
    """Starts a program that outlives this one (to restart or finish after exit)."""
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if os.name == "nt":
        kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000   # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW
    else:
        kw["start_new_session"] = True
    subprocess.Popen(cmd, **kw)


def relaunch_command(home_root):
    """How to start the app again after an update."""
    if kind() == "app":
        if platform_key() == "darwin":
            return ["/bin/sh", "-c", f'sleep 3; open "{app_location()}"']
        if platform_key() == "linux":
            return ["/bin/sh", "-c", f'sleep 3; "{app_location()}" --home "{home_root}" >/dev/null 2>&1']
        return None   # Windows: the installer starts the new version itself
    py, start = sys.executable, os.path.join(REPO_DIR, "launchers", "start.py")
    if os.name == "nt":
        return _after_exit_windows(f'"{py}" "{start}" --home "{home_root}"')
    return ["/bin/sh", "-c", f'sleep 3; "{py}" "{start}" --home "{home_root}" >/dev/null 2>&1']


def update(home_root=None, log=print, restart=False):
    """Updates to the newest version. Returns {"updated": bool, "message", "restart": bool}."""
    if kind() == "source":
        r = subprocess.run(["git", "-C", REPO_DIR, "pull", "--ff-only"], capture_output=True, text=True)
        http.log_event("GET", _origin(), 200 if r.returncode == 0 else 0, 0, 0, sent="git pull: download of the new version (nothing about you)",
                       purpose="Update (GitHub)")
        for line in (r.stdout + r.stderr).strip().splitlines()[-12:]:
            log("  " + line)
        if r.returncode != 0:
            return {"updated": False, "message": "git pull did not succeed (local changes? see above)", "restart": False}
        changed = "Already up to date" not in r.stdout
        if changed and restart and home_root:
            _detached(relaunch_command(home_root))
        return {"updated": changed, "restart": changed and restart,
                "message": "updated from GitHub" if changed else "already the newest version"}
    info = check()
    if info.get("error"):
        return {"updated": False, "message": f"could not check for updates: {info['error']}", "restart": False}
    if not info["newer"]:
        return {"updated": False, "message": f"you have the newest version ({__version__})", "restart": False}
    if not info.get("download"):
        return {"updated": False, "message": f"version {info['latest']} has no file for this system yet; try again later", "restart": False}
    log(f"downloading version {info['latest']} ...")
    tmp = tempfile.mkdtemp(prefix="jobagent-update-")
    dest = os.path.join(tmp, ASSETS[platform_key()])
    _download(info["download"], dest, log)
    key = platform_key()
    if key == "darwin":
        target = app_location()
        mnt = os.path.join(tmp, "mnt")
        os.makedirs(mnt)
        subprocess.run(["hdiutil", "attach", "-nobrowse", "-quiet", "-mountpoint", mnt, dest], check=True)
        try:
            src = os.path.join(mnt, "Job Agent.app")
            staged = target + ".new"
            shutil.rmtree(staged, ignore_errors=True)
            subprocess.run(["ditto", src, staged], check=True)
        finally:
            subprocess.run(["hdiutil", "detach", "-quiet", mnt])
        old = target + ".old"
        shutil.rmtree(old, ignore_errors=True)
        os.rename(target, old)
        os.rename(staged, target)
        shutil.rmtree(old, ignore_errors=True)
    elif key == "linux":
        import tarfile
        with tarfile.open(dest) as tf:
            member = next(m for m in tf.getmembers() if m.name.endswith("/JobAgent") and m.isfile())
            member.name = os.path.basename(member.name)
            tf.extract(member, tmp)
        target = app_location()
        staged = target + ".new"
        shutil.copy2(os.path.join(tmp, "JobAgent"), staged)
        os.chmod(staged, 0o755)
        os.replace(staged, target)          # a running program can be replaced on Linux
    else:
        log("starting the installer; Job Agent closes and opens again when it is done")
        _detached(_after_exit_windows(f'"{dest}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS'))
        return {"updated": True, "message": f"installing version {info['latest']}", "restart": True}
    log(f"installed version {info['latest']}")
    if restart and home_root:
        _detached(relaunch_command(home_root))
    return {"updated": True, "message": f"updated to version {info['latest']}", "restart": restart}


# ------------------------------------------------------------------ uninstall
def _remove_daily_runs(log):
    key = platform_key()
    if key == "darwin":
        for p in glob.glob(os.path.expanduser("~/Library/LaunchAgents/local.job-agent-engine.*.plist")):
            subprocess.run(["launchctl", "unload", p], capture_output=True)
            os.remove(p)
            log(f"removed daily run {os.path.basename(p)}")
    elif key == "win32":
        r = subprocess.run(["schtasks", "/Query", "/FO", "CSV", "/NH"], capture_output=True, text=True)
        for name in sorted(set(re.findall(r'"\\?(JobAgentEngine-[0-9a-f]+)"', r.stdout or ""))):
            subprocess.run(["schtasks", "/Delete", "/F", "/TN", name], capture_output=True)
            log(f"removed daily run {name}")
    else:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if r.returncode == 0 and "# job-agent-engine" in r.stdout:
            keep = [l for l in r.stdout.splitlines() if "# job-agent-engine" not in l]
            subprocess.run(["crontab", "-"], input="\n".join(keep) + ("\n" if keep else ""), capture_output=True, text=True)
            log("removed the daily run from crontab")


def _rm(path, log, what):
    if path and os.path.lexists(path):
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            os.remove(path)
        log(f"removed {what}: {path}")


def plan(home_root=None, remove_data=False, remove_engine=False):
    """What uninstall would remove, as text lines (for the confirmation)."""
    lines = ["every daily run Job Agent set up", f"the launcher's settings file {SETTINGS}"]
    if kind() == "app":
        lines.append(f"the app: {app_location()}" + (" (with the Windows uninstaller)" if platform_key() == "win32" else ""))
        if platform_key() == "linux":
            lines.append(f"the menu entry {LINUX_DESKTOP}")
    else:
        lines.append(f"the private Python in {os.path.join(REPO_DIR, '.venv')}")
        lines.append("the headless browser that './run.sh --browser' installed, if any")
        lines.append(f"the engine folder {REPO_DIR}" if remove_engine else f"(kept: the engine folder {REPO_DIR})")
    hs = homes(home_root)
    if remove_data:
        lines += [f"your job-search folder {h} (postings, CVs, letters, documents, backups)" for h in hs]
    else:
        lines += [f"(kept: your job-search folder {h})" for h in hs]
    return lines


def uninstall(home_root=None, remove_data=False, remove_engine=False, keep_app=False, log=print):
    """Removes Job Agent from this computer. With keep_app the program files
    stay (the Windows uninstaller removes them itself)."""
    hs = homes(home_root)
    _remove_daily_runs(log)
    _rm(SETTINGS, log, "settings file")
    if kind() == "source":
        venv = os.path.join(REPO_DIR, ".venv")
        if glob.glob(os.path.join(venv, "lib*", "python*", "site-packages", "playwright")) or \
                os.path.isdir(os.path.join(venv, "Lib", "site-packages", "playwright")):
            for cache in (os.path.expanduser("~/Library/Caches/ms-playwright"), os.path.expanduser("~/.cache/ms-playwright"),
                          os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")):
                for d in glob.glob(os.path.join(cache, "chromium_headless_shell-*")):
                    _rm(d, log, "headless browser")
        if os.name == "nt" and os.path.isdir(venv):    # the running Python is in it: remove it after this app closes
            _detached(_after_exit_windows(f'rmdir /s /q "{venv}"'))
            log(f"the private Python {venv} is removed when the app closes")
        else:
            _rm(venv, log, "private Python")
    if remove_data:
        for h in hs:
            _rm(h, log, "job-search folder")
    if kind() == "source":
        if remove_engine:
            _detached(["/bin/sh", "-c", f'sleep 2; rm -rf "{REPO_DIR}"'] if os.name != "nt"
                      else _after_exit_windows(f'rmdir /s /q "{REPO_DIR}"'))
            log(f"the engine folder {REPO_DIR} is removed in a moment")
        else:
            log(f"left in place: the engine folder {REPO_DIR} (delete it yourself if you do not need it)")
        return {"ok": True}
    if keep_app:
        return {"ok": True}
    key, loc = platform_key(), app_location()
    if key == "darwin":
        _detached(["/bin/sh", "-c", f'sleep 2; rm -rf "{loc}"'])
        log(f"the app {loc} is removed when it closes")
    elif key == "linux":
        _rm(LINUX_DESKTOP, log, "menu entry")
        _rm(loc, log, "the app")
    else:
        unins = sorted(glob.glob(os.path.join(loc, "unins*.exe")))
        if unins:
            _detached(_after_exit_windows(f'"{unins[-1]}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART'))
            log("the Windows uninstaller removes the app when it closes")
        else:
            log(f"remove the folder {loc} yourself (no uninstaller found)")
    return {"ok": True}
