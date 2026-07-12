# Open Home OS v14.6.2 — Dashboard Camera Refresh

Esta correção resolve a atualização das miniaturas e reduz o tamanho dos cartões no Dashboard.

## Arquivos para substituir

- `api/server.py`
- `public/index.html`
- `public/js/app.js`
- `public/css/style.css`

## Melhorias

- botão “Atualizar todas” força uma nova leitura das câmeras;
- cada miniatura usa uma captura nova, sem reutilizar imagem antiga;
- atualização automática a cada 30 segundos;
- atualização imediata ao abrir o Dashboard;
- indicação visual de câmera online/offline;
- cartões menores, com largura aproximada de 190–230 px;
- botões compactos “Ao vivo” e “Atualizar”.

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
