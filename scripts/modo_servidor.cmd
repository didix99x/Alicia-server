@echo off
rem Terminal de controle do MODO SERVIDOR (só para esses comandos; só funciona no próprio notebook).
chcp 65001 >nul
title ALICIA - MODO SERVIDOR
set "RAIZ=%~dp0.."
mode con: cols=110 lines=32 >nul 2>&1
color 0F
:loop
"%RAIZ%\painel\.venv\Scripts\python.exe" "%RAIZ%\scripts\modo_servidor.py"
if errorlevel 1 (
  echo.
  echo Pressione uma tecla para fechar.
  pause >nul
)
exit /b