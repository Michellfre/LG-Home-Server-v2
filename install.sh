#!/data/data/com.termux/files/usr/bin/bash

echo "===================================="
echo " LG Home Server v4 - Instalação"
echo "===================================="

BASE="$HOME/Servidor"
WEB="$BASE/Web"

mkdir -p "$WEB"
mkdir -p "$BASE/Cameras"
mkdir -p "$BASE/Backups"
mkdir -p "$BASE/Logs"
mkdir -p "$BASE/Files"

cp -f public/index.html "$WEB/index.html"
cp -rf public/css "$WEB/"
cp -rf public/js "$WEB/"
cp -rf public/img "$WEB/" 2>/dev/null

bash scripts/update_status.sh

echo ""
echo "Instalação concluída."
echo ""
echo "Agora rode:"
echo "nginx -s reload"
echo "bash scripts/start_api.sh"
echo ""
echo "Acesse: http://IP_DO_CELULAR:8080"
