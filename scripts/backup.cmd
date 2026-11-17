@echo off
rem Backup diario: Documentos + configuracao do servidor (sem .venv, logs nem .git). Destino padrao: C:\AliciaServer\Backup
set "RAIZ=%~dp0.."
if not defined ALICIA_DADOS set "ALICIA_DADOS=C:\AliciaServer\Alicia Server"
if not defined ALICIA_BACKUP set "ALICIA_BACKUP=C:\AliciaServer\Backup"
robocopy "%ALICIA_DADOS%\Documentos" "%ALICIA_BACKUP%\Documentos" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS >nul
robocopy "%RAIZ%" "%ALICIA_BACKUP%\configuracao" /MIR /XD .venv __pycache__ .git logs /XF *.log /R:1 /W:1 /NFL /NDL /NJH /NJS >nul