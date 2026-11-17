# Compilar o app Android do Alicia Server (no PC com Windows 11)

> Este arquivo é independente: quem for compilar não precisa ter visto a conversa que criou o projeto.

## O que é isto
**Alicia Server** é um servidor doméstico (notebook ligado 24h) com um painel web em `http://<endereço>:8080` (Alicia, arquivos, filmes, jogos, música, RPG).
Esta pasta (`alicia-apk`) é um app Android **simples**: uma `WebView` que mostra esse painel, para celular e TV box.

**Escolha e motivo:** WebView nativo em Java (sem Capacitor/Node/PWA). É o caminho mais simples, só depende de Gradle/Android SDK, não precisa de internet no app além do próprio servidor e deixa trocar o endereço do servidor dentro do app (botão ⚙ ou tecla MENU do controle), sem gerar outro APK.
Recursos: tela deitada, navegação por setas/OK (a WebView já usa o foco do controle), microfone com pedido de permissão do Android (sem microfone, o chat por texto continua), `usesCleartextTraffic` (o painel usa `http` dentro da rede privada).

## Dica
Copie esta pasta `alicia-apk` para o disco do PC (ex.: `C:\alicia-apk`) antes de compilar. Compilar direto pela rede (`\\alicia-server\...`) é lento.

## 1. Instalar (tudo gratuito, em PowerShell)
```powershell
winget install --id EclipseAdoptium.Temurin.17.JDK -e
winget install --id Gradle.Gradle -e
winget install --id Google.AndroidStudio -e     # só para obter o Android SDK; ou use as "command line tools"
```
Abra o Android Studio uma vez → *More Actions → SDK Manager* e instale: **Android SDK Platform 34** e **Android SDK Build-Tools 34**. Anote o caminho do SDK (normalmente `C:\Users\<você>\AppData\Local\Android\Sdk`).
Feche e abra o PowerShell de novo.

## 2. Preparar o projeto
```powershell
cd C:\alicia-apk
"sdk.dir=C\:\\Users\\<VOCÊ>\\AppData\\Local\\Android\\Sdk" | Out-File -Encoding ascii local.properties
gradle wrapper --gradle-version 8.7
```
(Troque `<VOCÊ>` pelo seu usuário do Windows.)

## 3. Gerar a chave de assinatura (uma vez só — guarde o arquivo!)
```powershell
keytool -genkeypair -v -keystore alicia.jks -alias alicia -keyalg RSA -keysize 2048 -validity 10000
```
Crie `keystore.properties` ao lado do `settings.gradle.kts`:
```
storeFile=alicia.jks
storePassword=SUA_SENHA
keyAlias=alicia
keyPassword=SUA_SENHA
```
**Nunca** envie `alicia.jks` nem `keystore.properties` para o GitHub (já estão no `.gitignore`).

## 4. Compilar e assinar
```powershell
.\gradlew.bat assembleRelease
```
O APK assinado fica em `app\build\outputs\apk\release\app-release.apk`. Renomeie para `AliciaServer.apk`.
(Sem `keystore.properties`, o Gradle gera `app-release-unsigned.apk`, que o Android não instala.)

## 5. Instalar
- **Celular:** envie o APK (cabo, Drive, pela pasta compartilhada) → abra → permita "instalar apps desconhecidos" só para o gerenciador de arquivos.
- **TV box:** copie para um pendrive ou use o `adb`:
  ```powershell
  adb connect <IP-da-TV-box>:5555
  adb install -r AliciaServer.apk
  ```
  (Ative *Opções do desenvolvedor → Depuração USB/rede* na TV box.)
- **Rede privada (Tailscale):** instale o app **Tailscale** (Play Store) no celular e na TV box, entre com a MESMA conta usada no servidor. Depois, no app Alicia Server, toque em ⚙ (ou MENU no controle) e digite `http://<IP-100.x.x.x-do-alicia-server>:8080`. Em casa também funciona `http://IP-DO-SERVIDOR:8080`.

## 6. Testar
Abra o app → digite o endereço → deve aparecer a tela de login do painel. Entre, abra *Alicia* e toque no microfone (celular: o Android pede permissão). Na TV box use setas/OK.

## Problemas prováveis
| Sintoma | Solução |
|---|---|
| `SDK location not found` | Faltou `local.properties` (passo 2) ou o caminho está errado. |
| `JAVA_HOME`/versão do Java | Use o JDK 17 (`java -version`). |
| "App não instalado" | O APK não está assinado (passo 3) ou já existe uma versão assinada com outra chave: desinstale a antiga. |
| Tela com "Não consegui falar com o Alicia Server" | Servidor desligado, Tailscale sem conexão, ou endereço errado (⚙). |
| Gradle baixa muito / demora | Normal na primeira vez; precisa de internet. |
| Sem som/voz na TV box | A TV box pode não ter microfone; use o chat por texto. |

> Nota honesta de quem criou o projeto: o código **não foi compilado** no notebook servidor (sem JDK/SDK por decisão do projeto). Se algum erro de compilação aparecer, corrija pelo log do Gradle; o app é pequeno (um arquivo Java + um layout).

## Filmes no app
A p�gina **Filmes** do painel mostra o Jellyfin dentro dela (porta 8096 do mesmo servidor), entrando sozinho como o usu�rio 'casa'. Funciona no app porque o app s� abre o endere�o do painel. Se preferir o app oficial do Jellyfin (Play Store/TV), use o endere�o do servidor com porta 8096 e o usu�rio casa (senha vazia). N�o testado no app compilado.
