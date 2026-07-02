#!/data/data/com.termux/files/usr/bin/bash
BASE="$HOME/Servidor"; WEB="$BASE/Web"
mkdir -p "$WEB" "$BASE/Cameras" "$BASE/Backups" "$BASE/Logs" "$BASE/Files" "$BASE/Trash"
IP=$(ip -o -4 addr show 2>/dev/null | awk '!/127.0.0.1/ {split($4,a,"/"); print a[1]; exit}')
[ -z "$IP" ] && IP="não encontrado"
NGINX="Parado"; pgrep nginx >/dev/null && NGINX="Ativo"
API="Parada"; pgrep -f "api/server.py" >/dev/null && API="Ativa"
cat > "$WEB/status.json" <<EOF
{"ip":"$IP","nginx":"$NGINX","api":"$API","disk":"$(df -h "$HOME" | awk 'NR==2 {print $4 " livre de " $2}')","used":"$(df "$HOME" | awk 'NR==2 {print $5}')","updated":"$(date '+%d/%m/%Y %H:%M:%S')","python":"$(python --version 2>/dev/null)"}
EOF
echo "Status atualizado."
