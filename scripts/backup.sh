#!/data/data/com.termux/files/usr/bin/bash
BASE="$HOME/Servidor"; mkdir -p "$BASE/Backups"
DATE=$(date '+%Y-%m-%d_%H-%M-%S')
tar -czf "$BASE/Backups/backup_$DATE.tar.gz" "$BASE/Files" "$BASE/Cameras" 2>/dev/null
echo "Backup criado: backup_$DATE.tar.gz"
