# Open Home OS v13.6 — Yoosee RTSP/ONVIF

Arquivos para substituir no GitHub:

- `api/server.py`
- `public/index.html`
- `public/css/style.css`
- `public/js/app.js`

## Alterações

- Perfil RTSP específico para Yoosee.
- Novos caminhos comuns: `/onvif1`, `/onvif2`, `/live/ch00_0`, `/live/ch00_1`,
  `/h264/ch1/main/av_stream`, `/11`, `/12` e outros.
- Diagnóstico claro para erro `401 Unauthorized`.
- Botão **Detectar ONVIF**.
- A câmera só é adicionada depois que o `ffprobe` valida o vídeo.
- O sistema não tenta adivinhar ou descobrir senhas.

## Instalação no Termux

```bash
cd ~/LG-Home-Server-v2
git pull
pkg install ffmpeg
bash install.sh
nginx -s reload
bash scripts/start_api.sh
```

Depois faça `Ctrl + F5` no Brave.
