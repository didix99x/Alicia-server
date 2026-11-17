@echo off
title Alicia Server - Monitor de acessos
set "RAIZ=%~dp0.."
:loop
"%RAIZ%\painel\.venv\Scripts\python.exe" "%RAIZ%\scripts\monitor.py"
timeout /t 3 >nul
goto loop