# Job-search agent engine
# File:    engine/schedule.py
# Purpose: Installs, removes and reports the daily automatic run (launchd on macOS, cron on Linux, Task Scheduler on Windows).
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
# Date:    2026-10-28

"""
One daily job per agent home, at HOUR:MINUTE local time, running
'start.py --home <home> --run auto' (full search on your search day, a sync
on the other days). The log goes to <home>/state/run.log.

- macOS: ~/Library/LaunchAgents/local.job-agent-engine.<id>.plist, loaded
  with launchctl. launchd also runs a missed job after the Mac wakes.
- Linux: one crontab line tagged '# job-agent-engine <home>'.
- Windows: a Task Scheduler task 'JobAgentEngine-<id>' (schtasks).

Nothing outside these is touched.
"""
import hashlib
import os
import subprocess
import sys

from .home import REPO_DIR

HOUR, MINUTE = 8, 2


def _id(home):
    return hashlib.sha1(os.path.abspath(home.root).encode("utf-8")).hexdigest()[:8]


def command(home):
    """The command the scheduler runs."""
    if getattr(sys, "frozen", False):  # packaged app
        return [sys.executable, "--home", home.root, "--run", "auto"]
    return [sys.executable, os.path.join(REPO_DIR, "start.py"), "--home", home.root, "--run", "auto"]


def _log(home):
    return os.path.join(os.path.dirname(home.path("notes")), "run.log")


def _plist_path(home):
    return os.path.expanduser(f"~/Library/LaunchAgents/local.job-agent-engine.{_id(home)}.plist")


def _xml(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _plist(home):
    args = "".join(f"<string>{_xml(a)}</string>" for a in command(home))
    log = _xml(_log(home))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>local.job-agent-engine.{_id(home)}</string>
  <key>ProgramArguments</key><array>{args}</array>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>{HOUR}</integer><key>Minute</key><integer>{MINUTE}</integer></dict>
  <key>StandardOutPath</key><string>{log}</string>
  <key>StandardErrorPath</key><string>{log}</string>
</dict></plist>
"""


def _tag(home):
    return f"# job-agent-engine {os.path.abspath(home.root)}"


def _cron_line(home):
    q = " ".join(f'"{a}"' for a in command(home))
    return f'{MINUTE} {HOUR} * * * {q} >> "{_log(home)}" 2>&1 {_tag(home)}'


def _crontab():
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def _task_name(home):
    return f"JobAgentEngine-{_id(home)}"


def status(home):
    """(installed: bool, description)"""
    try:
        if sys.platform == "darwin":
            on = os.path.exists(_plist_path(home))
        elif os.name == "nt":
            on = subprocess.run(["schtasks", "/Query", "/TN", _task_name(home)], capture_output=True).returncode == 0
        else:
            on = _tag(home) in _crontab()
    except Exception as e:
        return False, f"could not check: {e}"
    return on, (f"runs every day at {HOUR:02d}:{MINUTE:02d}" if on else "off")


def install(home):
    os.makedirs(os.path.dirname(_log(home)), exist_ok=True)
    if sys.platform == "darwin":
        p = _plist_path(home)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        subprocess.run(["launchctl", "unload", p], capture_output=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(_plist(home))
        r = subprocess.run(["launchctl", "load", p], capture_output=True, text=True)
        if r.returncode != 0:
            return False, f"launchctl: {r.stderr.strip()}"
    elif os.name == "nt":
        tr = subprocess.list2cmdline(command(home))
        r = subprocess.run(["schtasks", "/Create", "/F", "/SC", "DAILY", "/ST", f"{HOUR:02d}:{MINUTE:02d}",
                            "/TN", _task_name(home), "/TR", tr], capture_output=True, text=True)
        if r.returncode != 0:
            return False, f"schtasks: {(r.stderr or r.stdout).strip()}"
    else:
        lines = [l for l in _crontab().splitlines() if _tag(home) not in l]
        lines.append(_cron_line(home))
        r = subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", capture_output=True, text=True)
        if r.returncode != 0:
            return False, f"crontab: {r.stderr.strip()}"
    return True, f"daily run installed ({HOUR:02d}:{MINUTE:02d}), log: {_log(home)}"


def remove(home):
    if sys.platform == "darwin":
        p = _plist_path(home)
        if os.path.exists(p):
            subprocess.run(["launchctl", "unload", p], capture_output=True)
            os.remove(p)
    elif os.name == "nt":
        subprocess.run(["schtasks", "/Delete", "/F", "/TN", _task_name(home)], capture_output=True)
    else:
        cur = _crontab()
        if _tag(home) in cur:
            lines = [l for l in cur.splitlines() if _tag(home) not in l]
            subprocess.run(["crontab", "-"], input="\n".join(lines) + ("\n" if lines else ""), capture_output=True, text=True)
    return True, "daily run removed"


def describe(home):
    """Text for './run.sh schedule': what would be installed, for manual setups."""
    return (f"Daily run at {HOUR:02d}:{MINUTE:02d} ('auto': full search on your search day, sync on other days).\n"
            f"Install it with:   ./run.sh schedule install     (remove: ./run.sh schedule remove)\n"
            f"or with the switch on the app's Schedule page.\n\n"
            f"Command: {subprocess.list2cmdline(command(home))}\n"
            f"Log:     {_log(home)}\n\n"
            f"cron line (Linux):\n{_cron_line(home)}\n\nlaunchd file (macOS):\n{_plist(home)}")
