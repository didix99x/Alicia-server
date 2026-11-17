<#
  Alicia Server — tarefas automáticas e firewall (passo 8 do docs/INSTALACAO.md).
  Rode num PowerShell COMO ADMINISTRADOR:   .\scripts\instalar_tarefas.ps1
  Cria as tarefas que iniciam o painel, o Hermes e o monitor quando você entra no Windows, o backup diário (03:30),
  e libera as portas SOMENTE para a rede de casa e para a faixa do Tailscale (100.64.0.0/10).
  O painel e o Hermes rodam como usuário NORMAL (o Hermes se recusa a rodar como administrador).
#>
$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
$usuario = "$env:USERDOMAIN\$env:USERNAME"
$cfg = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1)
$gatilho = New-ScheduledTaskTrigger -AtLogOn -User $usuario
$normal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited

function Tarefa($nome, $exe, $args_, $gat) {
  Register-ScheduledTask -TaskName $nome -Force -Trigger $gat -Settings $cfg -Principal $normal -Action (New-ScheduledTaskAction -Execute $exe -Argument $args_) | Out-Null
  Write-Host "tarefa criada: $nome"
}
Tarefa "AliciaServer-Painel"  "wscript.exe" "`"$raiz\scripts\iniciar_painel_oculto.vbs`"" $gatilho
Tarefa "AliciaServer-Hermes"  "wscript.exe" "`"$raiz\scripts\iniciar_hermes_oculto.vbs`"" $gatilho
Tarefa "AliciaServer-Monitor" "cmd.exe"     "/c start `"`" /max `"$raiz\scripts\iniciar_monitor.cmd`"" $gatilho
Register-ScheduledTask -TaskName "AliciaServer-Backup" -Force -Trigger (New-ScheduledTaskTrigger -Daily -At 03:30) `
  -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries) -Principal $normal `
  -Action (New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$raiz\scripts\backup.cmd`"") | Out-Null
Write-Host "tarefa criada: AliciaServer-Backup"

# Firewall: só rede de casa (LocalSubnet) e Tailscale
$remotos = "LocalSubnet", "100.64.0.0/10"
foreach ($r in @(@("Alicia Server painel 8080", 8080), @("Alicia Server Jellyfin 8096", 8096))) {
  if (-not (Get-NetFirewallRule -DisplayName $r[0] -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $r[0] -Direction Inbound -Protocol TCP -LocalPort $r[1] -RemoteAddress $remotos -Action Allow -Profile Any | Out-Null
    Write-Host "firewall: $($r[0]) liberada só para a rede de casa e o Tailscale"
  }
}

# Economia de energia: nunca suspender/hibernar na tomada e tampa fechada = nada
powercfg /change standby-timeout-ac 0
powercfg /hibernate off
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setactive SCHEME_CURRENT
Write-Host "Energia configurada. Faça logoff/login (ou reinicie) para as tarefas começarem."