# Open Home OS v14.6.3 — Dashboard Image Fix

Corrige a mensagem “Falha ao atualizar” nas miniaturas do Dashboard.

## Causa corrigida

A imagem em Base64 recebia um fragmento de cache (`#data`), o que podia tornar o JPEG inválido no navegador.

## Arquivos para substituir

- `api/server.py`
- `public/index.html`
- `public/js/app.js`

## Outras melhorias

- captura FFmpeg mais tolerante a streams UDP;
- maior tempo de análise do RTSP;
- mensagem real do erro exibida no cartão.

## Atualização

```bash
cd ~/LG-Home-Server-v2
git pull
bash install.sh
nginx -s reload
pkill -f server.py
bash scripts/start_api.sh
```

No Brave:

```text
Ctrl + Shift + R
```

Depois clique em **Atualizar** na miniatura.
