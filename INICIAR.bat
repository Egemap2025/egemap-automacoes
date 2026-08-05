@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title W-vetro - Editor de Orcamentos
chcp 65001 >nul 2>&1

echo.
echo  ==========================================
echo   W-vetro - Editor de Orcamentos
echo  ==========================================
echo.

:: ── Verificar Node.js ──────────────────────────────────────────────────────
where node >nul 2>&1
if errorlevel 1 (
    echo  ERRO: Node.js nao esta instalado!
    echo  Acesse https://nodejs.org/ , baixe e instale.
    echo.
    pause
    exit /b 1
)

:: ── Instalar dependencias (so na primeira vez) ─────────────────────────────
if not exist "%~dp0node_modules" (
    echo  Instalando dependencias pela primeira vez...
    echo  Aguarde, pode demorar alguns minutos...
    echo.
    cd /d "%~dp0"
    call npm install
    if errorlevel 1 (
        echo.
        echo  ERRO na instalacao das dependencias!
        pause
        exit /b 1
    )
    echo.
)

:: ── Configurar login (so na primeira vez) ──────────────────────────────────
if not exist "%~dp0.env" (
    echo  ==========================================
    echo   Primeira vez! Configure seu login:
    echo  ==========================================
    echo.
    set /p WV_USER="  Usuario W-vetro: "
    echo.
    set /p WV_PASS="  Senha: "
    echo.
    set /p WV_LIC="  Numero da Licenca: "
    echo.
    (
        echo WVETRO_USUARIO=!WV_USER!
        echo WVETRO_SENHA=!WV_PASS!
        echo WVETRO_LICENCA=!WV_LIC!
    ) > "%~dp0.env"
    echo  Login salvo! Proxima vez vai entrar automatico.
    echo.
)

:: ── Iniciar ────────────────────────────────────────────────────────────────
echo  Iniciando...
echo.
cmd /k node "%~dp0src\alterar-orcamento.js"
