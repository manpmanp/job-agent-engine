# Job-search agent engine
# File:    engine/guard.py
# Purpose: Stops personal details from being committed or pushed from a development clone, and moves the agent folder into the ignored my_agent/.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.11
# Date:    2026-11-05

"""
    ./run.sh guard install      git hooks in this clone + your list of private details
    ./run.sh guard add TEXT     add one private detail to the list
    ./run.sh guard status       hooks installed? how many details listed?
    ./run.sh guard check        scan every file in the repository now
    ./run.sh guard move-data    move your agent folder (for example ~/JobAgent) to my_agent/ here

Your private details (name, e-mail addresses, home town, employer, phone,
calendar or account IDs, ...) are listed one per line in
~/.config/job-agent/private_markers.txt, outside the repository, so the
list itself is never published. The hooks then refuse:
- a commit whose files (also the text inside Word, Excel and PowerPoint
  files, and PDFs when pypdf is installed) or file names contain one of them,
- a commit message that contains one,
- a push of commits that contain one.
With no list, every commit is refused until the list exists.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from io import BytesIO

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKERS = os.environ.get("JOB_AGENT_MARKERS") or os.path.join(os.path.expanduser("~"), ".config", "job-agent", "private_markers.txt")
HOOK_TAG = "job-agent guard"
HOOKS = {
    "pre-commit": "pre-commit",
    "commit-msg": "commit-msg \"$1\"",
    "pre-push": "pre-push",
}
ZERO = "0" * 40


# ------------------------------------------------------------------ markers
def markers(path=None):
    try:
        with open(path or MARKERS, encoding="utf-8") as f:
            lines = [l.strip() for l in f]
    except OSError:
        return []
    return [l for l in lines if l and not l.startswith("#") and len(l) >= 3]


def add_marker(text, path=None):
    path = path or MARKERS
    text = " ".join(str(text).split())
    if len(text) < 3:
        raise ValueError("a detail needs at least 3 characters")
    have = [m.lower() for m in markers(path)]
    if text.lower() in have:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as f:
        if new:
            f.write("# Private details that must never be committed to the public engine (one per line).\n"
                    "# Matching ignores upper and lower case. This file stays outside the repository.\n")
        f.write(text + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return True


def _pattern(marks):
    # whole words where the detail starts/ends with a letter or digit: "Anna" matches "Anna," but not "Annaberg"
    parts = []
    for m in sorted(set(marks), key=len, reverse=True):
        p = re.escape(m).replace("\\ ", r"[\s_.-]+")
        if m[:1].isalnum():
            p = r"(?<![A-Za-z0-9])" + p
        if m[-1:].isalnum():
            p = p + r"(?![A-Za-z0-9])"
        parts.append(p)
    return re.compile("|".join(parts), re.IGNORECASE) if parts else None


# ------------------------------------------------------------------ reading files
OFFICE = (".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp")


def text_of(name, data):
    """The searchable text of a file's bytes: plain text, the text inside office files, PDFs when pypdf is there."""
    low = name.lower()
    if low.endswith(OFFICE):
        try:
            z = zipfile.ZipFile(BytesIO(data))
            raw = " ".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.endswith(".xml"))
            return re.sub(r"<[^>]+>", " ", raw)
        except (zipfile.BadZipFile, OSError, KeyError):
            return data.decode("utf-8", "ignore")
    if low.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            return "\n".join((pg.extract_text() or "") for pg in PdfReader(BytesIO(data)).pages)
        except Exception:
            return data.decode("latin-1", "ignore")
    if b"\0" in data[:8000]:
        return ""                       # images, video and other binaries: only the file name is checked
    return data.decode("utf-8", "ignore")


def scan(name, data, rx):
    """The private details found in a file name or its content."""
    if rx is None:
        return []
    found = {m.group(0) for m in rx.finditer(name)}
    found |= {m.group(0) for m in rx.finditer(text_of(name, data))}
    return sorted(found, key=str.lower)


def _git(repo, *args, data=False):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "ignore").strip() or "git failed")
    return r.stdout if data else r.stdout.decode("utf-8", "ignore")


def _need(rx):
    if rx is None:
        print(f"{HOOK_TAG}: no list of private details yet, so nothing can be checked and the commit is stopped.\n"
              f"  Add them with:  ./run.sh guard install   (or: ./run.sh guard add \"text\")", file=sys.stderr)
        return False
    return True


def _report(hits, what):
    print(f"{HOOK_TAG}: {what} stopped. Private details found:", file=sys.stderr)
    for where, words in hits:
        print(f"  {where}: {', '.join(words)}", file=sys.stderr)
    print("  Remove them (or keep the file in my_agent/, which is not part of the repository) and try again.", file=sys.stderr)


# ------------------------------------------------------------------ the hooks
def pre_commit(repo):
    rx = _pattern(markers())
    if not _need(rx):
        return 1
    names = [n for n in _git(repo, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split("\0") if n]
    hits = []
    for n in names:
        words = scan(n, _git(repo, "show", f":{n}", data=True), rx)
        if words:
            hits.append((n, words))
    if hits:
        _report(hits, "commit")
        return 1
    return 0


def commit_msg(repo, path):
    rx = _pattern(markers())
    if not _need(rx):
        return 1
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = "\n".join(l for l in f.read().splitlines() if not l.startswith("#"))
    words = scan("", text.encode("utf-8"), rx)
    if words:
        _report([("commit message", words)], "commit")
        return 1
    return 0


def pre_push(repo, lines):
    rx = _pattern(markers())
    if not _need(rx):
        return 1
    hits = []
    for line in lines:
        parts = line.split()
        if len(parts) < 4 or parts[1] == ZERO:
            continue                    # a branch being deleted
        local, remote = parts[1], parts[3]
        rng = local if remote == ZERO else f"{remote}..{local}"
        try:
            commits = _git(repo, "rev-list", rng).split()
        except RuntimeError:
            commits = _git(repo, "rev-list", local).split()
        for c in commits:
            msg = _git(repo, "log", "-1", "--format=%B", c)
            w = scan("", msg.encode("utf-8"), rx)
            if w:
                hits.append((f"message of {c[:7]}", w))
            for n in [x for x in _git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", "--diff-filter=ACMR", "-z", c).split("\0") if x]:
                w = scan(n, _git(repo, "show", f"{c}:{n}", data=True), rx)
                if w:
                    hits.append((f"{n} in {c[:7]}", w))
    if hits:
        _report(sorted(set((a, tuple(b)) for a, b in hits)), "push")
        return 1
    return 0


def check_all(repo):
    """Scans every tracked file as it is now. Returns the hits."""
    rx = _pattern(markers())
    if rx is None:
        return None
    hits = []
    for n in [x for x in _git(repo, "ls-files", "-z").split("\0") if x]:
        p = os.path.join(repo, n)
        try:
            with open(p, "rb") as f:
                data = f.read()
        except OSError:
            continue
        w = scan(n, data, rx)
        if w:
            hits.append((n, w))
    return hits


# ------------------------------------------------------------------ install / status
def _hooks_dir(repo):
    d = _git(repo, "rev-parse", "--git-path", "hooks").strip()
    return d if os.path.isabs(d) else os.path.join(repo, d)


def hook_text(kind):
    return ("#!/bin/sh\n"
            f"# {HOOK_TAG}: installed by ./run.sh guard install. Stops personal details from reaching the public repository.\n"
            'ROOT="$(git rev-parse --show-toplevel)" || exit 1\n'
            'PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3 || command -v python)"\n'
            f'PYTHONPATH="$ROOT" exec "$PY" -m engine.guard hook {HOOKS[kind]}\n')


def installed(repo=ENGINE_DIR):
    try:
        d = _hooks_dir(repo)
    except RuntimeError:
        return False
    for k in HOOKS:
        try:
            with open(os.path.join(d, k), encoding="utf-8") as f:
                if HOOK_TAG not in f.read():
                    return False
        except OSError:
            return False
    return True


def install(repo=ENGINE_DIR):
    d = _hooks_dir(repo)
    os.makedirs(d, exist_ok=True)
    done = []
    for k in HOOKS:
        p = os.path.join(d, k)
        if os.path.exists(p):
            with open(p, encoding="utf-8", errors="ignore") as f:
                if HOOK_TAG not in f.read():
                    shutil.copy2(p, p + ".before-guard")
        with open(p, "w", encoding="utf-8") as f:
            f.write(hook_text(k))
        os.chmod(p, 0o755)
        done.append(k)
    return done


# ------------------------------------------------------------------ moving the agent folder into my_agent/
SETTINGS = os.path.join(os.path.expanduser("~"), ".job-agent-engine.json")


def _app_settings():
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def move_data(src=None, engine_dir=ENGINE_DIR):
    """Moves the agent folder the app uses (or src) to <engine>/my_agent and points the app there.
    The my_agent/ already there is kept inside the moved folder's backups/. Returns lines to print."""
    from . import home as home_mod, schedule
    dest = os.path.join(engine_dir, "my_agent")
    s = _app_settings()
    src = os.path.abspath(os.path.expanduser(src or s.get("home") or os.path.join("~", "JobAgent")))
    out = []
    if os.path.realpath(src) == os.path.realpath(dest):
        return [f"the app already uses {dest}"]
    if not os.path.isdir(src):
        raise ValueError(f"no agent folder at {src}")
    if not os.path.isdir(os.path.join(src, "state")) and not os.path.isdir(os.path.join(src, "inputs")):
        raise ValueError(f"{src} does not look like an agent folder (no state/ or inputs/)")
    ign = subprocess.run(["git", "-C", engine_dir, "check-ignore", "-q", "--no-index", "my_agent/state/x"], capture_output=True)
    if ign.returncode != 0:
        raise ValueError("my_agent/ is not ignored by git in this folder; nothing was moved")
    try:
        from . import app
        if app.find_running(home_root=src):
            raise ValueError("Job Agent is open for that folder: quit it first (Quit the app, top right), then run this again")
    except ImportError:
        pass
    old_home = home_mod.Home(src)
    daily, _ = schedule.status(old_home, fresh=True)
    if daily:
        schedule.remove(old_home)
        out.append("daily search: taken off the old folder")
    if os.path.exists(dest):
        keep = os.path.join(src, "backups", datetime.now().strftime("%Y-%m-%d_%H%M%S") + "_earlier_my_agent")
        os.makedirs(os.path.dirname(keep), exist_ok=True)
        shutil.move(dest, keep)
        out.append(f"the earlier my_agent/ is kept in my_agent/backups/{os.path.basename(keep)}")
    shutil.move(src, dest)
    out.append(f"moved {src} -> {dest}")
    s["home"] = dest
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    out.append(f"the app now opens {dest}")
    if daily:
        ok, msg = schedule.install(home_mod.Home(dest))
        out.append("daily search: set up again for my_agent/" if ok else f"daily search: {msg}")
    return out


# ------------------------------------------------------------------ command line
def _ask_markers():
    print("List the private details that must never be published, one per line: your name (and other spellings),\n"
          "e-mail addresses, home town, employer, phone number, calendar or account IDs, your computer user name.\n"
          "Press Enter on an empty line to finish.")
    n = 0
    while True:
        try:
            line = input("  detail: ").strip()
        except EOFError:
            break
        if not line:
            break
        try:
            n += bool(add_marker(line))
        except ValueError as e:
            print(f"  {e}")
    return n


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "status"
    repo = ENGINE_DIR
    if cmd == "hook":
        kind = argv[1]
        try:
            if kind == "pre-commit":
                return pre_commit(repo)
            if kind == "commit-msg":
                return commit_msg(repo, argv[2])
            if kind == "pre-push":
                return pre_push(repo, sys.stdin.read().splitlines())
        except RuntimeError as e:
            print(f"{HOOK_TAG}: could not check ({e}); stopped to be safe", file=sys.stderr)
            return 1
        return 0
    if cmd == "install":
        if not os.path.isdir(os.path.join(repo, ".git")):
            print("this is not a git clone; nothing to guard")
            return 1
        print(f"hooks installed: {', '.join(install(repo))}")
        if not markers() and sys.stdin.isatty():
            print(f"added {_ask_markers()} detail(s) to {MARKERS}")
        n = len(markers())
        print(f"{n} private detail(s) listed in {MARKERS}" + ("" if n else "; commits are stopped until you add some: ./run.sh guard add \"text\""))
        if n:
            hits = check_all(repo)
            print("the repository as it is now: clean" if not hits else "the repository as it is now contains private details:")
            for where, words in hits or []:
                print(f"  {where}: {', '.join(words)}")
        return 0
    if cmd == "add":
        if len(argv) < 2:
            print("usage: ./run.sh guard add \"text\"")
            return 1
        print("added" if add_marker(" ".join(argv[1:])) else "already listed")
        return 0
    if cmd == "status":
        print(f"hooks: {'installed' if installed(repo) else 'not installed (./run.sh guard install)'}")
        print(f"private details listed: {len(markers())} ({MARKERS})")
        return 0
    if cmd == "check":
        hits = check_all(repo)
        if hits is None:
            print("no private details listed yet: ./run.sh guard install")
            return 1
        if not hits:
            print("clean: no listed private detail in any file of the repository")
            return 0
        for where, words in hits:
            print(f"  {where}: {', '.join(words)}")
        return 1
    if cmd == "move-data":
        try:
            for line in move_data(argv[1] if len(argv) > 1 else None):
                print(line)
        except ValueError as e:
            print(e)
            return 1
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
