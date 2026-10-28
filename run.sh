#!/usr/bin/env bash
# Job-search agent engine
# File:    run.sh
# Purpose: Single entry point: setup, dependency check and all engine commands.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.3.0
# Date:    2026-10-28
#
# Single entry point for the job-search agent engine.
#   ./run.sh [--home DIR] <command> [args]
# Commands: --setup (install + open the input forms), form, test, init, status, plan, collect, verify, enrich, run,
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
# home, then open the input forms in the browser.
SETUP=0; ARGS=()
for a in "$@"; do
  case "$a" in
    setup|--setup) SETUP=1 ;;
    *) ARGS+=("$a") ;;
  esac
done
if [ "$SETUP" = 1 ]; then
  if [ ! -x "$VENV/bin/python" ]; then
    echo "creating virtual environment in $VENV"
    "$BASE_PY" -m venv "$VENV"
  fi
  STAMP="$VENV/.requirements.installed"
  if [ ! -f "$STAMP" ] || ! cmp -s "$ENGINE_DIR/requirements.txt" "$STAMP"; then
    "$VENV/bin/python" -m pip install --quiet --upgrade pip
    "$VENV/bin/python" -m pip install --quiet -r "$ENGINE_DIR/requirements.txt"
    cp "$ENGINE_DIR/requirements.txt" "$STAMP"
    echo "Python dependencies installed in $VENV"
  fi
  if [ ! -d "$ENGINE_DIR/node_modules/docx" ]; then
    if command -v npm >/dev/null 2>&1; then
      (cd "$ENGINE_DIR" && npm install --no-audit --no-fund --silent) && echo "Node dependencies installed"
    else
      echo "npm not found: documents will be written as Markdown until Node.js is installed."
    fi
  fi
  PY="$VENV/bin/python"
  PYTHONPATH="$ENGINE_DIR${PYTHONPATH:+:$PYTHONPATH}" exec "$PY" -m engine.cli ${ARGS[@]+"${ARGS[@]}"} form
fi

if ! "$PY" -c "import openpyxl" >/dev/null 2>&1; then
  echo "Python dependencies are not installed. Run:" >&2
  echo "  $ENGINE_DIR/run.sh setup" >&2
  exit 1
fi

if [ "${1:-}" = "test" ]; then
  cd "$ENGINE_DIR" && exec "$PY" -m unittest discover -s tests
fi

PYTHONPATH="$ENGINE_DIR${PYTHONPATH:+:$PYTHONPATH}" exec "$PY" -m engine.cli "$@"
