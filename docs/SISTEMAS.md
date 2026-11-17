# Os sistemas do Alicia Server

Cada sistema abaixo explica **o que faz**, **como funciona por dentro**, **onde ficam os dados** e **limites conhecidos**. Para o passo a passo de instalação veja [INSTALACAO.md](INSTALACAO.md); para a visão geral, [ARQUITETURA.md](ARQUITETURA.md).

Índice: [1 Painel](#1-painel-web) · [2 Login e visitante](#2-login-usuários-e-visitante) · [3 Alicia](#3-alicia) · [4 Hermes](#4-hermes-agent-o-cérebro) · [5 Arquivos e backup](#5-arquivos-e-backup) · [6 Filmes e séries](#6-filmes-e-séries-jellyfin) · [7 Jogos](#7-jogos-no-navegador) · [8 Música](#8-música) · [9 RPG](#9-rpg-com-a-alicia-como-mestra) · [10 Monitor e registros](#10-monitor-de-acessos-e-registros) · [11 Servidor 24 h](#11-servidor-24-horas) · [12 Rede privada](#12-rede-privada-e-administração-remota) · [13 App Android](#13-app-android)

---

## 1. Painel web

**O que é:** a porta de entrada. Um servidor **FastAPI** (porta 8080) que entrega uma interface em HTML/CSS/JavaScript puro e expõe a API usada por ela. Foi escrito sem framework de interface de propósito: o trabalho visual fica no navegador e o notebook quase não sente.

**Páginas:** Início · Alicia · Arquivos · Filmes · Jogos · Música · RPG · Servidor · Registros · Configurações.

**Recursos da interface**
- **Tema escuro** com três cores de destaque (roxo, rosa, verde-água).
- **Busca no topo** (tecla `/`): páginas, jogos, músicas e artistas.
- **Tour** no primeiro acesso (pode pular e rever pelo botão ❓).
- **Modo TV** (📺): letras maiores e navegação pelas setas e OK do controle remoto.
- **Escala automática**: em monitor grande, ultrawide ou TV a interface inteira cresce junto (tudo em `rem`) e o conteúdo fica centralizado.
- **Celular**: barra de abas embaixo (Início, Alicia, Filmes, Jogos, Música e "Mais").
- **Player de música persistente**: mora acima das páginas, então a música continua quando você troca de página ou abre um jogo.
- **Erros claros**: o painel sempre diz o que aconteceu e o que fazer; ações perigosas pedem confirmação.

**Arquivos:** `painel/app/main.py` (API), `painel/app/web/` (interface). A interface está separada em `index.html` (estrutura), `app.css` (visual), `app.js` (base, login, início, busca, tour, modo TV), `p_a.js` (Alicia, Arquivos, Servidor, Registros, Configurações) e `p_b.js` (Filmes, Jogos, Música, RPG).

---

O fundo do painel é uma camada fixa feita só com gradientes CSS (aurora animada ou estrelas), sem imagens; as cores seguem a cor de destaque escolhida em Configurações.

## 2. Login, usuários e visitante

- **Senhas** guardadas com **Argon2** (`argon2-cffi`); sessão em cookie assinado (`itsdangerous`), `HttpOnly`, válida por 14 dias.
- **Bloqueio por tentativas:** 5 senhas erradas seguidas bloqueiam o IP por 5 minutos (e isso aparece no monitor como evento de segurança).
- **Usuários:** o administrador cria, apaga e troca senhas em *Configurações*. Também há `scripts/criar_usuario.py`.
- **Visitante:** botão **"Entrar como visitante"** na tela de entrada, sem senha, sessão de **24 horas**.
  - Usa **Jogos, Música, Filmes e RPG**.
  - **Não** vê Arquivos, Servidor, Registros, Configurações nem a Alicia.
  - O bloqueio é feito **no servidor** por um *middleware* (rotas `/api/arquivos`, `/api/logs`, `/api/nvidia`, `/api/usuarios`, `/api/hermes`, `/api/alicia/conversar`, `/api/alicia/voz`, `/api/alicia/musica`, `/api/verificar`, `/api/filmes/enviar`…). Esconder o botão não bastaria.
  - O administrador liga/desliga a entrada de visitante em *Configurações*; ao desligar, as sessões de visitante caem na hora.
  - Todo acesso de visitante aparece nos **Registros**.
- **Dados:** `painel/usuarios.json` (fora do Git), `painel/.segredo` (chave dos cookies, fora do Git).

---

## 3. Alicia

**O que é:** a assistente. Mantém o conceito do projeto original: expressiva, analítica, espontânea e um pouco sarcástica quando o contexto permite.

**Como funciona**
1. O painel monta o **prompt do sistema** com o texto original da personalidade (`alicia/alicia_core/prompts.py`), o **jeito** escolhido e, se ligado, a camada **sem filtro**.
2. Manda ao **Hermes** (cérebro) pela API local, numa sessão por usuário (por isso ela lembra da conversa).
3. A resposta começa com uma tag de expressão (`[FELIZ]`, `[SERIO]`, `[SURPRESA]`, `[PENSANDO]`, `[BRAVO]`); o painel troca a imagem da Alicia de acordo.

**Jeitos (personalidades de tom):** Normal, Brincalhona, Séria, Malcriada e Carinhosa.

**Modo sem filtro:** uma **camada extra** de personalidade (rebelde e debochada), que liga e desliga sem substituir a personalidade original (`unfiltered.py`). Tem limites que valem sempre e uma detecção de sofrimento real do usuário: nesse caso a camada rebelde é trocada por acolhimento.

**Voz:** voz neural feminina **pt-BR-FranciscaNeural** (a mesma do projeto original), gerada no servidor com `edge-tts`. O ritmo e o tom mudam conforme a emoção (feliz, séria, surpresa, pensando, brava). Sem internet, o painel usa a voz do navegador, sempre escolhendo uma voz feminina. Cada fala tem um botão 🔊 para ouvir de novo. A música abaixa enquanto a Alicia fala.

**Música por pedido:** no chat, "toca Linkin Park", "coloca algo animado", "quero ouvir…". Ela procura primeiro na sua biblioteca (e toca o artista inteiro, embaralhado); se não houver, busca no YouTube. A música **começa na hora** e a Alicia comenta logo em seguida. Entende também **pausa, continua, próxima, anterior, aumenta/abaixa o volume** e **"que música é essa?"** (esses comandos não gastam a IA).

**Análise do servidor:** a Alicia **lê o estado real do servidor** a cada conversa (só leitura). O painel entrega a ela, junto da mensagem, um bloco com dados medidos naquele instante: processador, memória, disco, serviços, chave da NVIDIA e, quando a pergunta é sobre o servidor (disco, memória, lento, acessos, segurança, backup, "está tudo bem?"…), também os programas que mais gastam memória, a saúde do HD (SMART), a biblioteca, o último backup e o resumo das últimas 24 h do monitor (logins, senhas erradas, erros, eventos de segurança e os mais recentes). Ela responde com esses números, diz o que está bom, o que preocupa e o que fazer, e **não altera nada sozinha**.

**Sem chave da NVIDIA:** o painel e tudo que não usa IA funcionam; a Alicia mostra "A Alicia ainda não tem cérebro. Coloque a chave da NVIDIA em Configurações."

**Modo de teste:** com `ALICIA_MODO_TESTE=1` o Hermes conversa com um **modelo falso** (`scripts/modelo_falso.py`), útil para testar sem gastar a API.

**Visitantes não usam a Alicia**, porque o Hermes tem memória compartilhada.

---

## 4. Hermes Agent (o cérebro)

- **O que é:** o [Hermes Agent](https://github.com/NousResearch/hermes-agent) da Nous Research: memória entre sessões, skills que ele cria e melhora, ferramentas, subagentes e tarefas agendadas.
- **Modelo:** usa a **API da NVIDIA (NIM)** pelo provedor `nvidia` (modelo `nvidia/nemotron-3-ultra-550b-a55b`). Nada de modelo local: o notebook é fraco.
- **Como roda:** o *gateway* do Hermes fica em `127.0.0.1:8642` (só local) com uma chave interna; o painel conversa com ele por HTTP. Uma tarefa agendada mantém o gateway ligado.
- **Importante:** o Hermes **recusa rodar como administrador**. Por isso `scripts/hermes_normal.ps1` e `scripts/rodar_normal.ps1` existem: rodam comandos dele como usuário normal.
- **Permissões limitadas:** o Hermes acessado pelo painel só tem as ferramentas `web`, `skills`, `todo` e `cronjob`. **Não tem terminal nem acesso a arquivos**, então não pode apagar seus arquivos nem mexer no sistema.
- **Uma chave só:** o `.env` do projeto é a fonte. `scripts/sync_env.py` espelha as variáveis para o `.env` do Hermes. Ao salvar uma chave nova pelo painel, o espelho é feito e o gateway reinicia sozinho.
- **Painel:** a página Servidor mostra as skills e as tarefas agendadas do Hermes e tem o botão de reiniciar (administrador).

---

## 5. Arquivos e backup

- **Pasta compartilhada** `Alicia Server` com `Documentos`, `Filmes`, `Séries`, `Jogos` e `Música`. Pode ser montada como unidade de rede no PC (compartilhamento `AliciaServer`).
- **Pela interface:** navegar com **miniaturas**, **prévia** de imagem, vídeo, áudio, PDF e texto, **enviar** arrastando (com barra de progresso, bom para arquivos grandes), **baixar**, **nova pasta** e **apagar**.
- **Apagar vai para a lixeira** (`.lixeira`), nunca some de vez; as pastas principais não podem ser apagadas.
- **Segurança de caminhos:** toda rota de arquivos resolve o caminho e recusa qualquer coisa fora da pasta de dados.
- **Backup:** tarefa diária às 03:30 (`scripts/backup.cmd`) copia `Documentos` e a configuração do servidor para `Backup`. **Atenção:** se o backup ficar no mesmo disco, ele não protege contra falha do HD; copie para outro disco.

---

## 6. Filmes e séries (Jellyfin)

- **Jellyfin** instalado como serviço do Windows, com as bibliotecas `Filmes` e `Séries` apontando para a pasta compartilhada.
- **Dentro do painel:** a página **Filmes** mostra o Jellyfin em tela cheia, dentro de um quadro. Assim o app Android precisa conhecer só um endereço.
- **Login sem senha:** o usuário `casa` (não administrador) entra sozinho. Isso é feito por um pequeno script no `jellyfin-web` (`alicia-autologin.js`). Para entrar como administrador abra `…:8096/?manual=1`.
- **Adicionar filmes e séries:** botão **➕ Adicionar** na página Filmes. O painel organiza as pastas no padrão do Jellyfin (`Nome do Filme (2010)/…` e `Série/Season 01/…`) e pede a atualização da biblioteca.
- **Conversão de vídeo (CPU fraca):** prioriza **reprodução direta**; a conversão fica em software, 2 threads e com pausa automática (*throttling*). A aceleração por hardware da placa integrada não foi ativada.
- **Registro:** quem assistiu o quê, em qual aparelho e se houve conversão aparece no monitor (consulta a cada 20 s).

---

## 7. Jogos no navegador

**Como funciona:** o emulador ([EmulatorJS](https://github.com/EmulatorJS/EmulatorJS)) roda **no navegador de quem joga**; o servidor só entrega o arquivo do jogo e guarda o progresso. Por isso o notebook não pesa e não é preciso instalar nada em celular, PC ou TV box.

| Console | Núcleo | Extensões |
|---|---|---|
| Nintendo | fceumm | `.nes` |
| Super Nintendo | snes9x | `.sfc` `.smc` |
| Nintendo 64 | mupen64plus_next | `.z64` `.n64` `.v64` |
| Game Boy / Game Boy Color | gambatte | `.gb` `.gbc` |
| Game Boy Advance | mgba | `.gba` |
| PlayStation | pcsx_rearmed | `.cue` `.chd` `.iso` `.pbp` (BIOS em `Jogos/BIOS`) |

- **Biblioteca em blocos** por console, com **busca** e capas opcionais (uma imagem com o mesmo nome do jogo).
- **Organização automática:** o painel olha o **arquivo** (inclusive o que há dentro de um `.zip`) e move o jogo para a pasta do console certo.
- **Adicionar jogos** pelo painel (a pasta de rede não é necessária).
- **Progresso salvo no servidor:** estado do jogo a cada 2 minutos, ao pausar/sair e ao usar "salvar"; na próxima vez o jogo abre de onde parou, **em qualquer aparelho**. Os saves ficam em `Jogos/Saves/<usuário>/<console>/`.
- **Controles:** teclado, controle Bluetooth/USB (API de gamepad do navegador) e botões na tela no celular; setas e OK navegam pela biblioteca na TV box.
- **Jogo em camada:** o jogo abre numa camada dentro do painel; por isso a **música continua tocando** enquanto você joga.
- **Sem jogos nem BIOS no repositório:** você coloca os seus, de jogos que tem.

Guia do usuário: [JOGOS.md](JOGOS.md).

---

### Favoritos, capas e emuladores

- **Favoritos:** a ☆ em cada jogo guarda o título na lista **de cada usuário** (`dados/jogos_fav_<usuário>.json`). Os favoritos aparecem numa faixa no topo e no filtro **⭐ Favoritos**.
- **Capas automáticas:** o servidor procura a **capa oficial da caixa** no acervo público *libretro-thumbnails*, casando o nome do arquivo com o do acervo (ignora região, `, The` e pontuação, com tolerância a pequenas diferenças). A capa é baixada **uma vez** e guardada em `Jogos/Capas/`; se você enviar uma imagem com o mesmo nome do jogo, ela tem prioridade. Jogos sem capa (hacks, traduções) mostram um bloco colorido com as iniciais.
- **Painel de emuladores:** um cartão por console com o emulador usado (FCEUmm, Snes9x, Mupen64Plus-Next, mGBA, Gambatte, PCSX-ReARMed), se está **pronto** no servidor, o **peso** (⚡ leve, ⚖️ médio, 🔥 pesado) e, no PlayStation, se a **BIOS** foi encontrada. Clicar no cartão filtra os jogos daquele console.

## 8. Música

**Visão geral:** o som toca **no aparelho em que você está**; o servidor busca, guarda e organiza.

**Fluxo de uma música**
1. Você busca (nome, artista ou link). A busca une a **sua biblioteca** e o **YouTube** (só metadados: título, canal e capa).
2. Ao tocar, o servidor pega o áudio com o **yt-dlp** (usando o Node do Hermes como interpretador JS exigido pelo YouTube) e guarda em `Música/<Gênero>/<Artista>/<Título>.m4a`.
3. O **gênero** é perguntado ao Hermes (uma palavra). Sem chave, fica "Sem gênero".
4. O aparelho toca o arquivo do servidor (com busca/avanço normal e **continua com a tela bloqueada** no celular).
5. Um índice (`dados/musica_indice.json`) permite navegar por **artistas** e **gêneros**.

**Interface (no estilo do Jellyfin):** abas Início, Artistas, Gêneros, Músicas, Playlists, Curtidas e Fila; Início com fileiras ("Adicionadas recentemente", Artistas, Gêneros…); páginas de artista e de gênero com capa, **Tocar tudo** e **Aleatório**; playlists e curtidas por usuário.

**Rádio automática:** quando a fila acaba, o servidor escolhe outra música do **mesmo gênero** (primeiro da biblioteca, depois uma busca nova).

**Player:** barra fixa com capa, anterior/tocar/próxima, curtir, **✕ fechar** (para a música e esvazia a fila), barra de progresso, volume e controles na tela de bloqueio do celular (Media Session).

**Aviso:** baixar áudio do YouTube contraria os termos de uso do serviço e pode ferir direitos autorais. É uma decisão do dono do servidor, para uso pessoal.

---

### Descobrir (repertório)

A aba **Descobrir** da Música não depende só do que você já ouviu:

- **20 estilos** (Pop, Rock, Rap, Funk, Sertanejo, MPB, Pagode, Forró, Eletrônica, Lo-fi, Jazz, Clássica, Metal, Reggae, Games, Anime, Anos 80/90, Gospel, Infantil) e **12 humores/atividades** (Treinar, Estudar, Relaxar, Dormir, Festa, Trabalhar, Dirigir, Romântico, Acordar, Triste, Jogar, Cozinhar).
- Cada um vira um **mix de 14 músicas escolhidas pela Alicia** (a IA monta a lista, o servidor acha cada faixa no YouTube, descartando shows ao vivo e compilações longas). O mix fica em cache por 24 horas.
- **A Alicia recomenda**: monta uma seleção pelo seu gosto (curtidas e mais ouvidas) ou surpreende você.
- **Importar playlist do YouTube**: cole o link e as músicas aparecem para tocar ou salvar como playlist.
- **Guardar no servidor**: baixa em segundo plano (fila, uma por vez) para tocar na hora depois; um indicador mostra o andamento.
- No chat: "toca música pra treinar", "coloca um sertanejo", "me recomenda umas músicas". Se a biblioteca tem poucas faixas do estilo, a Alicia completa com o mix.
## 9. RPG com a Alicia como mestra

- **Regras** inspiradas no **SRD 5.2** (conteúdo aberto, licença **CC-BY-4.0**; atribuição em [CREDITOS.md](CREDITOS.md)), simplificadas para serem rápidas e divertidas. O nome "Dungeons & Dragons" não é usado.
- **Dados justos:** d4, d6, d8, d10, d12, d20 (com vantagem/desvantagem) são rolados **pelo código do servidor** (`secrets`), nunca pela IA; o resultado aparece para todos e a Alicia narra em cima dele.
- **6 personagens prontos** (nível 1) com atributos, vida, CA, perícias, equipamento, magias e história curta.
- **2 campanhas originais** (escritas para este projeto, sem aventuras de terceiros): *A Cripta do Sino Quebrado* e *O Mercado das Sombras*, com capítulos, combates e finais que mudam conforme as escolhas.
- **Mesa:** sala com **código de 4 letras**, até **5 jogadores** (celular, PC ou TV box), chat da mesa, registro da história e partida salva em `dados/rpg_salas.json`.
- **Combate por turnos:** iniciativa, ataque, dano, acerto crítico, XP e subida de nível, tudo decidido pelo código.
- **Mestra:** a Alicia (pelo Hermes) narra com a personalidade dela, pede rolagens e guarda o estado. Para **economizar a API**, a história antiga é **resumida** em vez de reenviada a cada turno.
- **TV:** com o Modo TV do painel a TV box mostra a mesa em letras grandes enquanto cada um joga pelo celular.

---

## 10. Monitor de acessos e registros

**Requisito central do projeto:** tudo que passa pelo servidor aparece ao vivo.

- **Um log só**, em linhas JSON, com **rotação** (2 MB × 15 arquivos) para poupar o HD.
- **O que registra:** requisições do painel (método, endereço, código, tempo), logins (certos, errados, bloqueios), arquivos (abrir, enviar, baixar, apagar), conversas e chamadas à API da NVIDIA (**só metadados**), Jellyfin, música, jogos, RPG, mudanças de usuário/visitante e eventos do sistema (alertas de CPU, memória, disco cheio e **saúde do HD**).
- **Privacidade:** **nunca** registra senhas, chaves, tokens, conteúdo de arquivos nem de conversas.
- **Dois jeitos de ver:**
  - **Terminal** (`scripts/monitor.py`): abre sozinho no logon e reinicia se for fechado; cores por tipo; teclas para filtrar (1–4 por serviço, `s` segurança, `e` erros, `t` tudo, `p` pausar).
  - **Painel → Registros:** ao vivo, com filtros por tipo, serviço e texto.
- **Alertas de segurança** em destaque: várias senhas erradas, bloqueio de IP, visitante tentando entrar em área restrita…

---

## 11. Servidor 24 horas

- **Energia:** nunca suspende nem hiberna na tomada e a ação da tampa é "nada" (`powercfg`).
- **Inicialização:** tarefas agendadas no logon: `AliciaServer-Painel`, `AliciaServer-Hermes`, `AliciaServer-Monitor` e `AliciaServer-Backup` (03:30). Cada uma reinicia o serviço se ele cair. Jellyfin, Tailscale e SSH são serviços do Windows.
- **HD mecânico:** poucos serviços, logs com tamanho limitado, bancos sem gravar a cada segundo, saves a cada 2 minutos e alerta de **saúde do disco** no painel.
- **Pontos de atenção:** o login automático do Windows não é configurado por padrão (depende da senha da conta); sem ele, as tarefas só sobem depois que alguém entra. Veja [INSTALACAO.md](INSTALACAO.md).

---

## 12. Rede privada e administração remota

- **Tailscale** (rede privada gratuita): o notebook, o celular, o PC e a TV box entram na mesma conta e se enxergam de qualquer lugar. **Nenhuma porta é aberta no roteador.**
- **Firewall:** as portas do painel (8080), do Jellyfin (8096), do SSH e do compartilhamento de arquivos aceitam **somente a rede de casa e a faixa do Tailscale** (`100.64.0.0/10`).
- **OpenSSH Server:** administrar o notebook de outro PC (`ssh usuario@endereco`) e abrir o mesmo monitor de acessos de longe.
- **IP fixo:** em vez de fixar o IP no Windows, recomenda-se **reservar o IP do notebook no roteador** (evita conflito com o DHCP).

---

## 13. App Android

Um aplicativo **leve** que abre o painel no celular e na TV box. Resumo: `WebView` em tela cheia, tela de configuração do endereço, microfone para a Alicia, controle remoto na TV box. Todos os detalhes (função, escolha técnica, comportamento, como compilar e limites) estão em **[APK.md](APK.md)**.
