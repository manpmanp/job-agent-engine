#!/usr/bin/env bash
# Job-search agent engine
# File:    job-agent.sh
# Purpose: Linux launcher (double-click or run): opens the Job Agent app.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.0
# Date:    2026-10-28
cd "$(dirname "$0")" || exit 1
command -v python3 >/dev/null || { echo "Job Agent needs Python 3 (e.g. sudo apt install python3 python3-venv)."; exit 1; }
exec python3 start.py "$@"
