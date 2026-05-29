#!/bin/bash
set -o errexit
set -o nounset
set -o pipefail

DATE=$(date +%Y-%m-%d)
BACKUP_DIR="${BACKUP_DIR:-/tmp/gaintime_backups}"
DB_URL="${DATABASE_URL:-postgres://wends23:scam2024pass@127.0.0.1:5433/scam}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Début du backup..."

pg_dump "$DB_URL" \
    --format=custom \
    --file="$BACKUP_DIR/db_$DATE.dump" \
    --verbose 2>&1 | tail -1

echo "[$(date)] Backup terminé : $BACKUP_DIR/db_$DATE.dump"

# Nettoyage des vieux backups
find "$BACKUP_DIR" -name "db_*.dump" -mtime +$RETENTION_DAYS -delete
echo "[$(date)] Nettoyage des backups de plus de $RETENTION_DAYS jours effectué"
