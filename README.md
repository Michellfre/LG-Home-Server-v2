# LG Home Server v5

Servidor doméstico para Android usando Termux + Nginx + Python.

## Novidades

- API Python na porta 8090
- Gerenciador de arquivos pelo navegador
- Upload de arquivos
- Download de arquivos
- Exclusão de arquivos
- Listagem de câmeras, backups e arquivos
- Dashboard com status em tempo real

## Instalação

```bash
git pull
bash install.sh
nginx -s reload
bash scripts/start_api.sh
```
