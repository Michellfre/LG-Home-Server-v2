#!/data/data/com.termux/files/usr/bin/bash
echo "Open Home Server v10.3 - Diagnóstico"
echo "Python: $(python --version 2>/dev/null)"
pgrep nginx >/dev/null && echo "Nginx: ativo" || echo "Nginx: parado"
pgrep -f api/server.py >/dev/null && echo "API: ativa" || echo "API: parada"
echo "IP: $(ip -o -4 addr show 2>/dev/null | awk '!/127.0.0.1/ {split($4,a,"/"); print a[1]; exit}')"
echo "Disco: $(df -h "$HOME" | awk 'NR==2 {print $4 " livre de " $2 " (" $5 " usado)"}')"
echo "Memória: $(free -m 2>/dev/null | awk '/Mem:/ {print $3" MB usado de "$2" MB"}')"
echo "Termux API:"
command -v termux-wifi-connectioninfo >/dev/null && echo "termux-api instalado" || echo "Instale com: pkg install termux-api"
echo "Processos:"
ps 2>/dev/null | head -15
echo "Últimas linhas da API:"
tail -30 ~/Servidor/Logs/api.log 2>/dev/null
