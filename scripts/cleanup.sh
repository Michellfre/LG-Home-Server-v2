#!/data/data/com.termux/files/usr/bin/bash
find "$HOME/Servidor/Cameras" -type f -mtime +30 -delete
echo "Limpeza concluída em $(date)" >> "$HOME/Servidor/Logs/cleanup.log"
