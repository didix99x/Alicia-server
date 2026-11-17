# Roda um comando do Hermes SEM privilégios de administrador (o Hermes recusa rodar elevado).
# Uso: hermes_normal.ps1 "<argumentos do hermes>"  -> saída em logs\hermes_saida.txt
param([string]$Args1, [string]$Base = "", [string]$Chave = "")
$p = Split-Path $PSScriptRoot -Parent
$cmd = "`$env:Path=[Environment]::GetEnvironmentVariable('Path','User')+';'+[Environment]::GetEnvironmentVariable('Path','Machine'); " +
       $(if($Base){"`$env:NVIDIA_BASE_URL='$Base'; "}) + $(if($Chave){"`$env:NVIDIA_API_KEY='$Chave'; "}) +
       "$env:HERMES_HOME='C:\AliciaServer\hermes'; & 'C:\AliciaServer\hermes\bin\hermes.exe' $Args1 *> '$p\logs\hermes_saida.txt'"
$u = "$env:USERDOMAIN\$env:USERNAME"
Unregister-ScheduledTask -TaskName AliciaHermesTmp -Confirm:$false -EA SilentlyContinue
Register-ScheduledTask -TaskName AliciaHermesTmp -Principal (New-ScheduledTaskPrincipal -UserId $u -LogonType Interactive -RunLevel Limited) `
  -Action (New-ScheduledTaskAction -Execute powershell.exe -Argument "-NoProfile -WindowStyle Hidden -EncodedCommand $([Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($cmd)))") | Out-Null
Start-ScheduledTask AliciaHermesTmp
do { Start-Sleep 2 } while ((Get-ScheduledTask AliciaHermesTmp).State -eq 'Running')
Unregister-ScheduledTask -TaskName AliciaHermesTmp -Confirm:$false
Get-Content "$p\logs\hermes_saida.txt" -Encoding utf8


