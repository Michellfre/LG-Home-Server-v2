#!/data/data/com.termux/files/usr/bin/bash
echo "LG Home Server - Status"
date
echo ""
ip addr show wlan0 | grep "inet "
echo ""
df -h "$HOME"
echo ""
pgrep nginx >/dev/null && echo "Nginx: Ativo" || echo "Nginx: Parado"
