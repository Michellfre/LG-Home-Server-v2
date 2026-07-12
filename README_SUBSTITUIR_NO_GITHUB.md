# Open Home OS v14.6 — Vídeo ao Vivo MJPEG

Esta versão troca a sequência de snapshots por uma transmissão MJPEG contínua.

## Arquivos para substituir

- `api/server.py`
- `public/index.html`
- `public/css/style.css`
- `public/js/app.js`

## O que foi adicionado

- endpoint `/api/cameras/live.mjpeg`;
- vídeo contínuo no Brave sem abrir RTSP diretamente;
- FFmpeg converte RTSP para MJPEG;
- transporte salvo da câmera, como `/onvif2` via UDP;
- reconexão;
- pausar/continuar;
- tela cheia;
- servidor HTTP multithread para o vídeo não bloquear a API.

## Atualização no Termux

```bash
cd ~/LG-Home-Server-v2
git pull
pkg install ffmpeg
bash install.sh
nginx -s reload
pkill -f server.py
bash scripts/start_api.sh
```

No Brave, pressione `Ctrl + F5`.

## Uso

1. Abra o Dashboard ou a página Câmeras.
2. Clique em **Ver ao vivo**.
3. Use **Reconectar** caso a câmera perca a conexão.
