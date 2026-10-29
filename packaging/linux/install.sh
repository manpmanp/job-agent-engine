#!/usr/bin/env bash
# Job-search agent engine
# File:    packaging/linux/install.sh
# Purpose: Installs the Linux build for the current user (~/.local/bin + applications menu), or removes it with --remove.
# Author:  manpmanp <manp.node@gmail.com>
# Generated with Claude (Anthropic), under the author's direction and review.
# License: MIT (see LICENSE)
# Version: 0.4.1
# Date:    2026-10-29
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
BIN="$HOME/.local/bin/job-agent"
DESKTOP="$HOME/.local/share/applications/job-agent.desktop"
if [ "${1:-}" = "--remove" ]; then
  rm -f "$BIN" "$DESKTOP"
  echo "Job Agent removed. Your job search in ~/JobAgent is kept."
  exit 0
fi
mkdir -p "$(dirname "$BIN")" "$(dirname "$DESKTOP")"
install -m 755 "$HERE/JobAgent" "$BIN"
cat > "$DESKTOP" <<DESK
[Desktop Entry]
Type=Application
Name=Job Agent
Comment=Find job postings, decide, and draft your documents
Exec=$BIN
Terminal=false
Categories=Office;
DESK
echo "Job Agent installed. Start it from your applications menu, or run: job-agent"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "(add ~/.local/bin to your PATH to run 'job-agent' from a terminal)";; esac
