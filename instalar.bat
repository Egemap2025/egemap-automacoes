@echo off
title Egemap - Instalador

echo.
echo === EGEMAP AUTOMACOES - Instalador ===
echo.

node --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Node.js nao encontrado!
    echo Acesse nodejs.org e instale o Node.js LTS
    pause
    exit /b 1
)

echo Node.js OK
echo.

if not exist ".env" (
    echo ERRO: Arquivo .env nao encontrado!
    echo Crie o arquivo .env nesta pasta e tente novamente.
    pause
    exit /b 1
)

echo Arquivo .env OK
echo.

echo [1/3] Instalando dependencias... aguarde...
call npm install
if errorlevel 1 (
    echo ERRO: Falha ao instalar dependencias
    pause
    exit /b 1
)
echo OK
echo.

echo [2/3] Compilando...
call npm run build
if errorlevel 1 (
    echo ERRO: Falha na compilacao
    pause
    exit /b 1
)
echo OK
echo.

echo [3/3] Instalando navegador Chromium...
call npx playwright install chromium
echo OK
echo.

echo =====================================
echo   INSTALACAO CONCLUIDA!
echo   Agora execute: iniciar.bat
echo =====================================
echo.
pause
