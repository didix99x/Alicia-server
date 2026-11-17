# Problemas

- Sem admin na sessão: configurar energia, serviços e firewall (Etapa 3) exige abrir o terminal como Administrador.
- Sem Python/Git no PATH em terminais já abertos: abra um novo terminal.

## Problemas comuns (como resolver)
- **Painel não abre** (`http://IP-DO-SERVIDOR:8080`): faça login no Windows (o painel sobe no logon). Se ainda assim não abrir: abra o PowerShell e rode `Start-ScheduledTask AliciaServer-Painel`.
- **Monitor de acessos não abriu**: `Start-ScheduledTask AliciaServer-Monitor`. Ele só abre depois do login no Windows (login automático não configurado: exige sua senha — ver DECISOES.md).
- **Alicia diz "ainda não tem cérebro"**: falta a chave da NVIDIA (Configurações) ou o Hermes está parado (`Start-ScheduledTask AliciaServer-Hermes`; leva ~1 min).
- **Chave inválida / cota acabou**: o botão "Testar chave" diz qual dos dois; gere outra em https://build.nvidia.com.
- **Hermes "recusa rodar como administrador"**: normal; use `scripts\hermes_normal.ps1`.
- **Jellyfin parado**: `Restart-Service JellyfinServer` (administrador). No primeiro início ele demora ~35 s.
- **Jogo trava/atrasa**: veja JOGOS.md. **Sunshine parado**: `Restart-Service SunshineService`.
- **Disco cheio / HD com problema**: o painel e o monitor avisam. Libere espaço (lixeira do painel em `Alicia Server\.lixeira`) e copie o backup (`C:\AliciaServer\Backup`) para outro disco.
- **Sem acesso de fora de casa**: faça o login do Tailscale no notebook (`tailscale up`), no PC, no celular e na TV box com a MESMA conta; use o IP 100.x do notebook.
- **A música não toca**: é preciso um link do YouTube; o player abre uma janela do Edge no notebook (precisa de alguém logado no Windows).
- **`C:\cores`**: uma pasta vazia criada por engano na instalação; pode apagar à mão.

- **Jellyfin pedindo usuário/senha de novo:** o login automático do usuário 'casa' é um pequeno script (C:\Program Files\Jellyfin\Server\jellyfin-web\alicia-autologin.js, ligado no index.html; o original está em index.html.original). Uma atualização do Jellyfin pode apagar essa ligação: copie de volta o index.html.original + a linha <script src="alicia-autologin.js"></script> logo depois de <head>. Para entrar como administrador abra http://IP-DO-SERVIDOR:8096/?manual=1.
- **Bibliotecas duplicadas no Jellyfin (Filmes2, Séries2):** são restos de um teste; apague pelo Jellyfin (Painel → Bibliotecas → remover). Não apagam seus arquivos.

- **Ninguém consegue entrar (erro 500 no login):** o arquivo `painel/usuarios.json` pode ter ficado com um caractere invisível no começo se foi editado no Bloco de Notas/PowerShell. O painel já tolera isso; se persistir, recrie o usuário com `painel\.venv\Scripts\python.exe scripts\criar_usuario.py SEU_NOME --admin`.
- **Visitante não consegue entrar:** o administrador pode ter desligado em Configurações → Entrada de visitante.
- **Esqueci a senha do administrador:** rode `painel\.venv\Scripts\python.exe scripts\criar_usuario.py SEU_NOME NOVA_SENHA --admin` no notebook.
## Só alguns jogos de PlayStation aparecem

Jogos em .rar são convertidos sozinhos ao abrir a aba Jogos. Se algum não aparecer, veja se há um aviso de **senha** na aba (digite a senha) ou se o arquivo ficou como .rar.erro (estava corrompido ou sem .bin/.cue dentro). Veja [JOGOS.md](JOGOS.md).
