#!/usr/bin/env bash
# Job-search agent engine
# File:    launchers/linux/package/update.sh
# Purpose: Opens Job Agent on its update section, which fetches and installs the newest version.
# Author:  manpmanp <manp.node@gmail.com>. Generated with Claude (Anthropic), under the author's direction and review. MIT.
BIN="$HOME/.local/bin/job-agent"
[ -x "$BIN" ] || { echo "Job Agent is not installed (run ./install.sh first)."; exit 1; }
nohup "$BIN" --page update >/dev/null 2>&1 &
echo "Job Agent opens in your browser on its update section."
