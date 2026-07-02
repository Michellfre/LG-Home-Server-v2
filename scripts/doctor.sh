#!/data/data/com.termux/files/usr/bin/bash
echo "LG Home Server v5 - Diagnóstico"
echo "Projeto: $(pwd)"
echo "Nginx:"; pgrep nginx >/dev/null && echo "Ativo" || echo "Parado"
echo "API:"; pgrep -f "api/server.py" >/dev/null && echo "Ativa" || echo "Parada"
echo "IP:"; ip -o -4 addr show 2>/dev/null | awk '!/127.0.0.1/ {print $2, $4}'
echo "Web:"; ls "$HOME/Servidor/Web" 2>/dev/null
echo "Scripts:"; ls scripts
