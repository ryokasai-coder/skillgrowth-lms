#!/usr/bin/env bash
# Import a SQLite DB (e.g. downloaded from PythonAnywhere) into the VPS LMS.
#   bash import_db.sh /root/lms.db
# Keeps the previous DB as instance/lms.db.bak-<ts>. Runs integrity check + migrate.py.
set -euo pipefail
APP_DIR=/opt/skillgrowth-lms
SRC="${1:?usage: import_db.sh /path/to/lms.db}"
[ -f "$SRC" ] || { echo "not found: $SRC"; exit 1; }

R=$(sqlite3 "$SRC" "PRAGMA integrity_check;")
[ "$R" = ok ] || { echo "integrity_check failed: $R"; exit 1; }

systemctl stop skillgrowth-lms 2>/dev/null || true
TS=$(date +%Y%m%d_%H%M%S)
[ -f "$APP_DIR/instance/lms.db" ] && cp -p "$APP_DIR/instance/lms.db" "$APP_DIR/instance/lms.db.bak-$TS"
install -o lms -g lms -m 640 "$SRC" "$APP_DIR/instance/lms.db"

cd "$APP_DIR"
sudo -u lms .venv/bin/python migrate.py

echo "--- row counts ---"
for t in company user course lesson enrollment lesson_progress study_log login_session; do
  printf "%-16s %s\n" "$t" "$(sqlite3 "$APP_DIR/instance/lms.db" "SELECT COUNT(*) FROM $t" 2>/dev/null || echo '-')"
done

systemctl enable skillgrowth-lms >/dev/null
systemctl restart skillgrowth-lms
sleep 2
PORT=$(grep '^LMS_PORT=' /etc/skillgrowth-lms.env | cut -d= -f2)
curl -s -o /dev/null -w "health /login: %{http_code}\n" "http://127.0.0.1:$PORT/login"
echo "IMPORT OK"
