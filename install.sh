#!/data/data/com.termux/files/usr/bin/bash
echo "LG Home Server v6 - Instalando..."
BASE="$HOME/Servidor"; WEB="$BASE/Web"
mkdir -p "$WEB" "$BASE/Cameras" "$BASE/Backups" "$BASE/Logs" "$BASE/Files" "$BASE/Trash"
cp -f public/index.html "$WEB/index.html"; cp -rf public/css "$WEB/"; cp -rf public/js "$WEB/"
bash scripts/update_status.sh
echo "Instalação concluída. Rode: nginx -s reload && bash scripts/start_api.sh"
