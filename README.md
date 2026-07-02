# LG Home Server v4

Servidor doméstico para Android usando Termux + Nginx + Python.

## Novidades da v4

- Dashboard melhorado
- API local em Python
- Gerenciador de arquivos básico
- Listagem de pastas pelo navegador
- Status do sistema via API
- Estrutura preparada para câmeras Yoosee/RTSP
- Scripts de instalação, atualização, backup e diagnóstico

## Instalação

No Termux:

```bash
git pull
bash install.sh
nginx -s reload
bash scripts/start_api.sh
```

Acesse:

```text
http://IP_DO_CELULAR:8080
```

## API

A API roda na porta:

```text
http://IP_DO_CELULAR:8090
```
