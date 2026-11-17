# Relatório do que foi feito entre as etapas

Escrito para você ler depois. "Testado" = rodei e vi funcionar; "não testado" = escrevi/configurei mas não consegui verificar.

## Base (Etapas 1 e 2)
- Diagnóstico: Acer Aspire E1-471, i5-3230M, 8 GB, HD mecânico saudável, Windows 10 Home, Wi-Fi IP-DO-SERVIDOR.
- Instalei Python 3.12 e Git (winget, sem admin). Criei `alicia-server` com repositório Git, copiei a Alicia **sem** `.env`, `config.json` e banco (segredos). Venvs separados (`painel/.venv`, `alicia/.venv`) com versões fixadas. Testado: importação de todas as bibliotecas.

## Etapa 3 (servidor 24h) — parcial
- Energia: nunca suspende/hiberna na tomada; ação da tampa = nada (comando aplicado; o valor **não foi verificado** — teste fechando a tampa).
- Monitor de acessos (`scripts/monitor.py`) e painel sobem no logon por tarefas agendadas. Testado: você reiniciou e abriu. Corrigi a janela do PowerShell que aparecia.
- **Falta:** IP fixo, SSH/administração remota, login automático do Windows (precisa da sua senha).

## Etapa 7 (painel)
- Prévia estática aprovada por você (roxo). Painel real v1 em `http://IP-DO-SERVIDOR:8080/`: login com hash argon2 e bloqueio após 5 erros, status real, arquivos (enviar/baixar/lixeira), chave NVIDIA mascarada (testar/salvar), registros ao vivo. Testado: API por script. **Telas no navegador do painel real não foram vistas por mim.**

## Etapa 5 (arquivos e backup) — parcial
- Pasta de rede `\\IP-DO-SERVIDOR\AliciaServer` → `C:\AliciaServer\Alicia Server` (Documentos, Filmes, Séries, Jogos, Música). Wi-Fi marcado Privado, firewall só rede local. Backup diário 03:30 testado (mesmo HD — ideal copiar para outro disco).

## Etapa 6 (Hermes) — o que aconteceu
1. Instalador oficial leu-se antes (só GitHub/uv/PortableGit). Falhou na 1ª vez (link do Python do uv); limpei e repeti.
2. **Problema descoberto:** o Claude Desktop é app empacotado e o Windows redireciona o AppData dele, então o Hermes instalado ali ficava invisível para usuários normais. Reinstalei em `C:\AliciaServer\hermes` e rodei `hermes pm repair`.
3. O Hermes **recusa rodar como administrador**. Criei `scripts/rodar_normal.ps1` e `hermes_normal.ps1` para rodar como usuário normal.
4. Configurado provider `nvidia`, modelo `nvidia/nemotron-3-ultra-550b-a55b` (o mesmo que a Alicia usava; aparece no catálogo público).
5. Modelo falso (`scripts/modelo_falso.py`) imita a API da NVIDIA. Testado: Hermes respondeu; pela API do gateway (porta 8642, só local), duas mensagens na mesma sessão chegaram juntas ao modelo (continuidade de sessão ✓).
6. Gateway do Hermes sobe no logon (tarefa `AliciaServer-Hermes`). `scripts/sync_env.py` espelha o `.env` único do projeto para o `.env` do Hermes. Há `ALICIA_MODO_TESTE=1` (modelo falso) — **desligar no produto final**.
- **Não testado:** memória de longo prazo de verdade e tarefas agendadas (exigem modelo real chamando ferramentas), limites de permissão, API real.

## Etapa 8 (auditoria da Alicia)
- Primeiro audit foi na versão antiga; você enviou o zip novo. A base agora é o zip (tem poker, call, sem filtro). A cópia original em `server\alicia` nunca foi alterada.

## Etapas 3 e 4 (rede) — o que foi feito
- OpenSSH Server instalado e iniciando sozinho; firewall só rede local + faixa da rede privada (100.64.0.0/10). Para administrar do PC: `ssh <seu-usuario-windows>@IP-DO-SERVIDOR` (usa a senha do Windows). **Não testado de outro aparelho.**
- Tailscale instalado (serviço ligado). **Falta o login** (passo da lista final). Escolha: Tailscale em vez de WireGuard puro — conecta atrás do roteador sem abrir portas e tem app para Android/TV box (ver DECISOES.md).
- Nome do computador mudado para `alicia-server` (vale após o próximo reinício).
- IP fixo: **não** mudei o IP no Windows (arriscaria conflito com o DHCP do roteador). Recomendo reservar IP-DO-SERVIDOR para este notebook no roteador (passo na lista final).
- Atualizações automáticas: serviço do Windows Update está em modo Manual (padrão do Windows 10 Home); conferir em Configurações > Atualização.

## Etapa 13 (Jellyfin) — o que foi feito
- Jellyfin 12.4.0 instalado como serviço (inicia sozinho). O instalador mostrou um erro "não iniciou o serviço" porque o primeiro início demora ~35 s no notebook; o serviço está saudável (`/health` = Healthy).
- Assistente concluído por API: idioma pt-BR, usuário `admin` (senha em PRIMEIRO_ACESSO.txt), bibliotecas Filmes e Séries apontando para a pasta compartilhada.
- Conversão de vídeo: aceleração por hardware desligada (GPU HD 4000 não testada), 2 threads, uma conversão por vez com pausa automática (throttling), preset mais leve.
- Teste: gerei um vídeo de 10 s (H.264/AAC) em Filmes; o Jellyfin o listou e o stream direto funcionou (DirectPlay=True, sem conversão). **Não abri no navegador com os olhos.**
- Painel: cartão Filmes mostra o estado e abre o Jellyfin; acessos ao Jellyfin aparecem no monitor (JELLYFIN) via consulta a cada 20 s.
- Porta 8096 liberada só para rede local/privada.

## Etapas 9–17 em resumo (feitas depois do relatório acima)
- **9 Remoção de tela/Ollama:** apaguei screen, observer, local_vision/vlm, vision, hardware, envcheck e o código de consulta de tela; o app PyQt virou `desktop_legado/` (não roda). Dependências: só requests, Pillow e edge-tts. Testado: prompts, sem filtro e pôquer ainda importam.
- **10/11 Personalidade e junção:** o painel monta o prompt com as personalidades originais (Normal, Brincalhona, Séria, Malcriada, Carinhosa) e a camada "sem filtro" original, manda ao Hermes (API local) e devolve texto + expressão (imagem da Alicia). Testado com a chave real. Hermes do painel **sem terminal nem arquivos** (só web, skills, todo, agenda).
- **12 Atalhos:** `Alicia Server.url` na pasta compartilhada (PC); no celular abra o endereço no navegador → menu → "Adicionar à tela inicial".
- **14 Jogos, 15 Música, 16 RPG, 17 APK:** ver JOGOS.md, painel (páginas Música e RPG) e `alicia-apk/COMPILAR_NO_PC.md`.
- **Chave NVIDIA:** você a salvou pelo painel às 04:03; o teste de chave agora faz uma chamada real mínima (a lista de modelos é pública e dava "ok" até com chave errada).
