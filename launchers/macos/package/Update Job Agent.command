#!/bin/bash
# Job-search agent engine
# File:    launchers/macos/package/Update Job Agent.command
# Purpose: Opens Job Agent on its update section (Settings > Update and uninstall), which fetches and installs the newest version.
# Author:  manpmanp <manp.node@gmail.com>. Generated with Claude (Anthropic), under the author's direction and review. MIT.
APP="/Applications/Job Agent.app"; [ -d "$APP" ] || APP="$HOME/Applications/Job Agent.app"
if [ ! -d "$APP" ]; then
  echo "Job Agent is not in Applications. Drag it there from the disk image first."; read -r -p "Press Enter to close. "; exit 1
fi
nohup "$APP/Contents/MacOS/JobAgent" --page update >/dev/null 2>&1 &
disown
echo "Job Agent opens in your browser on its update section. You can close this window."
sleep 3
