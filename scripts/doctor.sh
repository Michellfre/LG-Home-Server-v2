#!/data/data/com.termux/files/usr/bin/bash
echo "Open Home OS v11.0 - Diagnóstico"
echo "Python: $(python --version 2>/dev/null)"
pgrep nginx >/dev/null && echo "Nginx: ativo" || echo "Nginx: parado"
pgrep -f api/server.py >/dev/null && echo "API: ativa" || echo "API: parada"
echo "IP: $(ip -o -4 addr show 2>/dev/null | awk '!/127.0.0.1/ {split($4,a,"/"); print a[1]; exit}')"
echo "Termux API:"; command -v termux-battery-status >/dev/null && termux-battery-status || echo "termux-api não instalado/configurado"
echo "FFmpeg:"; command -v ffmpeg >/dev/null && ffmpeg -version | head -1 || echo "ffmpeg não instalado"
echo "Log API:"; tail -60 ~/OpenHomeOS/Logs/api.log 2>/dev/null
