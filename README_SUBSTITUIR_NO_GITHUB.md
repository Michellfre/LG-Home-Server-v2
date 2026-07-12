# Open Home OS v14.7.1 — Recording Storage Selector

Adiciona a escolha do local de salvamento das gravações.

## Novidades

- lista locais de armazenamento detectados;
- permite selecionar armazenamento interno, SD Card ou pasta personalizada;
- campo para informar um caminho manual;
- botão **Testar pasta**;
- verifica permissão de escrita;
- informa espaço livre e capacidade total;
- salva o caminho escolhido nas configurações;
- cada câmera continua recebendo sua própria subpasta.

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

## Exemplo de pasta no SD Card

```text
/storage/94D4-9BC3/OpenHomeRecordings
```

O caminho exato pode mudar conforme o cartão instalado no Android.
