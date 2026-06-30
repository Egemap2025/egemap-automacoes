@echo off
chcp 65001 >nul
title Egemap Automações - Instalador

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║     EGEMAP AUTOMAÇÕES - Instalador       ║
echo  ╚══════════════════════════════════════════╝
echo.

:: Verifica Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo  [ERRO] Node.js nao encontrado!
    echo.
    echo  Instale o Node.js antes de continuar:
    echo  1. Acesse: https://nodejs.org
    echo  2. Clique em "Download Node.js LTS"
    echo  3. Instale com todas as opcoes padrao
    echo  4. Reinicie o computador
    echo  5. Execute este arquivo novamente
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('node --version') do set NODE_VER=%%i
echo  [OK] Node.js %NODE_VER% encontrado
echo.

:: Verifica .env
if not exist ".env" (
    echo  [ERRO] Arquivo .env nao encontrado!
    echo.
    echo  Coloque o arquivo .env nesta pasta e tente novamente.
    echo  (O arquivo .env foi enviado junto com as instrucoes)
    echo.
    pause
    exit /b 1
)
echo  [OK] Arquivo .env encontrado
echo.

echo  [1/3] Instalando dependencias (pode demorar 2-3 minutos)...
call npm install --silent
if errorlevel 1 (
    echo  [ERRO] Falha ao instalar dependencias
    pause
    exit /b 1
)
echo  [OK] Dependencias instaladas
echo.

echo  [2/3] Compilando o projeto...
call npm run build
if errorlevel 1 (
    echo  [ERRO] Falha na compilacao
    pause
    exit /b 1
)
echo  [OK] Projeto compilado
echo.

echo  [3/3] Configurando navegador (Chromium)...
call npx playwright install chromium
if errorlevel 1 (
    echo  [AVISO] Falha ao instalar Chromium - continuando mesmo assim
) else (
    echo  [OK] Chromium configurado
)
echo.

echo  ╔══════════════════════════════════════════╗
echo  ║         INSTALACAO CONCLUIDA!            ║
echo  ║                                          ║
echo  ║  Para iniciar o bot, execute:            ║
echo  ║  >> iniciar.bat                          ║
echo  ╚══════════════════════════════════════════╝
echo.
pause
