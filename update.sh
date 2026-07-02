#!/data/data/com.termux/files/usr/bin/bash

echo "===================================="
echo " Atualizando LG Home Server"
echo "===================================="

git pull
bash install.sh

if pgrep nginx >/dev/null; then
  nginx -s reload
else
  nginx
fi

echo "Atualização concluída."
