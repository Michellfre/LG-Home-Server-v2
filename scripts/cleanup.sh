#!/data/data/com.termux/files/usr/bin/bash
BASE="$HOME/Servidor"
mkdir -p "$BASE/Cameras" "$BASE/Logs"
find "$BASE/Cameras" -type f -mtime +30 -delete
echo "Limpeza concluída em $(date)" >> "$BASE/Logs/cleanup.log"
echo "Limpeza concluída."
