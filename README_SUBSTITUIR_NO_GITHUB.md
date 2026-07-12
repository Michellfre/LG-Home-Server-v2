# Open Home OS v14.0 — Camera Manager

Primeira etapa focada apenas nas câmeras.

Arquivos:
- api/server.py
- public/index.html
- public/css/style.css
- public/js/app.js
- config/camera_profiles.json

Instalação:

```bash
cd ~/LG-Home-Server-v2
git pull
pkg install ffmpeg
bash install.sh
nginx -s reload
bash scripts/start_api.sh
```

Depois use Ctrl + F5 no Brave.
