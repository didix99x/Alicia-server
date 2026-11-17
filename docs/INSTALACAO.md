# Instalação passo a passo

Este guia leva do **zero ao servidor no ar**. Ele descreve o que foi feito para construir o Alicia Server e traz os comandos exatos. Onde existe um script que automatiza o passo, ele está indicado.

> ⏱️ Tempo: cerca de 1 a 2 horas, a maior parte esperando downloads e instalações num notebook modesto.
> 🧪 Veja em [ESTADO.md](ESTADO.md) o que foi testado de verdade e o que ainda não.

## 0. O que você precisa

| Item | Detalhe |
|---|---|
| Computador | Qualquer PC com **Windows 10/11** que fique ligado (foi feito num notebook Core i5 de 3ª geração, 8 GB de RAM, HD mecânico) |
| Rede | Wi-Fi ou cabo; **internet** no servidor (API da NVIDIA, voz da Alicia, busca de músicas) |
| Conta NVIDIA | Chave gratuita da API em <https://build.nvidia.com> (a **única** coisa com cota no projeto) |
| Conta Tailscale | Gratuita, para acessar de fora de casa (<https://tailscale.com>) |
| Seus arquivos | Filmes, séries, jogos e BIOS que **você** tem. O repositório não traz nenhum |

Regras que o projeto segue: só software **gratuito** e de **fonte oficial**; nenhuma porta aberta na internet; nenhum modelo de IA local.

---

## 1. Preparar o Windows

1. Atualize o Windows e deixe o notebook **na tomada**.
2. **Reserve o IP do notebook no roteador** (recomendado em vez de IP fixo no Windows). Anote o IP, ex.: `192.168.X.X`.
3. (Opcional) Dê um nome ao computador, ex. `alicia-server` (Configurações → Sistema → Sobre).
4. Energia (o script do passo 8 faz isto por você): nunca suspender nem hibernar na tomada e **ação da tampa = nada**:
   ```powershell
   powercfg /change standby-timeout-ac 0
   powercfg /hibernate off
   powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
   powercfg /setactive SCHEME_CURRENT
   ```
5. Na BIOS, se existir a opção, ative **"Power on after AC loss"** (liga sozinho depois de queda de energia). Isso é com você: varia por modelo.

## 2. Instalar Python e Git

```powershell
winget install --id Python.Python.3.12 -e
winget install --id Git.Git -e
```
Feche e abra o PowerShell. Confira com `python --version` e `git --version`.

## 3. Baixar o projeto e instalar o painel

```powershell
git clone https://github.com/didix99x/Alicia-server.git
cd Alicia-server
.\scripts\instalar.ps1            # cria o ambiente, instala as bibliotecas, as pastas e o usuário administrador
```
O script `instalar.ps1`:
1. confere o Python;
2. cria `painel\.venv` e instala `painel\requirements.txt` (**versões fixadas**);
3. cria `logs`, `dados` e a pasta de dados (padrão `C:\AliciaServer\Alicia Server`) com `Documentos`, `Filmes`, `Séries`, `Jogos` (e as pastas dos consoles), `Música`;
4. cria o `.env` a partir de `.env.example`;
5. cria o administrador e grava a senha em `PRIMEIRO_ACESSO.txt` (**fora do Git**; anote e apague o arquivo).

Teste manualmente:
```powershell
$env:ALICIA_DADOS = "C:\AliciaServer\Alicia Server"; $env:PYTHONPATH = "painel"
painel\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --app-dir painel
```
Abra <http://localhost:8080> e entre. Neste ponto já funcionam: Arquivos, Jogos (sem emulador ainda), Música (busca), RPG (sem narração) e Servidor.

## 4. A chave da NVIDIA (pelo painel)

No painel: **Configurações → Chave da NVIDIA** → cole a chave (`nvapi-…`) → **Testar chave** → **Salvar**.
- A chave fica **só** no `.env` (permissão restrita ao usuário) e nunca aparece no código, nos logs nem em mensagens de erro; no painel ela aparece mascarada.
- O teste faz uma chamada real mínima (a lista pública de modelos responde "ok" mesmo sem chave, então ela não serve de teste).
- Sem chave, tudo que não usa IA funciona e a Alicia mostra um aviso amigável.

## 5. Instalar o Hermes Agent (o cérebro)

O Hermes tem instalador oficial para Windows (<https://hermes-agent.nousresearch.com/docs>). **Leia o script antes de rodar** e rode como **usuário normal** (ele se recusa a funcionar como administrador).

```powershell
mkdir C:\AliciaServer\hermes
$env:HERMES_HOME = "C:\AliciaServer\hermes"
$env:UV_PYTHON_INSTALL_DIR = "C:\AliciaServer\hermes\uv-python"
iwr https://hermes-agent.nousresearch.com/install.ps1 -OutFile $env:TEMP\hermes_install.ps1
# leia o arquivo, depois:
& $env:TEMP\hermes_install.ps1 -NonInteractive -SkipSetup -SkipBrowser -SkipComputerUse -HermesHome C:\AliciaServer\hermes
```
Se aparecer *"no dependency environment is committed for this install"*, rode `hermes pm repair`.

> **Dica:** se você instala usando um programa "empacotado" da Microsoft Store (por exemplo alguns terminais ou apps), o Windows pode redirecionar a pasta `AppData` dele. Instalar em `C:\AliciaServer\hermes` evita esse problema.

Configure o modelo (NVIDIA):
```powershell
hermes config set model.provider nvidia
hermes config set model.default nvidia/nemotron-3-ultra-550b-a55b
```
Ligue a API local e sincronize o `.env` único:
```powershell
python scripts\sync_env.py          # gera API_SERVER_KEY e copia as variáveis para o .env do Hermes
python scripts\limitar_hermes.py    # o Hermes do painel só terá: web, skills, todo, cronjob (sem terminal nem arquivos)
```
Inicie o gateway (a tarefa do passo 8 faz isso sozinha): `scripts\iniciar_hermes.cmd`. Confira: `curl http://127.0.0.1:8642/health`.

## 6. Instalar o Jellyfin (filmes e séries)

```powershell
winget install --id Jellyfin.Server -e
```
O primeiro início leva ~35 s (o instalador pode reclamar que "não iniciou o serviço"; é só demora, confira em <http://localhost:8096>).

1. Abra <http://localhost:8096> e faça o assistente: idioma pt-BR, **usuário administrador com senha**.
2. Crie as bibliotecas: **Filmes** (tipo Filmes) → `…\Alicia Server\Filmes`; **Séries** (tipo Programas de TV) → `…\Alicia Server\Séries`.
3. Painel do Jellyfin → Reprodução: deixe a conversão em **software**, 2 threads e *throttling* ligado (a CPU é fraca; prefira reprodução direta).
4. Crie o usuário **`casa`** (**sem senha**, não administrador) com acesso às duas bibliotecas.
5. **Login automático do `casa`** (como administrador):
   ```powershell
   .\scripts\jellyfin\instalar_autologin.ps1
   ```
   Para entrar como administrador depois: `http://ENDERECO:8096/?manual=1`.
6. Crie uma **chave de API** (Painel → Chaves de API) e coloque em `JELLYFIN_API_KEY` no `.env`. O painel a usa para mostrar quem está assistindo e atualizar a biblioteca.

Pronto: a página **Filmes** do painel mostra o Jellyfin dentro dela.

## 7. Instalar o emulador dos jogos (EmulatorJS)

1. Baixe a versão `4.2.3` do **release oficial** em <https://github.com/EmulatorJS/EmulatorJS/releases> (arquivo `.7z`, ~290 MB, já com os núcleos).
2. Extraia com o 7-Zip (`winget install --id 7zip.7zip -e`) para `C:\AliciaServer\emulatorjs` de modo que exista `C:\AliciaServer\emulatorjs\data\loader.js`. Se usar outra pasta, defina `ALICIA_EJS`.
3. Coloque seus jogos pelo painel (**Jogos → Adicionar jogos**) ou nas pastas `Jogos\<Console>`. BIOS do PlayStation em `Jogos\BIOS`.

## 8. Tarefas automáticas, firewall e energia

Num PowerShell **como administrador**:
```powershell
.\scripts\instalar_tarefas.ps1
```
Cria as tarefas `AliciaServer-Painel`, `AliciaServer-Hermes`, `AliciaServer-Monitor` e `AliciaServer-Backup` (03:30), libera as portas **8080** e **8096** apenas para a rede de casa e o Tailscale e aplica as configurações de energia.

> As tarefas começam quando o usuário **entra no Windows**. Para subir sozinhas depois de um reinício sem ninguém digitar a senha, configure o **login automático do Windows** (`netplwiz`). Isso exige a senha da conta e é uma decisão sua; veja os riscos em [SEGURANCA.md](SEGURANCA.md).

## 9. Rede privada (Tailscale) e administração remota

```powershell
winget install --id Tailscale.Tailscale -e
# abra o Tailscale e entre na sua conta (no notebook, no PC, no celular e na TV box: a MESMA conta)
```
- No site <https://login.tailscale.com> → **Machines**: ⋯ do notebook → **Disable key expiry** (para o acesso não expirar).
- Anote o IP `100.x.y.z` do notebook: é o endereço para usar fora de casa.
- **SSH** para administrar de longe:
  ```powershell
  Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
  Set-Service sshd -StartupType Automatic; Start-Service sshd
  Get-NetFirewallRule -DisplayName "OpenSSH*" | Set-NetFirewallRule -RemoteAddress LocalSubnet,100.64.0.0/10
  ```
- **Nenhuma porta** é aberta no roteador.

## 10. Pasta de rede (opcional)

```powershell
New-SmbShare -Name "AliciaServer" -Path "C:\AliciaServer\Alicia Server" -FullAccess "$env:USERDOMAIN\$env:USERNAME"
Set-NetConnectionProfile -InterfaceAlias "Wi-Fi" -NetworkCategory Private
```
No PC: Explorador → Mapear unidade de rede → `\\IP-DO-SERVIDOR\AliciaServer`.
⚠️ O Windows **bloqueia** acesso pela rede a contas **sem senha**. Se a conta do servidor não tem senha, use o painel para enviar arquivos.

## 11. Conferir tudo

1. Painel → **Configurações → Verificar tudo**: testa painel, disco, Jellyfin, emulador, Tailscale, Hermes, chave da NVIDIA, Alicia, modo sem filtro, mestra do RPG e dados. Cada item mostra ✓ ou ✗ e o que fazer.
2. Reinicie o notebook (com a tampa fechada, se quiser testar) e veja se o terminal do **monitor** abre sozinho e se o painel responde.
3. No celular com o Tailscale ligado, abra `http://100.x.y.z:8080`.

## 12. Usuários, visitante e família

- **Configurações → Usuários e senhas:** crie um usuário para cada morador.
- **Entrada de visitante:** ligada por padrão; desligue em Configurações se não quiser.
- Para o RPG com amigos, cada jogador usa um usuário (ou o visitante).

## 13. App Android

Veja [APK.md](APK.md) e [`alicia-apk/COMPILAR_NO_PC.md`](../alicia-apk/COMPILAR_NO_PC.md).

## 14. Atualizando

```powershell
git pull
painel\.venv\Scripts\python.exe -m pip install -r painel\requirements.txt
# reinicie o painel: Stop-ScheduledTask AliciaServer-Painel; Start-ScheduledTask AliciaServer-Painel
```

## Algo deu errado?

Veja [PROBLEMAS.md](PROBLEMAS.md): serviço parado, disco cheio, sem acesso de fora, Jellyfin pedindo senha, login que não entra e outros.
