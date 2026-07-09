@echo off
title Egemap - Instalando agente de orcamentos...
set PS1=%TEMP%\egemap_instalar.ps1
echo Baixando instalador, aguarde...
powershell -ExecutionPolicy Bypass -NoProfile -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/Egemap2025/egemap-automacoes/claude/budget-folder-drive-automation-q48tvv/EGEMAP_INSTALAR.ps1' -OutFile '%PS1%' -UseBasicParsing"
if not exist "%PS1%" (
    echo.
    echo Erro: nao foi possivel baixar. Verifique sua internet.
    pause
    exit /b 1
)
powershell -ExecutionPolicy Bypass -File "%PS1%"
