# Open Home OS v14.2 — Camera Manager Diagnostics

Substitua no GitHub:

- `api/server.py`
- `public/index.html`
- `public/css/style.css`
- `public/js/app.js`
- `config/camera_profiles.json`

## Novidades

- diagnóstico RTSP direto com comandos `OPTIONS` e `DESCRIBE`;
- identificação do servidor RTSP, métodos públicos e autenticação;
- confirmação de credenciais e SDP antes do teste pesado com `ffprobe`;
- diagnóstico completo por dispositivo;
- recomendações claras na interface;
- suporte mantido para Yoosee e Xiaomi Xiao Fang;
- nenhum teste automático de senhas.

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
1. Diagnóstico RTSP;
2. Teste rápido;
3. Busca profunda;
4. Testar e adicionar.
