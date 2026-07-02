#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")/.."; mkdir -p "$HOME/Servidor/Logs"; pkill -f "api/server.py" 2>/dev/null
nohup python api/server.py > "$HOME/Servidor/Logs/api.log" 2>&1 & sleep 1
pgrep -f "api/server.py" >/dev/null && echo "API iniciada na porta 8090." || echo "Falha. Veja: cat ~/Servidor/Logs/api.log"
