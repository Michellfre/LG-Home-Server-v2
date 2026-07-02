#!/data/data/com.termux/files/usr/bin/bash
echo "LG Home Server v3 - Instalando..."

BASE="$HOME/Servidor"
WEB="$BASE/Web"

mkdir -p "$WEB" "$BASE/Cameras" "$BASE/Backups" "$BASE/Logs"

cp -f public/index.html "$WEB/index.html"
cp -rf public/css "$WEB/"
cp -rf public/js "$WEB/"
bash scripts/update_status.sh

echo "Instalação concluída."
echo "Acesse: http://IP_DO_CELULAR:8080"
