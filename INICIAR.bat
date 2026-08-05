@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title W-vetro - Editor de Orcamentos

echo.
echo  ==========================================
echo   W-vetro - Editor de Orcamentos
echo  ==========================================
echo.

:: Verificar Node.js
where node >nul 2>&1
if errorlevel 1 (
    echo  ERRO: Node.js nao esta instalado!
    echo  Baixe em: https://nodejs.org/
    echo.
    pause
    exit /b 1
)

:: Instalar dependencias se necessario
if not exist "%~dp0node_modules" (
    echo  Instalando dependencias pela primeira vez...
    echo  Aguarde alguns minutos...
    echo.
    cd /d "%~dp0"
    call npm install
    if errorlevel 1 (
        echo.
        echo  ERRO na instalacao!
        pause
        exit /b 1
    )
    echo.
)

:: Configurar login se necessario (so na primeira vez)
if not exist "%~dp0.env" (
    echo  ==========================================
    echo   Primeira vez! Configure seu login:
    echo  ==========================================
    echo.
    set /p WV_USER="  Usuario W-vetro: "
    echo.
    set /p WV_PASS="  Senha: "
    echo.
    set /p WV_LIC="  Licenca (numero): "
    echo.
    echo WVETRO_USUARIO=!WV_USER!> "%~dp0.env"
    echo WVETRO_SENHA=!WV_PASS!>> "%~dp0.env"
    echo WVETRO_LICENCA=!WV_LIC!>> "%~dp0.env"
    echo  Login salvo! Proxima vez entra automatico.
    echo.
)

:: Iniciar
echo  Iniciando...
echo.
cmd /k node "%~dp0src\alterar-orcamento.js"
