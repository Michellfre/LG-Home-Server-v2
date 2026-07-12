# Open Home OS v14.3 — Xiaomi Xiao Fang Support

Substitua no GitHub:

- `api/server.py`
- `public/index.html`
- `public/css/style.css`
- `public/js/app.js`
- `config/camera_profiles.json`

## Xiaomi adicionada

Dados usados no perfil:

- Modelo: Xiaomi Xiao Fang Smart Camera
- IP atual: `192.168.1.4`
- MAC: `34:CE:00:D1:60:F4`
- Prefixo reconhecido: `34:CE:00`

## Novidades

- identificação automática da Xiaomi Xiao Fang pelo MAC;
- perfil dedicado no Camera Manager;
- distinção entre firmware original e firmware modificado/Dafang;
- diagnóstico de portas 22, 80, 443, 554, 8554, 8080, 8000 e 8899;
- relatório de compatibilidade local;
- indicação de Mi Home, RTSP, ONVIF, HTTP e SSH;
- cartão específico da Xiao Fang no Camera Manager.

## Atualização

```bash
cd ~/LG-Home-Server-v2
git pull
pkg install ffmpeg
bash install.sh
nginx -s reload
bash scripts/start_api.sh
```

No Brave, use `Ctrl + F5`.
