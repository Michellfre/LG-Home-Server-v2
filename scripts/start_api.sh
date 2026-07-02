#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")/.."
if pgrep -f "api/server.py" >/dev/null; then
  echo "API já está rodando."
else
  nohup python api/server.py > "$HOME/Servidor/Logs/api.log" 2>&1 &
  echo "API iniciada na porta 8090."
fi
