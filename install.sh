#!/data/data/com.termux/files/usr/bin/bash
echo "Open Home OS v11.0 Core - Instalando..."
BASE="$HOME/OpenHomeOS"; WEB="$BASE/Web"; CONFIG="$BASE/Config"; DATA="$BASE/Data"
mkdir -p "$WEB" "$CONFIG" "$BASE/Logs" "$DATA/Files" "$DATA/Shared" "$DATA/Documents" "$DATA/Downloads" "$DATA/Media" "$DATA/Photos" "$DATA/Videos" "$DATA/Music" "$DATA/Cameras" "$DATA/Snapshots" "$DATA/Streams" "$DATA/Backups" "$DATA/Trash" "$DATA/AI" "$DATA/IoT"
cp -f public/index.html "$WEB/index.html"
cp -rf public/css "$WEB/"
cp -rf public/js "$WEB/"
bash scripts/config_nginx.sh
echo "Instalação concluída."
echo "Rode: nginx -s reload && bash scripts/start_api.sh"
