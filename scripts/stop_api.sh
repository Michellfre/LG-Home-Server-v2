#!/data/data/com.termux/files/usr/bin/bash
pkill -f "api/server.py" && echo "Open Home OS API parada." || echo "API não estava rodando."
