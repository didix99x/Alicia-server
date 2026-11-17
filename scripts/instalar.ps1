<#
  Alicia Server — instalação do painel (passo 1 do docs/INSTALACAO.md).
  Rode num PowerShell normal, na pasta do projeto:   .\scripts\instalar.ps1
  O que faz: cria o ambiente Python do painel, instala as bibliotecas (versões fixadas), cria as pastas de dados,
  cria o .env a partir do exemplo e cria o usuário administrador (a senha vai para PRIMEIRO_ACESSO.txt, fora do Git).
#>
param(
  [string]$Dados  = "C:\AliciaServer\Alicia Server",   # onde ficam Documentos, Filmes, Séries, Jogos e Música
  [string]$Admin  = "admin"                            # nome do primeiro usuário
)
$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
Set-Location $raiz

Write-Host "1/5  Conferindo o Python 3.12..." -ForegroundColor Cyan
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { throw "Python não encontrado. Instale com: winget install --id Python.Python.3.12 -e" }
python --version

Write-Host "2/5  Criando o ambiente do painel (painel\.venv)..." -ForegroundColor Cyan
if (-not (Test-Path "painel\.venv")) { python -m venv painel\.venv }
& "painel\.venv\Scripts\python.exe" -m pip install --upgrade pip
& "painel\.venv\Scripts\python.exe" -m pip install -r painel\requirements.txt

Write-Host "3/5  Criando pastas..." -ForegroundColor Cyan
foreach ($d in "logs", "dados", $Dados) { New-Item -ItemType Directory -Force $d | Out-Null }
foreach ($d in "Documentos", "Filmes", "Séries", "Jogos", "Música") { New-Item -ItemType Directory -Force (Join-Path $Dados $d) | Out-Null }
foreach ($d in "Nintendo", "Super Nintendo", "Nintendo 64", "Game Boy", "Game Boy Advance", "PlayStation", "BIOS", "Saves") { New-Item -ItemType Directory -Force (Join-Path $Dados "Jogos\$d") | Out-Null }

Write-Host "4/5  Criando o .env (as chaves entram depois, pelo painel)..." -ForegroundColor Cyan
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

Write-Host "5/5  Criando o usuário administrador '$Admin'..." -ForegroundColor Cyan
if (-not (Test-Path "painel\usuarios.json")) { & "painel\.venv\Scripts\python.exe" scripts\criar_usuario.py $Admin --admin }

Write-Host ""
Write-Host "Pronto. Para testar agora:" -ForegroundColor Green
Write-Host "  `$env:ALICIA_DADOS = '$Dados'; `$env:PYTHONPATH = 'painel'"
Write-Host "  painel\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --app-dir painel"
Write-Host "Abra http://localhost:8080 (a senha do administrador está em PRIMEIRO_ACESSO.txt)."
Write-Host "Para iniciar tudo sozinho ao ligar o PC, rode (como administrador): .\scripts\instalar_tarefas.ps1"