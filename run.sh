#!/usr/bin/env bash
# Job-search agent engine
# File:    run.sh
# Purpose: Single entry point: setup, dependency check and all engine commands.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
# Date:    2026-10-28
#
# Single entry point for the job-search agent engine.
#   ./run.sh [--home DIR] <command> [args]
# Commands: --setup [--browser] (install + open the app), app, clean, release, form, fetch, test, init, status, plan, collect, verify, enrich, run,
#           schedule, open, add-postings, weekly, sync, intake, tailor, checkpoint,
#           note, demo. See docs/commands.md.
set -euo pipefail
ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ENGINE_DIR/.venv"
BASE_PY="${PYTHON:-python3}"

# Python packages live in a private virtual environment inside the engine
# folder (.venv), so nothing is installed system-wide. This works with
# Homebrew and other "externally managed" Pythons (PEP 668).
if [ -x "$VENV/bin/python" ]; then PY="$VENV/bin/python"; else PY="$BASE_PY"; fi

if ! command -v "$BASE_PY" >/dev/null 2>&1 && [ ! -x "$VENV/bin/python" ]; then
  echo "python3 not found. Install Python 3.9 or newer." >&2; exit 1
fi

# "setup" or "--setup" anywhere in the arguments: install the dependencies
# into .venv (first time, or when requirements changed), create the agent
# home, then open the app's Setup page in the browser.
# "clean": removes files the engine no longer uses or that are rebuilt on
# demand (Node modules from versions before 0.4, Python caches, Finder's
# .DS_Store files) and folders left empty by the 0.4.2 reorganisation.
# Agent homes (my_agent/, ~/JobAgent, ...) and .venv are never touched.
if [ "${1:-}" = "clean" ] || { [ "${1:-}" = "--home" ] && [ "${3:-}" = "clean" ]; }; then
  cd "$ENGINE_DIR"
  rm -rf node_modules package.json package-lock.json
  find . -path ./.git -prune -o -path ./.venv -prune -o -path ./my_agent -prune -o -path ./cloud/node_modules -prune \
       -o \( -name __pycache__ -o -name .DS_Store \) -print0 | xargs -0 rm -rf
  for d in app forms defaults inputs_templates state_templates skills demo engine/templates/js; do
    [ -d "$d" ] && [ -z "$(git ls-files "$d" 2>/dev/null)" ] && [ -z "$(find "$d" -type f 2>/dev/null)" ] && rm -rf "$d"
  done
  echo "cleaned: old Node modules, Python caches, .DS_Store files and empty old folders"
  [ -d my_agent ] && echo "kept my_agent/ (an agent home; delete it yourself if you do not use it)"
  exit 0
fi

# "release" (maintainers): publishes the version in engine/__init__.py.
# Brings this folder up to date with GitHub, then tags that version on the
# newest commit and pushes the tag; GitHub then builds the three packages
# and attaches them to the release. If the tag already exists on an older
# commit (tagged before pulling), it asks before moving it.
if [ "${1:-}" = "release" ]; then
  cd "$ENGINE_DIR"
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  [ "$BRANCH" = "main" ] || { echo "switch to main first (now on $BRANCH)" >&2; exit 1; }
  git diff --quiet && git diff --cached --quiet || { echo "you have uncommitted changes; commit or discard them first" >&2; exit 1; }
  git fetch --quiet origin main --tags --force
  git pull --quiet --ff-only origin main || { echo "could not update from GitHub (local commits?)" >&2; exit 1; }
  VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' engine/__init__.py)"
  TAG="v$VERSION"; HEAD_SHA="$(git rev-parse HEAD)"
  REMOTE_SHA="$(git ls-remote --tags origin "refs/tags/$TAG" | cut -f1)"
  if [ "$REMOTE_SHA" = "$HEAD_SHA" ]; then
    echo "$TAG is already released from the newest commit ($(git log -1 --format='%h %s' | cut -c1-70))"; exit 0
  fi
  if [ -n "$REMOTE_SHA" ]; then
    echo "$TAG exists on an older commit: $(git log -1 --format='%h %s' "$REMOTE_SHA" 2>/dev/null | cut -c1-70)"
    echo "newest commit:                 $(git log -1 --format='%h %s' | cut -c1-70)"
    read -r -p "Move $TAG to the newest commit and rebuild its packages? [y/N] " OK
    [ "$OK" = "y" ] || [ "$OK" = "Y" ] || { echo "nothing changed"; exit 0; }
    git tag -f "$TAG" >/dev/null && git push --quiet --force origin "refs/tags/$TAG"
  else
    git tag -d "$TAG" >/dev/null 2>&1 || true
    git tag "$TAG" && git push --quiet origin "refs/tags/$TAG"
  fi
  URL="$(git remote get-url origin | sed -e 's#^git@github.com:#https://github.com/#' -e 's#\.git$##')"
  echo "$TAG pushed. The packages are built in a few minutes: $URL/actions"
  echo "then download them from $URL/releases/tag/$TAG"
  exit 0
fi

SETUP=0; BROWSER=0; NOBROWSER=0; ARGS=()
for a in "$@"; do
  case "$a" in
    setup|--setup) SETUP=1 ;;
    --browser) BROWSER=1 ;;
    --remove-browser) NOBROWSER=1 ;;
    *) ARGS+=("$a") ;;
  esac
done

# Install or update the Python packages whenever requirements.txt changed
# (first start, or after 'git pull'). Nothing outside .venv is touched.
install_deps() {
  if [ ! -x "$VENV/bin/python" ]; then
    echo "creating virtual environment in $VENV"
    "$BASE_PY" -m venv "$VENV"
  fi
  STAMP="$VENV/.requirements.installed"
  if [ ! -f "$STAMP" ] || ! cmp -s "$ENGINE_DIR/requirements.txt" "$STAMP"; then
    echo "installing Python packages into $VENV ..."
    "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check -r "$ENGINE_DIR/requirements.txt" || {
      echo "installing packages failed; check the internet connection and try again" >&2; exit 1; }
    cp "$ENGINE_DIR/requirements.txt" "$STAMP"
  fi
  PY="$VENV/bin/python"
}
install_deps

if [ "$BROWSER" = 1 ]; then
  # Optional: Playwright's headless Chromium (about 100 MB, once), used to
  # read posting pages that are built in the browser.
  "$PY" -c "import playwright" >/dev/null 2>&1 || "$PY" -m pip install --quiet playwright
  "$PY" -m playwright install --only-shell chromium && echo "headless browser installed"
fi
if [ "$NOBROWSER" = 1 ]; then
  # Removes only the browsers this engine's Playwright installed (others keep theirs).
  "$PY" -m playwright uninstall >/dev/null 2>&1 || true
  "$PY" -m pip uninstall --quiet -y playwright >/dev/null 2>&1 || true
  echo "headless browser removed (an installed Chrome or Edge is still used when present)"
  [ "$SETUP" = 0 ] && [ ${#ARGS[@]} -eq 0 ] && exit 0
fi
if [ "$SETUP" = 1 ]; then
  PYTHONPATH="$ENGINE_DIR${PYTHONPATH:+:$PYTHONPATH}" exec "$PY" -m engine.cli ${ARGS[@]+"${ARGS[@]}"} form
fi
if [ "$BROWSER" = 1 ] && [ ${#ARGS[@]} -eq 0 ]; then exit 0; fi
set -- ${ARGS[@]+"${ARGS[@]}"}

if [ "${1:-}" = "test" ]; then
  cd "$ENGINE_DIR" && exec "$PY" -m unittest discover -s tests
fi

PYTHONPATH="$ENGINE_DIR${PYTHONPATH:+:$PYTHONPATH}" exec "$PY" -m engine.cli "$@"
