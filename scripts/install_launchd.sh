#!/usr/bin/env bash
# Install the Job Scout schedule as macOS launchd user agents:
#
#   com.jobscout.scan    — nightly scan (07:30): search + score + instant alerts
#   com.jobscout.digest  — weekly digest (Sunday 17:00): email the week's matches
#
# launchd (not cron) because it handles laptop sleep: a job whose time passed
# while the lid was closed fires once on wake instead of being skipped.
#
# The agents run with launchd's minimal environment, so everything here is
# absolute: the job-scout binary from the venv, CLAUDE_PATH baked into the
# plist (a bare `claude` would not be on launchd's PATH), and
# WorkingDirectory set to the repo so .env and data/ resolve.
#
# Re-run after moving the repo or reinstalling `claude`. Undo with
# scripts/uninstall_launchd.sh. Logs land in logs/scan.log and logs/digest.log.
set -euo pipefail

SCAN_HOUR=7;  SCAN_MINUTE=30
DIGEST_WEEKDAY=0; DIGEST_HOUR=17; DIGEST_MINUTE=0   # 0 = Sunday

REPO="$(cd "$(dirname "$0")/.." && pwd)"
JOB_SCOUT="$REPO/.venv/bin/job-scout"
AGENTS_DIR="$HOME/Library/LaunchAgents"
LOGS_DIR="$REPO/logs"
UID_NUM="$(id -u)"

[[ -x "$JOB_SCOUT" ]] || { echo "error: $JOB_SCOUT not found — run: python -m venv .venv && .venv/bin/pip install -e ." >&2; exit 1; }
[[ -f "$REPO/.env" ]] || echo "warning: $REPO/.env missing — runs will be email dry-runs" >&2

CLAUDE_PATH="${CLAUDE_PATH:-$(command -v claude || true)}"
[[ -n "$CLAUDE_PATH" ]] || { echo "error: claude binary not found — set CLAUDE_PATH or install Claude Code" >&2; exit 1; }

mkdir -p "$AGENTS_DIR" "$LOGS_DIR"

# write_plist <label> <log-name> <calendar-xml> [extra job-scout args...]
write_plist() {
  local label="$1" log_name="$2" calendar="$3"; shift 3
  local args_xml=""
  for arg in "$@"; do args_xml+="        <string>${arg}</string>
"; done
  cat > "$AGENTS_DIR/$label.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>${label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${JOB_SCOUT}</string>
${args_xml}    </array>
    <key>WorkingDirectory</key><string>${REPO}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>CLAUDE_PATH</key><string>${CLAUDE_PATH}</string>
    </dict>
    <key>StartCalendarInterval</key>
    <dict>
${calendar}
    </dict>
    <key>StandardOutPath</key><string>${LOGS_DIR}/${log_name}.log</string>
    <key>StandardErrorPath</key><string>${LOGS_DIR}/${log_name}.log</string>
    <key>RunAtLoad</key><false/>
</dict>
</plist>
PLIST
}

write_plist com.jobscout.scan scan \
  "        <key>Hour</key><integer>${SCAN_HOUR}</integer>
        <key>Minute</key><integer>${SCAN_MINUTE}</integer>"

write_plist com.jobscout.digest digest \
  "        <key>Weekday</key><integer>${DIGEST_WEEKDAY}</integer>
        <key>Hour</key><integer>${DIGEST_HOUR}</integer>
        <key>Minute</key><integer>${DIGEST_MINUTE}</integer>" \
  --digest

for label in com.jobscout.scan com.jobscout.digest; do
  launchctl bootout "gui/$UID_NUM/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$UID_NUM" "$AGENTS_DIR/$label.plist"
  echo "loaded $label"
done

printf '\nInstalled. Scan runs daily %02d:%02d; digest runs Sunday %02d:%02d.\n' \
  "$SCAN_HOUR" "$SCAN_MINUTE" "$DIGEST_HOUR" "$DIGEST_MINUTE"
echo "Logs: $LOGS_DIR/{scan,digest}.log"
echo "Trigger one now:  launchctl kickstart gui/$UID_NUM/com.jobscout.scan"
