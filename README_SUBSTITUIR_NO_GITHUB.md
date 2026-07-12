# v13.6 Yoosee RTSP/ONVIF

Substitua no repositório:

- `api/server.py`
- `public/index.html`
- `public/css/style.css`
- `public/js/app.js`

Depois execute no Termux:

```bash
cd ~/LG-Home-Server-v2
git pull
pkg install ffmpeg
bash install.sh
nginx -s reload
bash scripts/start_api.sh
```

No Brave: `Ctrl + F5`.

Na câmera Yoosee, mantenha a conexão NVR/RTSP ativada e use a senha NVR/RTSP definida no aplicativo.
