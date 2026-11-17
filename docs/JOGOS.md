# Jogos no Alicia Server (direto no navegador)

Como no Game Pass: abra o painel → **Jogos** → toque no jogo → joga. **Não precisa instalar nada nem fazer outro login** (só o login normal do painel). Funciona no PC, no celular e na TV box (pelo navegador).

## Organização automática
Você pode colocar o jogo em qualquer pasta: o painel olha o próprio arquivo (inclusive dentro do `.zip`) e move o jogo para a pasta do console certo (ex.: um jogo de Super Nintendo que foi parar em Nintendo vai para Super Nintendo).

## Como funciona
O jogo roda **dentro do navegador do aparelho** (emulador EmulatorJS, código aberto). O notebook só entrega o arquivo do jogo e guarda o seu progresso, então ele não pesa. Consoles: Nintendo, Super Nintendo, Nintendo 64, Game Boy/Color, GBA e PS1 (sem PS2).

## Onde colocar os jogos
Pasta compartilhada `Alicia Server\Jogos` (no PC: `\\IP-DO-SERVIDOR\AliciaServer\Jogos`), subpastas `NES`, `SNES`, `N64`, `GBA`, `GB` e `PS1`. Eu não baixei nenhum jogo nem BIOS: coloque só os seus.
- Formatos: Nintendo `.nes` · Super Nintendo `.sfc/.smc` · N64 `.z64/.n64/.v64` · GBA `.gba` · Game Boy e Game Boy Color `.gb/.gbc` · PlayStation `.cue` (com o `.bin`, ideal em `.zip`), `.chd`, `.iso`, `.pbp`. Arquivos `.zip` também funcionam.
- **Capa**: coloque uma imagem `.png` ou `.jpg` com o mesmo nome do jogo na mesma pasta.
- **BIOS do PlayStation**: coloque em `Jogos\BIOS` (ex.: `scph5501.bin`). Sem ela, muitos jogos de PS1 não abrem.
- Há um jogo de teste próprio, "Teste do Servidor" (NES): ele só pinta a tela de azul para provar que o emulador funciona. Pode apagar.

## Controles
- **Teclado** (PC) e **controle Bluetooth/USB** (PC, celular, TV box: o navegador reconhece sozinho; aperte um botão para ele aparecer).
- **Celular**: aparecem botões na tela.
- **TV box**: setas e OK do controle remoto escolhem o jogo; para jogar use um controle conectado.
Menu do emulador (ícones na tela do jogo): salvar/carregar, tela cheia, ajustes de controle.

## Saves (continua de onde parou, em qualquer aparelho)
O painel salva o progresso no servidor a cada 2 minutos, ao sair da página e quando você usa "salvar". Na próxima vez, o jogo abre de onde parou, mesmo em outro aparelho. Os saves ficam em `Jogos\Saves\<seu usuário>\`.

## Desempenho
Depende do **seu aparelho**, não do notebook. NES/SNES/GB/GBA rodam bem em quase tudo; N64 e PS1 pedem um celular/TV box razoável. Se travar, feche outras abas ou use o PC.

## Honestidade sobre os testes
Testei no navegador: lista de jogos, abrir o jogo de teste (o emulador do NES iniciou e desenhou a tela), salvar/ler save no servidor e bloqueio de acesso a arquivos fora da pasta. **Não testei jogos reais** (não tenho jogos), controle físico, celular, TV box, nem PS1/N64.


## Jogos em .rar ou em pastas (comum no PlayStation)

Jogos de PlayStation costumam vir em `.rar`, ou numa pasta com `.bin` + `.cue`, formatos que o emulador não abre direto. Ao abrir a aba Jogos, o servidor **arruma sozinho**:

- **`.rar`** vira um `.zip` só com o jogo (usa o 7-Zip).
- **Pasta já descompactada** (com `.bin`/`.cue`, mesmo dentro de subpastas como `JOGO` ou `cd 1`) vira um `.zip` por jogo. O que não é o jogo (atalhos de site, textos) é ignorado.
- **Vários discos** viram uma entrada por disco: `Nome - CD 1`, `Nome - CD 2`.
- **`.cue` com o nome do `.bin` errado** (acontece bastante em pacotes baixados) é **corrigido automaticamente** dentro do zip.
- **Capa:** uma imagem com "capa" no nome dentro da pasta vira a capa do jogo.
- Os originais vão para `Jogos/Originais_rar` (pode apagar depois para liberar espaço). Um aviso aparece na aba enquanto o servidor trabalha (alguns minutos).
- **Arquivo com senha:** a aba mostra um campo para digitar a senha (geralmente está no site de onde você baixou). A senha só é usada para descompactar e **não fica guardada**.
## Multiplayer (jogar junto com amigos)

Os jogos de **Nintendo, Super Nintendo, Nintendo 64 e PlayStation** podem ser jogados por mais de uma pessoa, cada uma no seu aparelho (Game Boy e Game Boy Advance não têm multiplayer aqui).

1. **Anfitrião:** na aba Jogos, toque no botão **👥** de um jogo. O jogo abre e aparece uma etiqueta "👥 Sala ABCD". Tocar nela copia o link da sala.
2. **Amigos:** na aba Jogos, o painel **👥 Jogar junto** lista as salas abertas, com o botão **Entrar**. Também dá para digitar o **código de 4 letras**, ou abrir o link.
3. Quem entra recebe a **imagem e o som** do jogo e usa os **controles** do próprio aparelho: teclado, controle físico ou **botões na tela** (celular e tablet). Cada um vira o jogador 2, 3 ou 4.

Quantos jogadores: Nintendo 2, Super Nintendo 2, Nintendo 64 até 4, PlayStation 2.

**Como funciona:** o jogo roda **só no aparelho do anfitrião**, que transmite a tela por WebRTC; o servidor apenas apresenta os aparelhos uns aos outros e lista as salas. Por isso:

- o anfitrião precisa **manter o jogo aberto e a tela ligada** (se fechar, a sala acaba e os convidados são avisados);
- o desempenho depende do aparelho do anfitrião: prefira notebook, PC ou um celular forte;
- o painel **não sabe quais jogos têm modo para dois jogadores**. O botão 👥 aparece em todos os jogos desses consoles. Se o jogo for só de um jogador, o segundo controle simplesmente não faz nada;
- o progresso salvo é o do anfitrião.