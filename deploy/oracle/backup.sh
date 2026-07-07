#!/usr/bin/env bash
#
# Nightly backup for the racedog_hr production site. Runs `bench backup --with-files`
# inside the container, keeps the last 7 days on the box, and (optionally) copies the
# newest archive OFF the box to Oracle Object Storage so a VM loss doesn't lose data.
#
# Install (run once):
#   chmod +x ~/HR-Management-system/deploy/oracle/backup.sh
#   ( crontab -l 2>/dev/null; echo "0 2 * * * $HOME/HR-Management-system/deploy/oracle/backup.sh >> $HOME/backup.log 2>&1" ) | crontab -
#
set -euo pipefail

SITE="hr.racedogtechnologies.com"
COMPOSE="$HOME/racedog-compose.yml"
RETAIN_DAYS=7
D="sudo docker"

# --- Optional off-box upload to Oracle Object Storage (20 GB free) -------------
# Fill these in AND install the OCI CLI (see DEPLOY-ORACLE.md) to enable upload.
OS_BUCKET=""          # e.g. racedog-hr-backups   (leave empty to keep backups local only)
OS_NAMESPACE=""       # your Object Storage namespace (Oracle console -> Tenancy details)
# ------------------------------------------------------------------------------

echo "[$(date -u +%FT%TZ)] backup start"
$D compose -f "$COMPOSE" exec -T backend \
  bench --site "$SITE" backup --with-files

# Resolve the site's backup dir inside the 'sites' volume on the host.
VOL=$($D volume ls --format '{{.Name}}' | grep -E 'sites$' | head -1)
BACKDIR="$($D volume inspect "$VOL" -f '{{.Mountpoint}}')/$SITE/private/backups"

# Retention: drop anything older than RETAIN_DAYS.
sudo find "$BACKDIR" -type f -mtime +"$RETAIN_DAYS" -delete || true

# Off-box copy (only if configured).
if [[ -n "$OS_BUCKET" && -n "$OS_NAMESPACE" ]] && command -v oci >/dev/null 2>&1; then
  NEWEST_DB=$(sudo ls -t "$BACKDIR"/*-database.sql.gz 2>/dev/null | head -1 || true)
  NEWEST_FILES=$(sudo ls -t "$BACKDIR"/*-files.tar 2>/dev/null | head -1 || true)
  for f in "$NEWEST_DB" "$NEWEST_FILES"; do
    [ -n "$f" ] || continue
    oci os object put -bn "$OS_BUCKET" -ns "$OS_NAMESPACE" \
      --file "$f" --name "$(basename "$f")" --force
  done
  echo "[$(date -u +%FT%TZ)] uploaded newest backup to os://$OS_BUCKET"
else
  echo "[$(date -u +%FT%TZ)] off-box upload not configured — backups kept locally only"
fi

echo "[$(date -u +%FT%TZ)] backup done"
