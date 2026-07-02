#!/data/data/com.termux/files/usr/bin/bash

echo "LG Home Server - Diagnóstico"
echo "-----------------------------"
echo "Pasta atual: $(pwd)"
echo "Home: $HOME"
echo ""
echo "Arquivos do projeto:"
ls
echo ""
echo "Pasta scripts:"
ls scripts 2>/dev/null || echo "scripts não encontrada"
echo ""
echo "Pasta Web:"
ls "$HOME/Servidor/Web" 2>/dev/null || echo "Web não encontrada"
echo ""
echo "Nginx:"
pgrep nginx >/dev/null && echo "Ativo" || echo "Parado"
echo ""
echo "IP:"
ip addr show wlan0 2>/dev/null | awk '/inet / {print $2}'
