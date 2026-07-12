#!/usr/bin/env bash
# Remove the Job Scout launchd agents installed by install_launchd.sh.
set -euo pipefail

AGENTS_DIR="$HOME/Library/LaunchAgents"
UID_NUM="$(id -u)"

for label in com.jobscout.scan com.jobscout.digest; do
  launchctl bootout "gui/$UID_NUM/$label" 2>/dev/null && echo "unloaded $label" || true
  rm -f "$AGENTS_DIR/$label.plist" && echo "removed $AGENTS_DIR/$label.plist"
done
