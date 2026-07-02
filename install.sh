#!/data/data/com.termux/files/usr/bin/bash
echo "LG Home Server v2 - Instalando..."

BASE="$HOME/Servidor"
WEB="$BASE/Web"

mkdir -p "$WEB" "$BASE/Cameras" "$BASE/Backups" "$BASE/Logs"

cp -f public/index.html "$WEB/index.html"
cp -rf public/css "$WEB/"
cp -rf public/js "$WEB/"

NGINX_CONF="$PREFIX/etc/nginx/nginx.conf"

if [ -f "$NGINX_CONF" ]; then
  cp "$NGINX_CONF" "$NGINX_CONF.bak.$(date +%Y%m%d%H%M%S)"
  python scripts/config_nginx.py "$NGINX_CONF" "$WEB"
fi

echo ""
echo "Instalação concluída."
echo "Agora rode:"
echo "nginx -s reload"
echo ""
echo "Acesse:"
echo "http://IP_DO_CELULAR:8080"
