#!/data/data/com.termux/files/usr/bin/bash
CONF="$PREFIX/etc/nginx/nginx.conf"; ROOT="$HOME/OpenHomeOS/Web"; mkdir -p "$ROOT"
cat > "$CONF" <<EOF
worker_processes 1;
events { worker_connections 1024; }
http {
 include mime.types;
 default_type application/octet-stream;
 sendfile on;
 keepalive_timeout 65;
 server {
  listen 8080;
  server_name localhost;
  root $ROOT;
  index index.html;
  location / { try_files \$uri \$uri/ /index.html; }
 }
}
EOF
echo "Nginx configurado."
