#!/data/data/com.termux/files/usr/bin/bash
echo "LG Home Server v9 - Instalando..."
BASE="$HOME/Servidor"; WEB="$BASE/Web"
mkdir -p "$WEB" "$BASE/Cameras" "$BASE/Backups" "$BASE/Logs" "$BASE/Files" "$BASE/Trash" "$BASE/Config" "$BASE/Media" "$BASE/Downloads" "$BASE/Documents"
[ -f "$BASE/Config/cameras.json" ] || echo "[]" > "$BASE/Config/cameras.json"
[ -f "$BASE/Config/notifications.json" ] || echo "[]" > "$BASE/Config/notifications.json"
[ -f "$BASE/Config/settings.json" ] || echo '{"camera_retention_days":30,"auto_delete_when_disk_above":90,"backup_hour":"02:00","theme":"dark","notifications":true}' > "$BASE/Config/settings.json"
cp -f public/index.html "$WEB/index.html"; cp -rf public/css "$WEB/"; cp -rf public/js "$WEB/"
bash scripts/update_status.sh
echo "Instalação concluída. Rode: nginx -s reload && bash scripts/start_api.sh"
