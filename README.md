# Open Home OS v13.5 RTSP Camera Setup

Adiciona um assistente para câmeras detectadas na porta 554:

- formulário de nome, ambiente, usuário, senha e caminho RTSP;
- teste com `ffprobe`;
- tentativa de caminhos RTSP comuns usando somente as credenciais informadas pelo proprietário;
- gravação da câmera apenas quando o stream for validado;
- botão correto para câmera RTSP, sem tentar abrir a porta 5000 como página Web.

Dependência no Termux:

```bash
pkg install ffmpeg
```
