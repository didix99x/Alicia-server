<#
  Jellyfin: login automático do usuário "casa" (sem senha). Rode COMO ADMINISTRADOR depois de criar o usuário "casa" no Jellyfin:
      .\scripts\jellyfin\instalar_autologin.ps1
  Copia o script para a pasta do site do Jellyfin e liga ele no index.html (o original fica em index.html.original).
  Uma atualização do Jellyfin pode apagar isso: é só rodar de novo.
  Para entrar como administrador depois, abra  http://ENDERECO:8096/?manual=1
#>
param([string]$Web = "C:\Program Files\Jellyfin\Server\jellyfin-web")
$ErrorActionPreference = "Stop"
if (-not (Test-Path "$Web\index.html")) { throw "Não achei $Web\index.html. Passe a pasta com -Web." }
Copy-Item "$PSScriptRoot\alicia-autologin.js" "$Web\alicia-autologin.js" -Force
if (-not (Test-Path "$Web\index.html.original")) { Copy-Item "$Web\index.html" "$Web\index.html.original" }
$html = [IO.File]::ReadAllText("$Web\index.html.original")
$html = $html.Replace("<head>", '<head><script src="alicia-autologin.js"></script>')
[IO.File]::WriteAllText("$Web\index.html", $html, (New-Object Text.UTF8Encoding $false))
Write-Host "Pronto. Abra o Jellyfin num navegador: ele deve entrar sozinho como 'casa'."