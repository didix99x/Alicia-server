# Decisões
- **Pasta do projeto**: `alicia-server` ao lado de `alicia`, repositório Git próprio. O `.env` e o banco da Alicia não foram copiados (segredos/dados pessoais); o banco foi guardado em `dados_originais/` para migração futura.
- **Python 3.12** (via winget, escopo de usuário, sem admin). Alternativa descartada: Python 3.14 que o instalador do Hermes baixa sozinho — o Hermes cuida do próprio Python; a Alicia/painel usam 3.12.
- **Hermes no Windows nativo**: o README oficial diz que o Windows nativo é suportado (`iex (irm https://hermes-agent.nousresearch.com/install.ps1)`). Ainda não instalado; será feito na Etapa 6.
- **Sistema operacional**: Windows 10 Home em 2026 está fora do suporte padrão da Microsoft. Recomendação para o futuro: um Linux leve (Debian/Ubuntu Server) seria melhor para 24h com 8 GB e HD mecânico. Fica registrado para você decidir; nada foi trocado.

## Etapa 8 — Auditoria da Alicia (feita por busca no código; leitura parcial)
Organização: `alicia_core/` (core.py 73 KB é o "cérebro" e mistura tudo; conversation, prompts, database, nvidia_client, ollama_client, vision, screen, voice_input, audio, tts, ui/desktop_pet), `launcher.py`, `main.py`, `tests/`.

**(a) Depende do Ollama:** `ollama_client.py`, `vision.py`, funções `_prepare_vision_now/_ensure_vision_model/_maybe_recheck_vision` em core.py, `launcher.py`, `diagnostico.py`, `deps.py`, `config.py`, `.alicia_vision_choice`.
**(b) Hermes substitui:** `nvidia_client.py` (chamadas ao modelo), memória (`database.py`: tabelas conversation_history, memories, user_profile), montagem de contexto em `prompts.py`/`conversation.py`.
**(c) Só da Alicia, manter:** imagens/expressões (`assets/`, `enums.AliciaExpression`, `parse_expression_tags`), voz (`tts.py`, `voice_input.py`, `audio_*`), personalidade (`prompts.py`), modo gamer, modo descanso, UI.
**(d) Tela a remover:** `screen.py`, `vision.py`, tabela `vision_logs`, `analyze_screen_now`, `screen_observation_loop` (observadora), `_is_direct_visual_command`. **O modo gamer depende de tela** (`_detect_current_game`, `_run_gamer_analysis`): precisa ser reescrito sem captura de tela (o jogador descreve ou informa o jogo).
**(e) ACHADO IMPORTANTE:** não encontrei no código os modos **call, pôquer e sem filtro** (nenhuma ocorrência dessas palavras). Existem gamer e descanso. Ou estão em outra versão da Alicia, ou precisam ser criados do zero. Não vou inventar: preciso que você confirme (ver pergunta final). A UI é PyQt6 (desktop), que não roda via navegador; a "cara" no painel será reconstruída em HTML usando os PNGs de expressão.
**Memória:** o banco SQLite original está guardado em `dados_originais/`. Plano: exportar `memories` e `user_profile` como texto para a memória do Hermes e manter o resto como arquivo de histórico.

**Correção (usuário pediu: NÃO criar modos novos; usar só o que há no código):** o que a Alicia tem de verdade, em `prompts.py` e `core.py`:
- **Personalidades** (só mudam o tom): Normal, Brincalhona, Séria, Malcriada, Carinhosa.
- **Modos**: Gamer (depende de tela, será adaptado), Descanso (ignora a voz), Observação de Tela (será removida).
- Não existem no código os modos "call", "pôquer" e "sem filtro" com esses nomes. Nada será inventado. Se existirem em outro arquivo seu, avise; senão, a camada "sem filtro" do prompt será tratada na Etapa 10 como a personalidade **Malcriada**, que é a existente mais próxima, só se você aprovar.

## Atualização da base da Alicia (substitui a auditoria acima)
Você enviou `Alicia-project-main.zip` (versão mais nova). A cópia em `alicia/` foi substituída por ela (a anterior está no histórico Git). Essa versão **tem** os modos que faltavam: `poker/` (engine, cartas, avaliador, reações, fala), `call_audio/call_context/call_listener/virtual_audio` (modo call), `unfiltered.py` (sem filtro) e também `observer*.py`, `screen.py`, `local_vision.py`, `local_vlm.py`, `vlm_setup.py` (tela/visão local — a remover). Não há mais menção a "ollama" em `alicia_core`. A auditoria detalhada (Etapa 8) será refeita nesses arquivos antes de mudar código. O projeto original em `server\alicia` segue intocado.

- **Rede privada: Tailscale** (descartado: WireGuard puro, que exige porta aberta/IP público e configurar cada aparelho à mão; Cloudflare Tunnel, que expõe o serviço à internet). Instalado, aguardando login.
- **IP fixo**: reserva no roteador em vez de IP estático no Windows (evita conflito com DHCP).
- **Hermes sempre como usuário normal** e gateway com API local (127.0.0.1:8642) com chave interna; painel fala com ele por HTTP.
- **App desktop PyQt da Alicia** movido para `alicia/desktop_legado/` (depende de captura de tela, removida). A cara da Alicia agora é o painel web.

- **Jogos no navegador (EmulatorJS) em vez de streaming (Sunshine/Moonlight):** pedido do usuário (sem instalar nada, sem logins). Roda no aparelho de quem joga, poupa o notebook e funciona em celular/TV box. Descartado: Sunshine+Moonlight (exige app e pareamento; codificação por software pesada no i5 de 3ª geração); RetroArch no servidor. Sunshine e RetroArch foram desinstalados.
- **Música tocando no aparelho de quem usa**, interface estilo Spotify (busca, playlists, curtidas, fila, barra de player fixa): o som vem do player oficial incorporado do YouTube (com anúncios normais; nada é baixado). A busca por nome usa yt-dlp só para metadados (título/canal/capa) — não é a API oficial (que exige chave Google); se o YouTube mudar algo, a busca pode falhar e colar o link continua funcionando.

- **Música guardada no servidor (decisão do usuário):** o servidor pega o áudio com o yt-dlp e guarda em Alicia Server\Música\<Gênero>\<Artista>\<Música>.m4a; o aparelho toca dali (funciona com qualquer música, seek e tela bloqueada). O gênero é perguntado ao Hermes (uma palavra; 'Sem gênero' se não houver chave). **Aviso:** baixar do YouTube contraria os termos do serviço e pode ferir direitos autorais; fica por responsabilidade do usuário, para uso pessoal. O player incorporado do YouTube foi abandonado (muitos vídeos bloqueiam incorporação). O índice fica em dados/musica_indice.json.

- **Jogo dentro do painel (camada), não em outra página:** assim o player de música (que vive na página do painel) continua tocando durante o jogo. Descartado: abrir o jogo em nova aba/página (a música parava ao trocar de página).

- **Jellyfin dentro do painel (página Filmes e Séries):** o app Android só conhece o endereço do painel; um link para outra porta não abre no WebView. Por isso o Jellyfin aparece num quadro dentro do painel e o login do usuário 'casa' (sem senha) é automático (script no jellyfin-web, ver PROBLEMAS.md). Envio de filmes/séries pelo painel organiza as pastas no padrão do Jellyfin e pede a atualização da biblioteca.

- **Aba Música no estilo do Jellyfin:** abas Início, Artistas, Gêneros, Músicas, Playlists, Curtidas e Fila; Início com fileiras (adicionadas recentemente, artistas, gêneros, playlists, curtidas); páginas de artista e de gênero com capa, 'Tocar tudo' e 'Aleatório'; busca une a biblioteca do servidor e o YouTube.

- **Interface refeita do zero em arquivos separados** (HTML + CSS + 3 scripts) em vez de um arquivo gigante: mais fácil de manter. Descartado: framework (React/Vue), que pesaria no notebook e exigiria compilar.
- **Perfil visitante sem senha** (pedido do usuário): sessão de 24 h, só Jogos/Música/Filmes/RPG; rotas de arquivos, registros, chave, usuários, Hermes e conversa com a Alicia bloqueadas no servidor. A Alicia fica de fora porque a memória do Hermes é compartilhada: um visitante poderia perguntar coisas pessoais. **Risco conhecido:** o RPG também fala com o Hermes (chamadas avulsas, sem a sua conversa), então a memória dele em tese ainda poderia aparecer numa narração; não consegui verificar isso.
- **Usuários criados pelo painel** (Configurações) em vez de só por script.
- **Voz da Alicia pelo servidor (edge-tts, voz Francisca) em vez da voz do navegador:** a do navegador no Windows do usuário é masculina e varia de aparelho para aparelho. Usa o serviço online do Microsoft Edge (gratuito, o mesmo do projeto original); fallback para a voz do navegador escolhendo voz feminina.
- **Escala da interface por tamanho de tela:** todos os tamanhos do CSS em rem e o tamanho-base calculado pela largura/altura (até 1,9x). Descartado: CSS zoom (comportamento diferente entre navegadores com vh/vw).
