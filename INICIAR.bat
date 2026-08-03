@echo off
cd /d "%~dp0"
title W-vetro - Editor de Orcamentos

echo.
echo  ==========================================
echo   W-vetro - Editor de Orcamentos
echo  ==========================================
echo.

where node >nul 2>&1
if errorlevel 1 (
    echo  ERRO: Node.js nao esta instalado!
    echo  Baixe em: https://nodejs.org/
    echo.
    pause
    exit /b 1
)

if not exist "%~dp0node_modules" (
    echo  Instalando dependencias pela primeira vez...
    echo.
    call npm install
    if errorlevel 1 (
        echo.
        echo  ERRO na instalacao!
        pause
        exit /b 1
    )
    echo.
)

echo  Iniciando...
echo.
cmd /k node "%~dp0src\alterar-orcamento.js"
