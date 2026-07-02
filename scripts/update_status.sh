#!/data/data/com.termux/files/usr/bin/bash

BASE="$HOME/Servidor"
WEB="$BASE/Web"

mkdir -p "$WEB" "$BASE/Cameras" "$BASE/Backups" "$BASE/Logs" "$BASE/Files"

IP=$(ip -o -4 addr show 2>/dev/null | awk '!/127.0.0.1/ {split($4,a,"/"); print a[1]; exit}')
[ -z "$IP" ] && IP="não encontrado"

DISK=$(df -h "$HOME" | awk 'NR==2 {print $4 " livre de " $2}')
USED=$(df "$HOME" | awk 'NR==2 {print $5}')
DATE=$(date '+%d/%m/%Y %H:%M:%S')
UPTIME=$(uptime 2>/dev/null | sed 's/"/\"/g')

NGINX="Parado"
pgrep nginx >/dev/null && NGINX="Ativo"

API="Parada"
pgrep -f "api/server.py" >/dev/null && API="Ativa"

CAM_COUNT=$(find "$BASE/Cameras" -type f 2>/dev/null | wc -l | tr -d ' ')
BACKUP_COUNT=$(find "$BASE/Backups" -type f 2>/dev/null | wc -l | tr -d ' ')
LOG_COUNT=$(find "$BASE/Logs" -type f 2>/dev/null | wc -l | tr -d ' ')
FILE_COUNT=$(find "$BASE/Files" -type f 2>/dev/null | wc -l | tr -d ' ')

cat > "$WEB/status.json" <<EOF
{
  "ip": "$IP",
  "nginx": "$NGINX",
  "api": "$API",
  "disk": "$DISK",
  "used": "$USED",
  "camera_files": "$CAM_COUNT",
  "backup_files": "$BACKUP_COUNT",
  "log_files": "$LOG_COUNT",
  "files": "$FILE_COUNT",
  "uptime": "$UPTIME",
  "updated": "$DATE"
}
EOF

echo "Status atualizado: $WEB/status.json"
