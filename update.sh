#!/data/data/com.termux/files/usr/bin/bash
echo "Atualizando LG Home Server..."
git pull
bash install.sh
nginx -s reload
echo "Atualização concluída."
