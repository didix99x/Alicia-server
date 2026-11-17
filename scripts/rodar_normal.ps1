param([string]$Exe,[string]$Argumentos)
$p = Split-Path $PSScriptRoot -Parent; $u="$env:USERDOMAIN\$env:USERNAME"; $out="$p\logs\normal_saida.txt"; Remove-Item $out -EA SilentlyContinue
$cmd = "& '$Exe' $Argumentos *> '$out'"
Unregister-ScheduledTask -TaskName AliciaNormalTmp -Confirm:$false -EA SilentlyContinue
Register-ScheduledTask -TaskName AliciaNormalTmp -Principal (New-ScheduledTaskPrincipal -UserId $u -LogonType Interactive -RunLevel Limited) -Action (New-ScheduledTaskAction -Execute powershell.exe -Argument "-NoProfile -WindowStyle Hidden -EncodedCommand $([Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($cmd)))") | Out-Null
Start-ScheduledTask AliciaNormalTmp; Start-Sleep 3
while ((Get-ScheduledTask AliciaNormalTmp).State -eq 'Running') { Start-Sleep 1 }
Unregister-ScheduledTask -TaskName AliciaNormalTmp -Confirm:$false
Get-Content $out -Encoding utf8 -EA SilentlyContinue
