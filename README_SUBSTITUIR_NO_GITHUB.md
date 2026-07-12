# Open Home OS v14.6.4 — Camera Center Fix

Corrige o erro:

```text
fetchCameraSnapshot is not defined
```

## O que mudou

- criada uma biblioteca única `CameraCenter`;
- Dashboard, página Câmeras e vídeo ao vivo passam a usar as mesmas funções;
- adicionada compatibilidade com chamadas antigas por `fetchCameraSnapshot`;
- corrigida atualização das miniaturas;
- mensagens reais do backend continuam sendo exibidas;
- cartões do Dashboard ficaram um pouco menores;
- exclusão da câmera também atualiza o Dashboard.

## Arquivos para substituir

- `api/server.py`
- `public/index.html`
- `public/js/app.js`
- `public/css/style.css`

## Atualização no Termux

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

Depois abra o Dashboard e clique em **Atualizar todas**.
