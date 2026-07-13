#!/usr/bin/env bash
# Install the Job Scout schedule as cron jobs — for an always-on host (the
# home server). Laptops should use install_launchd.sh instead: cron silently
# skips runs whose time passes while the machine is asleep.
#
#   nightly scan   07:30           search + score + instant alerts
#   weekly digest  Sunday 17:00    email the week's matches
#
# cron runs with a minimal environment, so each job cd's into the repo (so
# .env and data/ resolve) and calls the venv's job-scout by absolute path.
# The claude binary is found via CLAUDE_PATH, which must be set in .env on
# any host where `claude` isn't on cron's PATH (i.e. every host).
#
# Idempotent: re-running replaces the previously installed Job Scout lines.
# Remove them with: crontab -l | grep -v '# job-scout' | crontab -
set -euo pipefail

SCAN_SCHEDULE="30 7 * * *"
DIGEST_SCHEDULE="0 17 * * 0"   # Sunday

REPO="$(cd "$(dirname "$0")/.." && pwd)"
JOB_SCOUT="$REPO/.venv/bin/job-scout"
LOGS_DIR="$REPO/logs"

[[ -x "$JOB_SCOUT" ]] || { echo "error: $JOB_SCOUT not found — run: python3 -m venv .venv && .venv/bin/pip install -e ." >&2; exit 1; }
[[ -f "$REPO/.env" ]] || echo "warning: $REPO/.env missing — runs will be email dry-runs" >&2
grep -q '^CLAUDE_PATH=' "$REPO/.env" 2>/dev/null \
  || echo "warning: CLAUDE_PATH not set in .env — cron won't find a bare \`claude\`; add CLAUDE_PATH=\$(which claude)" >&2

mkdir -p "$LOGS_DIR"

TAG='# job-scout'
{
  crontab -l 2>/dev/null | grep -v "$TAG" || true
  echo "$SCAN_SCHEDULE cd $REPO && $JOB_SCOUT >> $LOGS_DIR/scan.log 2>&1 $TAG"
  echo "$DIGEST_SCHEDULE cd $REPO && $JOB_SCOUT --digest >> $LOGS_DIR/digest.log 2>&1 $TAG"
} | crontab -

echo "Installed. Current crontab:"
crontab -l | grep "$TAG"
echo
echo "Logs: $LOGS_DIR/{scan,digest}.log"
echo "Test a run now:  cd $REPO && EMAIL_DRY_RUN=1 $JOB_SCOUT"
