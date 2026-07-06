#!/data/data/com.termux/files/usr/bin/bash
echo "Open Home OS v13 Diagnóstico"
echo "IP: $(ip -o -4 addr show 2>/dev/null | awk '!/127.0.0.1/ {split($4,a,"/"); print a[1]; exit}')"
echo "Armazenamento:"; df -h | grep -E '/storage|/mnt/media_rw|/sdcard|/data'
echo "API log:"; tail -100 ~/OpenHomeOS/Logs/api.log 2>/dev/null
