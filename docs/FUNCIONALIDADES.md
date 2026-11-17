# 🧭 Funcionalidades, uma por uma

Este guia explica **o que cada funcionalidade faz, como usar e quais são os limites**. Para a parte técnica, veja [SISTEMAS.md](SISTEMAS.md); para instalar, [INSTALACAO.md](INSTALACAO.md).

**Índice:** [Entrada e perfis](#-entrada-e-perfis) · [Início](#-início) · [Alicia](#-alicia) · [Música](#-música) · [Descobrir](#-descobrir) · [Jogos](#-jogos) · [Filmes e séries](#-filmes-e-séries) · [Arquivos](#-arquivos-e-backup) · [RPG](#-rpg-com-a-alicia-como-mestra) · [Servidor e registros](#-servidor-e-registros) · [Configurações](#-configurações) · [Celular, TV e APK](#-celular-tv-e-apk) · [Acesso de fora de casa](#-acesso-de-fora-de-casa) · [Segurança](#-segurança-na-prática)

---

## 🔑 Entrada e perfis

| Perfil | Como entra | O que pode |
|---|---|---|
| **Morador/administrador** | Usuário e senha | Tudo: Alicia, arquivos, servidor, registros, configurações, envio de filmes |
| **Visitante** | Botão **Entrar como visitante** (sem senha) | Só Jogos, Música, Filmes (assistir) e RPG |

- A senha fica protegida com **Argon2**. Depois de **5 erros seguidos, o IP é bloqueado por 5 minutos** e o monitor avisa.
- A sessão dura 14 dias (visitante: 24 horas).
- O visitante é limitado **no servidor**: mesmo que alguém tente abrir o endereço de uma página restrita, recebe "acesso negado".
- O administrador liga ou desliga a entrada de visitantes em **Configurações**.

## 🏠 Início

A tela de abertura: a Alicia cumprimenta você e cada recurso é um **cartão** (Filmes, Jogos, Música, RPG, Arquivos…) mostrando o **estado real** do serviço. Tem **busca geral**, um **tour** na primeira entrada e o botão de **modo TV**.

## 💬 Alicia

A assistente do servidor. O cérebro é o **Hermes Agent** (memória e ferramentas) usando um modelo da NVIDIA; a personalidade e os prompts são originais.

- **Conversa com memória:** ela lembra do que foi dito em conversas anteriores.
- **Jeitos de falar:** personalidades diferentes para escolher.
- **Modo sem filtro:** liberta o tom da conversa (continua dentro das regras do serviço de IA).
- **Voz feminina:** voz neural *Francisca* (pt-BR) com entonação diferente para cada expressão (feliz, séria, brincalhona…). Sem internet, usa a voz do navegador.
- **Pede música:** *"toca uma música pra treinar"*, *"coloca Legião Urbana"*, *"me recomenda algo"*. Ela abre o player e toca **no seu aparelho**.
- **Controla o player:** pausa, continua, próxima, volume.
- **Analisa o servidor:** *"como está o servidor?"* → resposta com **números reais** de memória, disco, HD, backup, acessos e alertas.
- **Fala por cima da música** baixando o volume e devolvendo depois.

Limites: visitantes não conversam com ela (a memória é compartilhada); o comentário depois de um pedido de música leva de 15 a 25 s (é a IA escrevendo).

## 🎵 Música

Visual inspirado no **Jellyfin/Spotify**, em blocos.

- **Toca no aparelho que você está usando**, não no notebook (o notebook só processa).
- **Busca** na biblioteca do servidor e no YouTube.
- **Biblioteca organizada** por **artista** e **gênero**; cada música tocada é **guardada no servidor** e na próxima vez toca na hora.
- **Rádio do mesmo gênero:** quando a música termina, entra outra parecida automaticamente.
- **Fila**, **curtidas** e **playlists**.
- **Player por cima de tudo:** continua tocando quando você troca de página ou abre um jogo; botão para **fechar** o player.
- **Controle na tela de bloqueio** do celular (Media Session).

Limites: a primeira vez de uma música nova leva de 10 a 25 s (o servidor busca o áudio). Alguns vídeos recusam download; o painel avisa e pula para a próxima.

## 🔎 Descobrir

A aba que amplia o **repertório**:

- **20 estilos:** Pop, Rock, Rap e Hip-hop, Funk, Sertanejo, MPB, Pagode e Samba, Forró, Eletrônica, Lo-fi, Jazz, Clássica, Metal, Reggae, Trilhas de games, Anime, Anos 80, Anos 90, Gospel e Infantil.
- **12 humores e atividades:** Treinar, Estudar, Relaxar, Dormir, Festa, Trabalhar, Dirigir, Romântico, Acordar, Triste, Jogar e Cozinhar.
- **Mixes curados pela Alicia:** cada um vira uma lista de cerca de 14 músicas escolhidas pela IA e localizadas no YouTube (sem shows ao vivo nem compilações de horas). O mix fica em cache por 24 horas.
- **A Alicia recomenda:** monta uma seleção pelo que você curtiu e mais ouve, ou te surpreende.
- **Importar playlist do YouTube:** cole o link; as músicas aparecem para tocar ou **salvar como playlist**.
- **Guardar no servidor:** baixa a lista inteira **em segundo plano** (uma música por vez) com indicador de andamento.

## 🎮 Jogos

Retrô **no navegador**, **sem instalar nada e sem login**, como num serviço de assinatura de jogos.

- **6 consoles:** Nintendo, Super Nintendo, Nintendo 64, Game Boy, Game Boy Advance e PlayStation.
- **Biblioteca em blocos** com o nome completo do console (sem abreviações).
- **Detecção automática:** você coloca o arquivo na pasta e o servidor descobre o console **pelo conteúdo**.
- **Progresso salvo no servidor** (continua de onde parou, em qualquer aparelho).
- **Jogo por cima do painel:** a música não para.
- **Emulação no seu aparelho:** o notebook não faz esforço.
- **⭐ Favoritos:** toque na estrela de um jogo; seus favoritos ficam numa faixa no topo e num filtro (cada usuário tem os seus).
- **Capas:** cada jogo mostra a **capa oficial da caixa**, buscada sozinha na primeira vez e guardada no servidor. Sem capa disponível, aparece um bloco colorido com as iniciais. Para usar uma capa sua, envie uma imagem com o mesmo nome do jogo.
- **Painel de emuladores:** um cartão por console com o emulador, se está pronto, o peso (leve, médio, pesado) e a situação da BIOS do PlayStation. Clique para filtrar por console.
- **Controle** por teclado, toque na tela ou controle físico.

Limites: Nintendo 64 e PlayStation exigem aparelho mais forte. Os jogos e BIOS **não vêm no repositório**; você coloca os seus. Veja [JOGOS.md](JOGOS.md).

## 🎬 Filmes e séries

- **Jellyfin dentro do painel**, **em tela cheia** e **já logado** (usuário "casa", sem pedir senha).
- **Enviar filmes e séries** pelo painel (só moradores); o Jellyfin reconhece capas, sinopses e episódios.
- Funciona no navegador, no APK e na TV box.

Limite: conversão pesada de vídeo no notebook fraco é lenta; prefira arquivos em formatos que o aparelho já toca (MP4/H.264).

## 📁 Arquivos e backup

- Pastas compartilhadas acessíveis de qualquer aparelho.
- **Listar, enviar, baixar, criar pasta e apagar (para a lixeira).**
- **Lixeira:** apagar nunca é definitivo; as pastas principais são protegidas.
- **Backup diário automático** de Documentos e configuração.
- Impossível sair da pasta de dados (`../` é bloqueado).

Limite: o backup fica no mesmo HD; copie para outro disco para proteção real.

## 🎲 RPG com a Alicia como mestra

- **Mesas com código** para convidar até **5 jogadores**.
- **Personagens prontos** e criação de personagem.
- **Dados justos:** rolados pelo servidor, ninguém trapaceia.
- **Combate** por turnos e **campanhas originais** ("A Cripta do Sino Quebrado" e "O Mercado das Sombras").
- A **Alicia narra** e reage às ações.

Regras simplificadas, inspiradas no SRD 5.2 (CC-BY-4.0).

## 🖥️ Servidor e registros

- **Servidor:** gráficos ao vivo de CPU, memória e disco; estado de cada serviço (painel, Hermes, Jellyfin, Tailscale); controle do Hermes; saúde do HD.
- **Registros:** **quem acessou o quê, quando e de onde**, ao vivo, com filtro. **Nunca** guarda senha, chave, conteúdo de arquivo ou de conversa.
- **Monitor em terminal** abre no logon do notebook para acompanhar sem o navegador.
- **Alertas:** disco acima de 90%, HD com problema, tentativas de senha, serviço caído.
- **Verificar tudo:** testa 11 itens (painel, IA, voz, Hermes, Jellyfin, pastas, backup…).

## ⚙️ Configurações

- **Chave da IA (NVIDIA):** cola e testa na hora; fica mascarada e só no `.env`.
- **Usuários:** criar, apagar e trocar senha.
- **Visitante:** ligar ou desligar.
- **Voz e personalidade** da Alicia.

## 📱 Celular, TV e APK

- **Celular:** abas embaixo, tudo em blocos grandes.
- **Tela grande:** o painel **escala** de telas pequenas a monitores ultrawide.
- **Modo TV:** blocos enormes e navegação por controle remoto.
- **APK:** app leve que abre o painel em tela cheia, com endereço configurável, microfone para a Alicia e ícone próprio. Veja [APK.md](APK.md).

## 🌍 Acesso de fora de casa

**Tailscale** cria uma rede privada entre seus aparelhos: o servidor fica acessível em qualquer lugar **sem abrir porta no roteador**. O firewall só aceita a rede de casa e a rede Tailscale. Há também **SSH** para administrar à distância.

## 🔐 Segurança na prática

Sem portas abertas na internet · senhas em Argon2 · bloqueio por tentativas · visitante limitado no servidor · Hermes do painel **sem terminal e sem acesso a arquivos** · segredos fora do Git · registros sem dados sensíveis. Detalhes e decisões conscientes em [SEGURANCA.md](SEGURANCA.md).
