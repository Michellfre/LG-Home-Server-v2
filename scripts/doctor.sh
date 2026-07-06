#!/data/data/com.termux/files/usr/bin/bash
echo "Open Home OS v13.2 Diagnóstico"
echo "IP: $(ip -o -4 addr show 2>/dev/null | awk '!/127.0.0.1/ {split($4,a,"/"); print a[1]; exit}')"
echo "Gateway: $(ip route | awk '/default/ {print $3; exit}')"
echo "Vizinhos ARP:"; ip neigh show
echo "API status:"; curl -s http://127.0.0.1:8090/api/status | head -c 1000; echo
echo "API log:"; tail -120 ~/OpenHomeOS/Logs/api.log 2>/dev/null
