# Segurança e privacidade

O Alicia Server guarda arquivos pessoais e fala com uma API externa. Estas são as regras e como elas são cumpridas.

## Princípios

1. **Nada exposto na internet.** Nenhuma porta é aberta no roteador. O acesso de fora de casa é feito pela rede privada **Tailscale**.
2. **Sempre com login** (exceto o botão "Entrar como visitante", que dá acesso limitado).
3. **Segredos só em `.env`**, fora do Git, com permissão restrita ao usuário.
4. **Mínimo privilégio:** cada parte só pode o que precisa.
5. **Privacidade nos registros:** quem, quando, de onde e o quê; **nunca** senhas, chaves, tokens, nem o conteúdo de arquivos ou de conversas.

## O que protege o quê

| Risco | Proteção |
|---|---|
| Acesso vindo da internet | Sem portas abertas; firewall do Windows libera 8080, 8096, SSH e SMB **apenas** para `LocalSubnet` e `100.64.0.0/10` (Tailscale) |
| Senha fraca/roubada | Senhas com **Argon2**; **5 erros seguidos bloqueiam o IP por 5 minutos**; cada erro vira alerta no monitor |
| Sessão roubada | Cookie assinado, `HttpOnly`, `SameSite=Lax`; 14 dias (visitante: 24 h) |
| Visitante entrando onde não deve | **Middleware no servidor** bloqueia `/api/arquivos`, `/api/logs`, `/api/nvidia`, `/api/usuarios`, `/api/hermes`, `/api/verificar`, `/api/filmes/enviar`, `/api/alicia/*` (conversa, voz, música); o administrador desliga a entrada de visitantes a qualquer hora |
| Vazar dados pela Alicia | Visitantes não conversam com ela (a memória do Hermes é compartilhada) |
| Hermes mexer no sistema | O Hermes do painel só tem `web`, `skills`, `todo` e `cronjob`: **sem terminal e sem arquivos**; roda como usuário normal (ele recusa administrador) |
| Sair da pasta de dados | Toda rota de arquivos resolve o caminho e recusa o que estiver fora da pasta; tentativa de `../` retorna erro |
| Apagar sem querer | "Apagar" move para a **lixeira**; pastas principais são protegidas; confirmação antes |
| Chave da NVIDIA vazar | Fica só no `.env` (ACL do Windows); mascarada no painel; nunca em código, log, README ou mensagem de erro; `.gitignore` bloqueia `.env` |
| API local do Hermes | Escuta só em `127.0.0.1` e exige chave interna |
| Upload indevido | O envio de filmes e séries só aceita extensões de vídeo e legenda; o envio de arquivos é exclusivo dos moradores (o visitante é bloqueado); caminhos são validados |
| Disco falhando | O monitor confere a saúde do HD a cada hora e alerta no painel (o backup depende dele) |

## O que **não** está protegido (decisões conscientes)

- **O visitante entra sem senha.** Qualquer pessoa na sua rede de casa ou na sua conta Tailscale pode usar Jogos, Música, Filmes e RPG. Desligue em Configurações se não quiser.
- **O usuário `casa` do Jellyfin não tem senha.** Quem alcança a porta 8096 (rede de casa/Tailscale) assiste como `casa`. Ele não é administrador.
- **Login automático do Windows** (opcional, para subir tudo após um reinício) deixa o computador abrir sem senha para quem tiver acesso físico a ele.
- **Pasta de rede:** o Windows exige conta com senha; sem ela, ela fica inacessível (o que é seguro, mas incômodo).
- **Música:** o servidor baixa áudio do YouTube, o que contraria os termos de uso do serviço. Responsabilidade do dono.
- **Backup no mesmo HD** não protege contra falha do disco: copie para outro lugar.

## Enviando para o GitHub com segurança

- O `.gitignore` exclui `.env`, `usuarios.json`, `.segredo`, `PRIMEIRO_ACESSO.txt`, `dados/`, `logs/`, ambientes virtuais, chaves (`*.jks`, `keystore.properties`), mídia, jogos e bancos de dados.
- As capturas de tela do repositório usam **dados de exemplo** (`scripts/demo`), nunca o servidor real.
- Antes de publicar, rode uma busca por segredos e endereços pessoais (veja `docs/ETAPAS.md`).
- Se uma chave for exposta por engano, **troque-a** (gere outra em <https://build.nvidia.com> e salve de novo pelo painel).
