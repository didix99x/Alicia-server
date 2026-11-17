@echo off
rem Inicia o painel (porta 8080) e o reinicia sozinho se cair. Caminhos relativos a esta pasta.
set "RAIZ=%~dp0.."
set PYTHONPATH=%RAIZ%\painel
:loop
"%RAIZ%\painel\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --app-dir "%RAIZ%\painel" 2>>"%RAIZ%\logs\painel.err"
timeout /t 5 >nul
goto loop