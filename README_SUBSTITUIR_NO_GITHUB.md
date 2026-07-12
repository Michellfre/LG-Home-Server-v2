# Open Home OS v14.1 — Camera Manager Pro

Substitua no GitHub:

- `api/server.py`
- `public/index.html`
- `public/css/style.css`
- `public/js/app.js`
- `config/camera_profiles.json`

## Melhorias

- teste RTSP por TCP, UDP e modo automático;
- teste rápido e busca profunda;
- mais caminhos conhecidos para Yoosee;
- classificação de erros de autenticação, transporte, conexão e caminho;
- resultado visual amigável;
- detalhes técnicos recolhidos em uma seção expansível;
- salvamento do transporte que funcionou.

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
