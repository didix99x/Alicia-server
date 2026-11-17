# Estado do projeto: o que foi testado de verdade

Este documento separa com honestidade **o que foi verificado**, **o que foi só configurado** e **o que ainda não existe**.

## ✅ Testado de verdade (rodando no servidor real)

| Área | O que foi verificado |
|---|---|
| Painel | Todas as páginas abrem sem erro de JavaScript; sem rolagem horizontal em 390 px (celular); layout conferido em celular, notebook e ultrawide (3440×1440) |
| Login | Entrada, senha errada, sessão inválida, bloqueio de caminhos; criação, exclusão e troca de senha de usuários |
| Visitante | Entrada sem senha; rotas restritas devolvem 403; login por senha do perfil visitante é recusado |
| Alicia | Conversa real com o modelo da NVIDIA (resposta, expressão, personalidade, memória de sessão); voz Francisca gerada pelo servidor |
| Música | Busca (biblioteca + YouTube), download e organização por gênero/artista, reprodução com avanço, rádio do mesmo gênero, fila, curtidas, botão de fechar, pedidos pela Alicia (música, pausa, próxima, volume) |
| Jogos | Biblioteca em blocos, organização automática por conteúdo do arquivo, emulador abrindo um jogo de teste e um de Super Nintendo, salvar/ler progresso no servidor, camada sobre o painel com a música continuando |
| Filmes | Jellyfin dentro do painel em tela cheia, login automático do usuário "casa", envio de filme e série com reconhecimento pelo Jellyfin |
| RPG | Sessão completa com 2 jogadores simulados, incluindo combate e final (narração com o modelo falso nesse teste) |
| Hermes | Conversa, sessões, tarefa agendada que rodou e gerou saída, ferramentas limitadas |
| Segurança | Bloqueio de `../`, bloqueio por tentativas, firewall restrito, `.env` fora do Git |
| Monitor | Registros ao vivo no painel; terminal abrindo no logon |
| Backup | Tarefa diária rodando e copiando Documentos e configuração |
| **Verificar tudo** | 11 de 11 itens ✓ com a chave real |

## ⚠️ Configurado, mas **não testado** de ponta a ponta

- **Reinício completo** do notebook com **tampa fechada**, com todos os serviços instalados (painel e monitor já subiram sozinhos num reinício anterior; Hermes, Jellyfin e Tailscale foram instalados depois).
- **Administração por SSH** a partir de outro aparelho e abrir o monitor de longe.
- **Acesso de fora de casa** pelo Tailscale a partir do celular.
- **App Android**: o projeto está completo, mas **nunca foi compilado nem instalado**.
- **Jogos pesados** (Nintendo 64 e PlayStation) em celular/TV box reais; **controle físico**.
- **Pedir música pela voz** (microfone) e a Alicia falando por cima da música.
- **Pasta de rede** acessada de outro PC (depende de a conta do Windows ter senha).
- **Narração do RPG com a API real** em várias rodadas e com pessoas de verdade.
- **Aceleração por hardware** de vídeo (Jellyfin) na placa integrada: não ativada.

## ❌ Ainda não existe

- Modos **call** e **gamer** da Alicia no painel (o código original existe em `alicia/alicia_core`, mas depende do app desktop). O **pôquer** tem motor pronto, sem tela.
- **Migração da memória antiga** da Alicia (SQLite do app desktop) para o Hermes.
- **Prioridade automática** do jogo sobre a conversão de vídeo do Jellyfin.
- **IP fixo no Windows** (recomendado: reserva no roteador).
- **Login automático do Windows** (exige a senha da conta; decisão do dono).
- **Backup em outro disco** (hoje fica no mesmo HD).
- **Busca de música pela API oficial do YouTube** (exigiria uma chave do Google); a busca atual usa o `yt-dlp` só para metadados.

## 📏 Consumo medido (notebook com tudo ligado)

Notebook de teste: Core i5-3230M (2 núcleos), 8 GB de RAM, HD mecânico.
- Processador parado: cerca de 20 a 40%.
- Memória: cerca de 5 a 6 GB usados com o painel, o Hermes, o Jellyfin e um navegador abertos.
- Disco: dezenas de GB usados; o painel alerta quando passa de 90%.

É suficiente para o uso doméstico descrito aqui; conversão pesada de vídeo e emulação rodam **fora** do servidor (no navegador de quem usa) justamente por isso.

## 🧱 Limitações conhecidas

- A primeira vez que uma música nova toca leva de **10 a 25 s** (o servidor precisa buscar o áudio); depois toca na hora.
- O comentário da Alicia depois de um pedido de música leva de **15 a 25 s** (é a IA escrevendo).
- Alguns vídeos do YouTube podem recusar o download; o painel avisa e pula para a próxima.
- A voz depende de internet (serviço do Edge); sem ela usa a voz do navegador.
- Visitantes não conversam com a Alicia.
