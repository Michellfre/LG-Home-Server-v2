#!/data/data/com.termux/files/usr/bin/bash
echo "===================================="
echo " LG Home Server v5 - Instalação"
echo "===================================="

BASE="$HOME/Servidor"
WEB="$BASE/Web"

mkdir -p "$WEB" "$BASE/Cameras" "$BASE/Backups" "$BASE/Logs" "$BASE/Files"

cp -f public/index.html "$WEB/index.html"
cp -rf public/css "$WEB/"
cp -rf public/js "$WEB/"

bash scripts/update_status.sh

echo ""
echo "Instalação concluída."
echo "Rode:"
echo "nginx -s reload"
echo "bash scripts/start_api.sh"
echo ""
echo "Acesse: http://IP_DO_CELULAR:8080"
