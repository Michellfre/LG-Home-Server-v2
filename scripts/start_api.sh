#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")/.."
mkdir -p "$HOME/OpenHomeOS/Logs"
pkill -f "api/server.py" 2>/dev/null
nohup python api/server.py > "$HOME/OpenHomeOS/Logs/api.log" 2>&1 &
sleep 1
pgrep -f "api/server.py" >/dev/null && echo "Open Home OS API iniciada na porta 8090." || echo "Falha. Veja: cat ~/OpenHomeOS/Logs/api.log"
