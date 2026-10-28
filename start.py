#!/usr/bin/env python3
# Job-search agent engine
# File:    start.py
# Purpose: Cross-platform launcher: prepares its own Python environment on first start, then opens the local app.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
# Date:    2026-10-28

"""
Double-click "Job Agent.command" (macOS), "Job Agent.bat" (Windows) or
"job-agent.sh" (Linux), or run:  python3 start.py

First start: creates a private Python environment in .venv/ next to this
file and installs the few packages the engine needs (nothing system-wide),
asks where to keep your job-search folder (default: a "JobAgent" folder in
your home folder), remembers it, and opens the app in your browser.

Later starts open the app directly. If it is already running, the browser
is just pointed at it.

Other uses:
    start.py --home DIR          use another job-search folder
    start.py --run auto          one run without the app (used by the daily schedule)
    start.py --cli <command...>  any engine command, as with ./run.sh
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
VENV = os.path.join(HERE, ".venv")
VENV_PY = os.path.join(VENV, "Scripts", "python.exe") if os.name == "nt" else os.path.join(VENV, "bin", "python")
STAMP = os.path.join(VENV, ".requirements.installed")
REQ = os.path.join(HERE, "requirements.txt")
SETTINGS = os.path.join(os.path.expanduser("~"), ".job-agent-engine.json")
DEFAULT_HOME = os.path.join(os.path.expanduser("~"), "JobAgent")
MIN_PY = (3, 9)


def say(msg):
    print(msg, flush=True)


def pause_on_error(msg):
    say("\n" + msg)
    if sys.stdin and sys.stdin.isatty():
        try:
            input("\nPress Enter to close this window.")
        except EOFError:
            pass
    sys.exit(1)


def _same(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def ensure_environment(argv):
    """Re-runs this script inside .venv with the requirements installed."""
    if getattr(sys, "frozen", False):
        return
    if sys.version_info < MIN_PY:
        pause_on_error(f"Python {MIN_PY[0]}.{MIN_PY[1]} or newer is needed (this is {sys.version.split()[0]}). "
                       "Install it from https://www.python.org/downloads/ and start again.")
    in_venv = os.path.exists(VENV_PY) and _same(sys.executable, VENV_PY)
    if not os.path.exists(VENV_PY):
        say("First start: preparing Job Agent (about a minute, only once)...")
        import venv
        try:
            venv.EnvBuilder(with_pip=True).create(VENV)
        except Exception as e:
            pause_on_error(f"Could not create the Python environment in {VENV}: {e}\n"
                           "On Debian/Ubuntu install it with: sudo apt install python3-venv")
    req = open(REQ, "rb").read()
    if not os.path.exists(STAMP) or open(STAMP, "rb").read() != req:
        say("Installing the packages Job Agent needs...")
        r = subprocess.run([VENV_PY, "-m", "pip", "install", "--disable-pip-version-check", "--quiet", "-r", REQ])
        if r.returncode != 0:
            pause_on_error("Installing packages failed. Check your internet connection and start again.")
        with open(STAMP, "wb") as f:
            f.write(req)
    if not in_venv:
        r = subprocess.run([VENV_PY, os.path.abspath(__file__)] + argv)
        sys.exit(r.returncode)


def _settings():
    try:
        with open(SETTINGS, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def choose_home(explicit=None):
    if explicit:
        return os.path.abspath(os.path.expanduser(explicit))
    env = os.environ.get("JOB_AGENT_HOME")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    s = _settings()
    if s.get("home"):
        return s["home"]
    home = DEFAULT_HOME
    if sys.stdin and sys.stdin.isatty():
        say(f"\nWhere should Job Agent keep your job search (postings, CVs, letters)?")
        try:
            ans = input(f"Press Enter for {DEFAULT_HOME}, or type another folder: ").strip()
        except EOFError:
            ans = ""
        if ans:
            home = os.path.abspath(os.path.expanduser(ans))
    try:
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump({"home": home}, f, indent=2)
    except OSError:
        pass
    return home


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ensure_environment(argv)
    sys.path.insert(0, HERE)
    from engine import cli  # noqa: E402

    home = None
    if "--home" in argv:
        i = argv.index("--home")
        home = argv[i + 1] if i + 1 < len(argv) else None
        argv = argv[:i] + argv[i + 2:]
    if argv[:1] == ["--cli"]:
        rest = argv[1:]
        if "--home" in rest:  # --cli --home X ...
            return cli.main(rest)
        return cli.main(["--home", choose_home(home)] + rest)
    if argv[:1] == ["--run"]:
        mode = argv[1] if len(argv) > 1 else "auto"
        return cli.main(["--home", choose_home(home), "run", mode])
    home = choose_home(home)
    say(f"Job Agent: your job-search folder is {home}")
    return cli.main(["--home", home, "app"])


if __name__ == "__main__":
    main(sys.argv[1:])
