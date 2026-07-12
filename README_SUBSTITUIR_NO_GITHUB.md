# Open Home OS v14.4 — Camera Manager Learning

Esta versão aprende a configuração que funcionou e evita repetir dezenas de testes.

Substitua no GitHub:

- `api/server.py`
- `public/index.html`
- `public/css/style.css`
- `public/js/app.js`
- `config/camera_profiles.json`

## Melhorias

- memoriza caminho e transporte RTSP por IP, porta e perfil;
- prioriza automaticamente `/onvif2` por UDP após validação;
- preenche o caminho encontrado na tela;
- adiciona a câmera sem repetir toda a busca profunda;
- salva codec, resolução, transporte e data do último teste;
- remove credenciais das mensagens técnicas;
- adiciona snapshot JPEG no Camera Manager;
- botão “Atualizar imagem” em cada câmera cadastrada.

## Atualização no Termux

```bash
cd ~/LG-Home-Server-v2
git pull
pkg install ffmpeg
bash install.sh
nginx -s reload
bash scripts/start_api.sh
```

No Brave: `Ctrl + F5`.

Fluxo recomendado:
1. Teste rápido;
2. quando aparecer “Vídeo encontrado”, clique em “Testar e adicionar”;
3. abra “Câmeras”;
4. clique em “Atualizar imagem”.
