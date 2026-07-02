#!/data/data/com.termux/files/usr/bin/bash
git pull
bash install.sh
nginx -s reload
bash scripts/start_api.sh
echo "Atualização concluída."
