# LG Home Server v3.2

Servidor doméstico para Android usando Termux + Nginx.

## Esta versão corrige

- Pasta `scripts` ausente
- Atualização de status
- Instalação incompleta
- Estrutura do projeto

## Recursos

- Dashboard web
- Status em JSON
- IP local
- Status do Nginx
- Espaço livre
- Contagem de arquivos de câmeras
- Contagem de backups
- Logs
- Scripts de backup, limpeza e preparação de câmeras

## Instalação

```bash
bash install.sh
nginx -s reload
```

## Atualização

```bash
git pull
bash update.sh
```

## Atualizar status manualmente

```bash
bash scripts/update_status.sh
```
