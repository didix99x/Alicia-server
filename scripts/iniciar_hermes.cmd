@echo off
rem Inicia o gateway do Hermes (API local 127.0.0.1:8642). Deve rodar como usuario normal, nunca como administrador.
set "RAIZ=%~dp0.."
if not defined HERMES_EXE set "HERMES_EXE=C:\AliciaServer\hermes\bin\hermes.exe"
:loop
"%HERMES_EXE%" gateway run >> "%RAIZ%\logs\hermes_gateway.log" 2>&1
timeout /t 10 >nul
goto loop