@echo off
:: Inicia o agente manualmente (caso precise reiniciar sem reiniciar o Windows)
setlocal
set PROJETO=%~dp0
if "%PROJETO:~-1%"=="\" set PROJETO=%PROJETO:~0,-1%

echo Iniciando Agente de Orcamentos...
start "" /B pythonw.exe "%PROJETO%\watcher.py"
if errorlevel 1 (
    start "" /MIN python.exe "%PROJETO%\watcher.py"
)
echo Agente iniciado em segundo plano.
echo Verifique o arquivo watcher.log para acompanhar o que esta acontecendo.
timeout /t 3 >nul
endlocal
