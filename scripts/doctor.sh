#!/data/data/com.termux/files/usr/bin/bash
echo "LG Home Server v5.1 - Diagnóstico"
echo "Python:"
python --version
echo ""
echo "Nginx:"
pgrep nginx >/dev/null && echo "Ativo" || echo "Parado"
echo ""
echo "API:"
pgrep -f "api/server.py" >/dev/null && echo "Ativa" || echo "Parada"
echo ""
echo "Log da API:"
tail -20 "$HOME/Servidor/Logs/api.log" 2>/dev/null
