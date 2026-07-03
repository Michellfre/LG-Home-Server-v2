#!/data/data/com.termux/files/usr/bin/bash
echo "Open Home OS v12.0 Smart Home Core - Instalando..."
BASE="$HOME/OpenHomeOS"; WEB="$BASE/Web"; CONFIG="$BASE/Config"; DATA="$BASE/Data"
mkdir -p "$WEB" "$CONFIG" "$BASE/Logs" "$DATA/Files" "$DATA/Cameras" "$DATA/Snapshots" "$DATA/Backups" "$DATA/Trash" "$DATA/IoT" "$DATA/Stats"
[ -f "$CONFIG/tuya_sensors.json" ] || echo "[]" > "$CONFIG/tuya_sensors.json"
cp -f public/index.html "$WEB/index.html"
cp -rf public/css "$WEB/"
cp -rf public/js "$WEB/"
bash scripts/config_nginx.sh
echo "Instalação concluída. Rode: nginx -s reload && bash scripts/start_api.sh"
