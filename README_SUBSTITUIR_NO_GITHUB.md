# Open Home OS v14.5 — Dashboard Cameras Live

Substitua no GitHub:

- `api/server.py`
- `public/index.html`
- `public/css/style.css`
- `public/js/app.js`

## Novidades

- miniaturas das câmeras adicionadas no Dashboard;
- atualização automática das miniaturas;
- botão “Ver ao vivo”;
- janela ampliada da câmera;
- atualização contínua de frames compatível com Brave;
- pausar/continuar;
- tela cheia;
- botão para atualizar todas as miniaturas.

> O modo ao vivo desta versão usa quadros JPEG sucessivos.
> Isso funciona no navegador sem abrir RTSP diretamente.
> Uma versão futura poderá usar HLS/WebRTC para vídeo mais fluido.

## Atualização

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
