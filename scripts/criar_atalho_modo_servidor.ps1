<#
  Cria o atalho "Alicia - Modo Servidor" na Área de Trabalho (abre o terminal de controle COMO ADMINISTRADOR).
  Rode uma vez:   .\scripts\criar_atalho_modo_servidor.ps1
#>
$raiz = Split-Path $PSScriptRoot -Parent
$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) "Alicia - Modo Servidor.lnk"
$sc = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$sc.TargetPath = "$raiz\scripts\modo_servidor.cmd"; $sc.WorkingDirectory = "$raiz\scripts"
$sc.IconLocation = "$env:SystemRoot\System32\shell32.dll,24"; $sc.Description = "Terminal do Modo Servidor (só neste notebook)"; $sc.Save()
$b = [IO.File]::ReadAllBytes($lnk); $b[0x15] = $b[0x15] -bor 0x20; [IO.File]::WriteAllBytes($lnk, $b)   # marca "executar como administrador"
Write-Host "Atalho criado: $lnk"