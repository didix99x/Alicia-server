# Arquitetura

## Visão geral

```mermaid
flowchart TB
    subgraph Clientes["Aparelhos (celular, PC, TV box, app Android)"]
      B[Navegador / WebView]
    end
    B -->|"HTTP · rede de casa ou Tailscale"| P

    subgraph Notebook["Notebook servidor (Windows)"]
      direction TB
      P["Painel FastAPI<br/>:8080"]
      subgraph Locais["Só local (127.0.0.1)"]
        H["Hermes gateway<br/>:8642"]
      end
      J["Jellyfin<br/>:8096"]
      E["EmulatorJS<br/>/ejs (arquivos estáticos)"]
      Y["yt-dlp + Node<br/>(áudio da música)"]
      T["edge-tts<br/>(voz da Alicia)"]
      D[("Pasta de dados<br/>Documentos · Filmes · Séries<br/>Jogos · Música")]
      L[("logs/acessos.log<br/>(rotação)")]
      M["Monitor<br/>(terminal)"]
      I[("dados/<br/>índice da música, RPG, config")]
    end
    N["API da NVIDIA (NIM)"]
    YT["YouTube"]
    MS["Serviço de voz do Edge"]

    P --> H --> N
    P --> J
    P --> E
    P --> Y --> YT
    P --> T --> MS
    P --> D
    P --> I
    P --> L --> M
    J --> D
```

## Componentes e portas

| Componente | Porta | Quem acessa | Como inicia |
|---|---|---|---|
| Painel (FastAPI/Uvicorn) | 8080 | rede de casa + Tailscale | tarefa `AliciaServer-Painel` |
| Hermes gateway (API OpenAI-compatível) | 8642 (só `127.0.0.1`) | só o painel | tarefa `AliciaServer-Hermes` |
| Jellyfin | 8096 | rede de casa + Tailscale | serviço do Windows |
| SSH (administração) | 22 | rede de casa + Tailscale | serviço do Windows |
| Pasta de rede (SMB) | 445 | só rede de casa | recurso do Windows |
| EmulatorJS | (servido pelo painel em `/ejs`) | navegador | arquivos estáticos |

Nenhuma porta é aberta no roteador.

## Pastas e dados

| Caminho | Conteúdo | No Git? |
|---|---|---|
| `painel/` | código do painel | sim |
| `alicia/` | prompts, personalidades, imagens, pôquer, app desktop legado | sim |
| `scripts/` | instalação, tarefas, monitor, backup, Hermes, demonstração | sim |
| `alicia-apk/` | projeto Android | sim |
| `painel/usuarios.json`, `painel/.segredo` | usuários (hashes) e chave dos cookies | **não** |
| `.env` | chaves (NVIDIA, Hermes, Jellyfin) | **não** |
| `dados/` | índice da música, mesas de RPG, configuração do painel, cache | **não** |
| `logs/` | registros e erros | **não** |
| `C:\AliciaServer\Alicia Server\` (padrão) | **Documentos, Filmes, Séries, Jogos, Música** | fora do repositório |
| `C:\AliciaServer\hermes\` | instalação do Hermes | fora do repositório |
| `C:\AliciaServer\emulatorjs\` | EmulatorJS (baixado do projeto oficial) | fora do repositório |

Os caminhos fora do repositório são configuráveis por variáveis de ambiente (`ALICIA_DADOS`, `ALICIA_EJS`, `ALICIA_BACKUP`, `HERMES_EXE`).

## Fluxos principais

### Conversa com a Alicia
```mermaid
sequenceDiagram
    participant U as Usuário
    participant W as Navegador
    participant P as Painel
    participant H as Hermes
    participant N as NVIDIA
    U->>W: escreve ou fala
    W->>P: POST /api/alicia/conversar
    P->>P: prompt = personalidade + jeito + camada sem filtro
    P->>H: chat (sessão do usuário)
    H->>N: modelo (nemotron)
    N-->>H: resposta
    H-->>P: texto com [EXPRESSÃO]
    P-->>W: texto limpo + expressão
    W->>P: POST /api/alicia/voz (opcional)
    P-->>W: áudio da voz Francisca
```

### Pedido de música pela Alicia
```mermaid
sequenceDiagram
    participant W as Navegador
    participant P as Painel
    participant Y as yt-dlp
    participant H as Hermes
    W->>P: "toca Linkin Park" (so_achar)
    P->>P: biblioteca primeiro, senão busca no YouTube
    P-->>W: faixas (rápido)
    W->>W: começa a tocar na hora
    W->>P: (em seguida) pede o comentário da Alicia
    P->>H: "a música já está tocando, comente"
    H-->>P: frase no jeito dela
    P-->>W: frase (e voz)
    Note over P,Y: ao tocar, o áudio é baixado, guardado em Música/Gênero/Artista e indexado
```

### Jogo no navegador
1. O painel lista `Jogos/<console>/` e organiza arquivos pelo conteúdo.
2. Clicar abre `/jogar` numa **camada** (iframe) sobre o painel; o emulador (`/ejs`) carrega no navegador.
3. O jogo vem de `/api/jogos/arquivo`; o estado salvo vai e volta por `/api/jogos/save`.
4. O player de música fica fora da camada e não para.

## API do painel (resumo)

| Área | Rotas |
|---|---|
| Sessão | `POST /api/login` · `POST /api/logout` · `GET /api/eu` · `GET /api/publico` · `POST /api/visitante` |
| Administração | `GET/POST/DELETE /api/usuarios` · `POST /api/senha` · `POST /api/visitante/config` · `POST /api/hermes/reiniciar` |
| Estado | `GET /api/status` · `GET /api/hermes/info` · `POST /api/verificar` |
| Chave | `GET /api/nvidia` · `POST /api/nvidia/testar` · `POST /api/nvidia/salvar` |
| Arquivos | `GET /api/arquivos` · `POST /api/arquivos/enviar` · `GET /api/arquivos/baixar` · `DELETE /api/arquivos` · `POST /api/arquivos/pasta` |
| Alicia | `GET /api/alicia/opcoes` · `POST /api/alicia/conversar` · `POST /api/alicia/voz` · `POST /api/alicia/musica` · `GET /api/alicia/imagem/{nome}` |
| Música | `GET /api/musica/buscar` · `GET/POST /api/musica/biblioteca` · `GET /api/musica/servidor` · `GET /api/musica/audio/{id}` · `GET /api/musica/proxima` · `POST /api/musica/tocando` · `GET /api/musica/descobrir` · `GET /api/musica/mix` · `GET /api/musica/playlist` · `POST /api/musica/recomendar` · `POST /api/musica/guardar` · `GET /api/musica/guardando` |
| Jogos | `GET /api/jogos` · `GET /api/jogos/arquivo` · `GET /api/jogos/bios` · `GET/POST /api/jogos/save` · `GET /api/jogos/capa` · `GET /api/jogos/imagem` (capa automática) · `POST /api/jogos/favorito` · `GET /api/jogos/info` · `POST /api/jogos/inicio` · `POST /api/jogos/fim` · `POST /api/jogos/senha` · `POST /api/atividade` · `GET /jogar` |
| Filmes | `POST /api/filmes/enviar` |
| RPG | `GET /api/rpg/info` · `POST /api/rpg/sala` · `POST /api/rpg/entrar` · `GET /api/rpg/sala/{codigo}` · `POST …/falar` · `POST …/dado` · `POST …/combate` |
| Registros | `GET /api/logs` · `GET /api/logs/ao-vivo` (SSE) |

Todas exigem login, exceto `/api/login`, `/api/publico` e `/api/visitante`. O visitante só alcança Jogos, Música, Filmes (leitura), RPG e o estado básico.

## Decisões de projeto que moldaram a arquitetura

- **Nada de IA local**: o notebook é fraco; toda a IA usa a API da NVIDIA através do Hermes.
- **Trabalho visual no navegador**: o servidor entrega arquivos e dados; emulação de jogos e interface rodam no aparelho de quem usa.
- **Sem banco de dados pesado**: JSON pequeno gravado só quando algo muda, para poupar o HD mecânico.
- **Uma instância, poucos processos**: painel, gateway do Hermes e Jellyfin.

Mais em [DECISOES.md](DECISOES.md).
