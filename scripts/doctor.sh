#!/data/data/com.termux/files/usr/bin/bash
python --version
pgrep nginx >/dev/null && echo Nginx ativo || echo Nginx parado
pgrep -f api/server.py >/dev/null && echo API ativa || echo API parada
tail -20 ~/Servidor/Logs/api.log 2>/dev/null
