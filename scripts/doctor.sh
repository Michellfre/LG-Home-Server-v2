#!/data/data/com.termux/files/usr/bin/bash
echo "Open Home Server v10.5 - Diagnóstico"
echo "Python: $(python --version 2>/dev/null)"
pgrep nginx >/dev/null && echo "Nginx: ativo" || echo "Nginx: parado"
pgrep -f api/server.py >/dev/null && echo "API: ativa" || echo "API: parada"
echo "IP: $(ip -o -4 addr show 2>/dev/null | awk '!/127.0.0.1/ {split($4,a,"/"); print a[1]; exit}')"
echo "FFmpeg:"; command -v ffmpeg >/dev/null && ffmpeg -version | head -1 || echo "Opcional: pkg install ffmpeg"
echo "Bateria:"; termux-battery-status 2>/dev/null || echo "Termux:API não respondeu"
echo "Wi-Fi:"; termux-wifi-connectioninfo 2>/dev/null || echo "Termux:API Wi-Fi não respondeu"
echo "Últimas linhas da API:"; tail -30 ~/Servidor/Logs/api.log 2>/dev/null
