# Open Home OS v14.6.1 — Camera Dashboard Hotfix

Esta correção resolve dois problemas da v14.6:

- o Dashboard mostrava “Nenhuma câmera adicionada” mesmo com câmera cadastrada;
- a página Câmeras não exibia o botão “Ver ao vivo”.

## Arquivos para substituir

- `api/server.py`
- `public/index.html`
- `public/js/app.js`

## Atualização

```bash
cd ~/LG-Home-Server-v2
git pull
bash install.sh
nginx -s reload
pkill -f server.py
bash scripts/start_api.sh
```

No Brave, pressione `Ctrl + Shift + R` ou `Ctrl + F5`.

Depois:
1. abra o Dashboard;
2. clique em “Atualizar todas”;
3. clique em “Ver ao vivo”.
