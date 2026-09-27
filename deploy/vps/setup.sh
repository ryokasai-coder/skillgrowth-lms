#!/usr/bin/env bash
# Skill Growth LMS: VPS setup (idempotent, non-destructive). Run as root.
#   bash setup.sh [PORT]
# - Installs into /opt/skillgrowth-lms as dedicated system user "lms".
# - Listens on 127.0.0.1:PORT only (nginx fronts it). Does NOT touch nginx/DNS.
# - Service is started only after a DB exists (see import_db.sh).
set -euo pipefail

APP_DIR=/opt/skillgrowth-lms
APP_USER=lms
REPO=https://github.com/ryokasai-coder/skillgrowth-lms.git
ENV_FILE=/etc/skillgrowth-lms.env
PORT="${1:-3080}"

[ "$(id -u)" = 0 ] || { echo "run as root"; exit 1; }

# Port must be free (or already ours)
if ss -ltn "( sport = :$PORT )" | grep -q LISTEN; then
  if ! systemctl is-active --quiet skillgrowth-lms; then
    echo "ERROR: port $PORT is already in use by another process. Choose another: bash setup.sh <PORT>"; exit 1
  fi
fi

apt-get install -y -q python3-venv sqlite3 fonts-ipaexfont-gothic >/dev/null

id "$APP_USER" >/dev/null 2>&1 || useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"

if [ -d "$APP_DIR/.git" ]; then
  sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only
else
  mkdir -p "$APP_DIR"; chown "$APP_USER:$APP_USER" "$APP_DIR"
  sudo -u "$APP_USER" git clone "$REPO" "$APP_DIR"
fi
sudo -u "$APP_USER" mkdir -p "$APP_DIR/instance" "$APP_DIR/backups"
chmod 750 "$APP_DIR/instance" "$APP_DIR/backups"

[ -x "$APP_DIR/.venv/bin/python" ] || sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -q --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

FONT=$(ls /usr/share/fonts/opentype/ipaexfont-gothic/ipaexg.ttf /usr/share/fonts/truetype/ipaexfont-gothic/ipaexg.ttf 2>/dev/null | head -1 || true)

if [ ! -f "$ENV_FILE" ]; then
  umask 027
  cat > "$ENV_FILE" <<ENV
LMS_SECRET_KEY=$(python3 -c 'import secrets;print(secrets.token_hex(32))')
LMS_HTTPS=1
LMS_TRUST_PROXY=1
LMS_HOST=127.0.0.1
LMS_PORT=$PORT
LMS_DATABASE_URI=sqlite:///$APP_DIR/instance/lms.db
LMS_JP_FONT_PATH=$FONT
ENV
  chown root:"$APP_USER" "$ENV_FILE"; chmod 640 "$ENV_FILE"
  echo "created $ENV_FILE"
else
  echo "keep existing $ENV_FILE"
fi

cat > /etc/systemd/system/skillgrowth-lms.service <<UNIT
[Unit]
Description=Skill Growth LMS (waitress)
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$APP_DIR/.venv/bin/python serve.py
Restart=always
RestartSec=3
NoNewPrivileges=true
ProtectSystem=full
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/skillgrowth-lms-backup.service <<UNIT
[Unit]
Description=Skill Growth LMS daily backup

[Service]
Type=oneshot
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python backup.py
UNIT

cat > /etc/systemd/system/skillgrowth-lms-backup.timer <<UNIT
[Unit]
Description=Skill Growth LMS daily backup (03:30)

[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now skillgrowth-lms-backup.timer >/dev/null

if [ -f "$APP_DIR/instance/lms.db" ]; then
  systemctl enable skillgrowth-lms >/dev/null
  systemctl restart skillgrowth-lms
  sleep 2
  curl -s -o /dev/null -w "health /login: %{http_code}\n" "http://127.0.0.1:$PORT/login"
else
  echo "No DB yet -> service not started. Next: bash import_db.sh /path/to/lms.db"
fi
echo "SETUP OK (dir=$APP_DIR port=$PORT)"
