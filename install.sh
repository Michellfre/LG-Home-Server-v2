#!/data/data/com.termux/files/usr/bin/bash
echo "Open Home Server v10.7 Jarvis + TV Mode - Instalando..."
BASE="$HOME/Servidor"; WEB="$BASE/Web"
mkdir -p "$WEB" "$BASE/Cameras" "$BASE/Backups" "$BASE/Logs" "$BASE/Files" "$BASE/Shared" "$BASE/Trash" "$BASE/Config" "$BASE/Media" "$BASE/Photos" "$BASE/Videos" "$BASE/Music" "$BASE/Downloads" "$BASE/Documents" "$BASE/Snapshots" "$BASE/Streams"
[ -f "$BASE/Config/cameras.json" ] || echo "[]" > "$BASE/Config/cameras.json"
[ -f "$BASE/Config/discovery.json" ] || echo "[]" > "$BASE/Config/discovery.json"
[ -f "$BASE/Config/notifications.json" ] || echo "[]" > "$BASE/Config/notifications.json"
[ -f "$BASE/Config/events.json" ] || echo "[]" > "$BASE/Config/events.json"
[ -f "$BASE/Config/setup.json" ] || echo '{"done":false,"step":1}' > "$BASE/Config/setup.json"
[ -f "$BASE/Config/jarvis.json" ] || echo '{"history":[],"tv_mode":false,"name":"Jarvis"}' > "$BASE/Config/jarvis.json"
[ -f "$BASE/Config/sensor_cache.json" ] || echo '{"ts":0}' > "$BASE/Config/sensor_cache.json"
cp -f public/index.html "$WEB/index.html"; cp -rf public/css "$WEB/"; cp -rf public/js "$WEB/"
bash scripts/update_status.sh
echo "Instalação concluída. Rode: nginx -s reload && bash scripts/start_api.sh"
