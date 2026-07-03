#!/data/data/com.termux/files/usr/bin/bash
echo "Open Home Server v10.4 Android Sensor Edition - Instalando..."
BASE="$HOME/Servidor"; WEB="$BASE/Web"
mkdir -p "$WEB" "$BASE/Cameras" "$BASE/Backups" "$BASE/Logs" "$BASE/Files" "$BASE/Shared" "$BASE/Trash" "$BASE/Config" "$BASE/Media" "$BASE/Photos" "$BASE/Videos" "$BASE/Music" "$BASE/Downloads" "$BASE/Documents"
[ -f "$BASE/Config/cameras.json" ] || echo "[]" > "$BASE/Config/cameras.json"
[ -f "$BASE/Config/notifications.json" ] || echo "[]" > "$BASE/Config/notifications.json"
[ -f "$BASE/Config/events.json" ] || echo "[]" > "$BASE/Config/events.json"
[ -f "$BASE/Config/setup.json" ] || echo '{"done":false,"step":1}' > "$BASE/Config/setup.json"
[ -f "$BASE/Config/sensor_cache.json" ] || echo '{"ts":0}' > "$BASE/Config/sensor_cache.json"
[ -f "$BASE/Config/settings.json" ] || echo '{"project_name":"Open Home Server","device_name":"LG K41S","camera_retention_days":30,"auto_delete_when_disk_above":90,"battery_low_level":20,"temperature_alert":40,"backup_hour":"02:00","theme":"dark","notifications":true}' > "$BASE/Config/settings.json"
cp -f public/index.html "$WEB/index.html"; cp -rf public/css "$WEB/"; cp -rf public/js "$WEB/"
bash scripts/update_status.sh
echo "Instalação concluída."
echo "Rode: nginx -s reload && bash scripts/start_api.sh"
