#!/data/data/com.termux/files/usr/bin/bash

BASE="$HOME/Servidor"
mkdir -p "$BASE/Backups" "$BASE/Logs"

DATE=$(date '+%Y-%m-%d_%H-%M-%S')
BACKUP_FILE="$BASE/Backups/backup_$DATE.tar.gz"

tar -czf "$BACKUP_FILE" "$BASE/Cameras" "$BASE/Logs" 2>/dev/null

echo "Backup criado: $BACKUP_FILE"
echo "Backup criado em $(date): $BACKUP_FILE" >> "$BASE/Logs/backup.log"
