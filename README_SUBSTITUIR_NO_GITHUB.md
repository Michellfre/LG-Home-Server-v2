# Open Home OS v14.7 — Camera Recording

Adiciona gravação manual das câmeras RTSP no armazenamento do servidor.

## Recursos

- botão **Gravar**;
- botão **Parar**;
- arquivos MP4 divididos em segmentos;
- configuração de 1, 5, 10 ou 30 minutos por arquivo;
- retenção em dias;
- limite máximo de armazenamento;
- limpeza automática/manual de gravações antigas;
- listagem dos arquivos gravados por câmera;
- gravação usa o transporte salvo, como UDP para Yoosee;
- vídeo é copiado sem recodificação quando possível, reduzindo uso de CPU.

## Arquivos para substituir

- `api/server.py`
- `public/index.html`
- `public/js/app.js`
- `public/css/style.css`

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

No Brave:

```text
Ctrl + Shift + R
```

## Onde ficam as gravações

```text
~/LG-Home-Server-v2/recordings/
```

Cada câmera recebe sua própria pasta.
