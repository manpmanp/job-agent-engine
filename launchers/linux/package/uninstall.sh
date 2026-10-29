#!/usr/bin/env bash
# Job-search agent engine
# File:    launchers/linux/package/uninstall.sh
# Purpose: Opens Job Agent on its uninstall section, which removes the app, its daily run and settings (and, if you tick it, your job-search folder).
# Author:  manpmanp <manp.node@gmail.com>. Generated with Claude (Anthropic), under the author's direction and review. MIT.
BIN="$HOME/.local/bin/job-agent"
if [ -x "$BIN" ]; then
  nohup "$BIN" --page uninstall >/dev/null 2>&1 &
  echo "Job Agent opens in your browser on its uninstall section."
  exit 0
fi
echo "Job Agent is not installed. Removing its daily run and settings file, if any."
crontab -l 2>/dev/null | grep -v "# job-agent-engine" | crontab - 2>/dev/null || true
rm -f "$HOME/.job-agent-engine.json" "$HOME/.local/share/applications/job-agent.desktop"
echo "Done. Your job-search folder (~/JobAgent) is kept; delete it yourself if you do not need it."
