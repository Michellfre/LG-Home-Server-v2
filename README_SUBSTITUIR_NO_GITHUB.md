# Open Home OS v13.5.1 — Correção da janela RTSP

Substitua no repositório estes três arquivos:

- `public/index.html`
- `public/css/style.css`
- `public/js/app.js`

Depois, no Termux:

```bash
cd ~/LG-Home-Server-v2
git pull
bash install.sh
nginx -s reload
bash scripts/start_api.sh
```

No Brave, atualize sem cache com `Ctrl + F5`.

A janela agora fecha de quatro formas:

1. Botão **X**;
2. clique na área escura fora da janela;
3. tecla **Esc**;
4. fechamento automático depois que a câmera é adicionada.

O `z-index` foi elevado acima de todo o dashboard e o fundo da janela ficou opaco.
