# LG Home Server v5.1

Correção da API para Python 3.13.

## Correção principal

A versão anterior usava o módulo `cgi`, que foi removido do Python 3.13.  
Esta versão remove essa dependência e usa um parser interno simples para upload.

## Instalação

```bash
git pull
bash install.sh
nginx -s reload
bash scripts/start_api.sh
```

## Teste da API

```bash
curl http://127.0.0.1:8090/api/status
```
