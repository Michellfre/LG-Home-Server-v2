# Open Home OS v14.8 — Biblioteca de Gravações

## Novidades

- seletor visual de pasta;
- navegação por armazenamento interno, SD Card e pastas permitidas;
- botão “Selecionar esta pasta”;
- exibição do espaço livre;
- nova página **Gravações** no menu lateral;
- busca por câmera, ambiente ou nome do arquivo;
- filtro por data e câmera;
- reprodução integrada no navegador;
- suporte a avanço do vídeo por Range HTTP;
- exclusão de gravações pela interface.

## Arquivos para substituir

- `api/server.py`
- `public/index.html`
- `public/js/app.js`
- `public/css/style.css`

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

No Brave:

```text
Ctrl + Shift + R
```
