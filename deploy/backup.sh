#!/usr/bin/env bash
# پشتیبان روزانه‌ی دیتابیس PostgreSQL و فایل‌های media و private_media (PDF رژیم بیماران)؛ ۱۴ نسخه‌ی آخر نگه داشته می‌شود.
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/nutrition_clinic}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/nutrition_clinic}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M)"

set -a
# shellcheck disable=SC1091
source "$APP_DIR/.env"
set +a

mkdir -p "$BACKUP_DIR"

PGPASSWORD="$DB_PASSWORD" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -Fc "$DB_NAME" \
    > "$BACKUP_DIR/db-$STAMP.dump"
tar -czf "$BACKUP_DIR/media-$STAMP.tar.gz" -C "$APP_DIR" media
# فایل‌های پزشکی؛ پشتیبان هم محرمانه است (فقط مالک بخواند)
(umask 077 && tar -czf "$BACKUP_DIR/private-media-$STAMP.tar.gz" -C "$APP_DIR" private_media)

find "$BACKUP_DIR" -type f -mtime +"$KEEP_DAYS" -name 'db-*.dump' -delete
find "$BACKUP_DIR" -type f -mtime +"$KEEP_DAYS" -name 'media-*.tar.gz' -delete
find "$BACKUP_DIR" -type f -mtime +"$KEEP_DAYS" -name 'private-media-*.tar.gz' -delete

echo "$(date) backup ok: $STAMP"
