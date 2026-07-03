#!/data/data/com.termux/files/usr/bin/bash
echo "Open Home Server v10.7 - Diagnóstico"
python --version
pgrep nginx >/dev/null && echo "Nginx: ativo" || echo "Nginx: parado"
pgrep -f api/server.py >/dev/null && echo "API: ativa" || echo "API: parada"
tail -40 ~/Servidor/Logs/api.log 2>/dev/null
