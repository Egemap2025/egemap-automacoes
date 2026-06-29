@echo off
setlocal
set PROJETO=%~dp0
if "%PROJETO:~-1%"=="\" set PROJETO=%PROJETO:~0,-1%
cd /d "%PROJETO%"
python "%PROJETO%\testar_agente.py"
endlocal
