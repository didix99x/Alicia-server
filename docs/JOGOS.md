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

