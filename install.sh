#!/data/data/com.termux/files/usr/bin/bash

echo "===================================="
echo " LG Home Server v3.2 - Instalação"
echo "===================================="

BASE="$HOME/Servidor"
WEB="$BASE/Web"

mkdir -p "$WEB"
mkdir -p "$BASE/Cameras"
mkdir -p "$BASE/Backups"
mkdir -p "$BASE/Logs"

cp -f public/index.html "$WEB/index.html"
cp -rf public/css "$WEB/"
cp -rf public/js "$WEB/"
cp -rf public/img "$WEB/" 2>/dev/null

if [ -f scripts/update_status.sh ]; then
  bash scripts/update_status.sh
else
  echo "Aviso: scripts/update_status.sh não encontrado."
fi

echo ""
echo "Instalação concluída."
echo "Acesse: http://IP_DO_CELULAR:8080"
