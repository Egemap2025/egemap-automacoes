@echo off
echo Parando o Agente de Orcamentos...
taskkill /F /FI "WINDOWTITLE eq Agente de Orcamentos*" >nul 2>&1
powershell -Command "Get-Process powershell | Where-Object { $_.CommandLine -like '*watcher.ps1*' } | Stop-Process -Force" >nul 2>&1
echo Agente parado.
pause
