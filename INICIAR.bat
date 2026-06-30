@echo off
setlocal
set PROJETO=%~dp0
if "%PROJETO:~-1%"=="\" set PROJETO=%PROJETO:~0,-1%
powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "%PROJETO%\watcher.ps1"
endlocal
