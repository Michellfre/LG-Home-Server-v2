#!/data/data/com.termux/files/usr/bin/bash
echo "Open Home OS v13.2 Discovery Engine - Instalando..."
BASE="$HOME/OpenHomeOS"; WEB="$BASE/Web"; CONFIG="$BASE/Config"; DATA="$BASE/Data"
mkdir -p "$WEB" "$CONFIG" "$BASE/Logs" "$DATA/Files" "$DATA/Cameras" "$DATA/Snapshots" "$DATA/Backups" "$DATA/IoT" "$DATA/Connect" "$DATA/Network" "$DATA/Discovery"
[ -f "$CONFIG/devices.json" ] || echo "[]" > "$CONFIG/devices.json"
[ -f "$CONFIG/rooms.json" ] || echo '["Sala","Quarto","Cozinha","Garagem","Oficina","Jardim"]' > "$CONFIG/rooms.json"
[ -f "$CONFIG/network_devices.json" ] || echo '{"last_scan":"","devices":[],"summary":{}}' > "$CONFIG/network_devices.json"
[ -f "$CONFIG/tuya_cloud.json" ] || echo '{"enabled":false,"client_id":"","client_secret":"","data_center":"https://openapi.tuyaus.com","asset_id":"","last_sync":"","token":"","token_expire":0}' > "$CONFIG/tuya_cloud.json"
cp -f public/index.html "$WEB/index.html"
cp -rf public/css "$WEB/"
cp -rf public/js "$WEB/"
bash scripts/config_nginx.sh
echo "Instalação concluída. Rode: nginx -s reload && bash scripts/start_api.sh"
