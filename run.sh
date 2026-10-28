#!/usr/bin/env bash
# Job-search agent engine
# File:    run.sh
# Purpose: Single entry point: setup, dependency check and all engine commands.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.2.0
# Date:    2026-10-28
#
# Single entry point for the job-search agent engine.
#   ./run.sh [--home DIR] <command> [args]
# Commands: init, status, plan, add-postings, weekly, sync, intake, tailor,
#           checkpoint, note, demo. See docs/commands.md.
set -euo pipefail
ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "python3 not found. Install Python 3.9 or newer." >&2; exit 1
fi
if [ "${1:-}" = "setup" ]; then
  "$PY" -m pip install -r "$ENGINE_DIR/requirements.txt"
  if command -v npm >/dev/null 2>&1; then (cd "$ENGINE_DIR" && npm install --no-audit --no-fund); else
    echo "npm not found: documents will be written as Markdown until Node.js is installed."; fi
  exit 0
fi
if ! "$PY" -c "import openpyxl" >/dev/null 2>&1; then
  echo "Python package 'openpyxl' is missing. Install it with:" >&2
  echo "  $PY -m pip install -r \"$ENGINE_DIR/requirements.txt\"" >&2
  exit 1
fi
PYTHONPATH="$ENGINE_DIR${PYTHONPATH:+:$PYTHONPATH}" exec "$PY" -m engine.cli "$@"
