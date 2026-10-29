#!/bin/bash
# Job-search agent engine
# File:    Job Agent.command
# Purpose: macOS double-click launcher: opens the Job Agent app.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.1
# Date:    2026-10-29
cd "$(dirname "$0")/../.." || exit 1   # the engine folder
PY="$(command -v python3 || true)"
for p in /opt/homebrew/bin/python3 /usr/local/bin/python3; do [ -z "$PY" ] && [ -x "$p" ] && PY="$p"; done
if [ -z "$PY" ]; then
  echo "Job Agent needs Python 3. Install it from https://www.python.org/downloads/ and double-click this file again."
  read -r -p "Press Enter to close." _; exit 1
fi
exec "$PY" launchers/start.py "$@"
