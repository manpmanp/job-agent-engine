#!/bin/bash
# Job-search agent engine
# File:    launchers/macos/package/Uninstall Job Agent.command
# Purpose: Opens Job Agent on its uninstall section, which removes the app, its daily run and settings (and, if you tick it, your job-search folder).
# Author:  manpmanp <manp.node@gmail.com>. Generated with Claude (Anthropic), under the author's direction and review. MIT.
APP="/Applications/Job Agent.app"; [ -d "$APP" ] || APP="$HOME/Applications/Job Agent.app"
if [ -d "$APP" ]; then
  nohup "$APP/Contents/MacOS/JobAgent" --page uninstall >/dev/null 2>&1 &
  disown
  echo "Job Agent opens in your browser on its uninstall section. You can close this window."
  sleep 3; exit 0
fi
# The app is already gone: remove what it may have left.
echo "Job Agent is not in Applications. Removing its daily run and settings file, if any."
for p in "$HOME"/Library/LaunchAgents/local.job-agent-engine.*.plist; do
  [ -e "$p" ] && launchctl unload "$p" 2>/dev/null; [ -e "$p" ] && rm -f "$p" && echo "removed $p"
done
rm -f "$HOME/.job-agent-engine.json"
echo "Done. Your job-search folder (~/JobAgent) is kept; delete it yourself if you do not need it."
read -r -p "Press Enter to close. "
