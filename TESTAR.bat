@echo off
setlocal
set PROJETO=%~dp0
if "%PROJETO:~-1%"=="\" set PROJETO=%PROJETO:~0,-1%

chcp 65001 >nul
title Testando Agente de Orcamentos...

echo.
echo  Testando conexao com o Google Drive...
echo.

if not exist "%PROJETO%\rclone.exe" (
    echo  [ERRO] rclone.exe nao encontrado.
    echo         Execute INSTALAR.bat primeiro.
    pause
    exit /b 1
)

if not exist "%PROJETO%\rclone.conf" (
    echo  [ERRO] rclone.conf nao encontrado.
    echo         Execute INSTALAR.bat primeiro.
    pause
    exit /b 1
)

:: Testar conexao listando a pasta raiz
echo  Verificando acesso a pasta "Pedidos e Contratos"...
"%PROJETO%\rclone.exe" lsd "egemap:" --config "%PROJETO%\rclone.conf" 2>&1
if errorlevel 1 (
    echo.
    echo  [ERRO] Nao foi possivel conectar ao Drive.
    echo         Execute INSTALAR.bat novamente para reautorizar.
    pause
    exit /b 1
)

echo.
echo  Criando pasta de teste no Drive...
"%PROJETO%\rclone.exe" mkdir "egemap:2026/_TESTE_AGENTE/Verificacao" --config "%PROJETO%\rclone.conf"
if errorlevel 1 (
    echo  [ERRO] Nao foi possivel criar pasta no Drive.
    pause
    exit /b 1
)

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   Tudo funcionando!                          ║
echo  ║                                              ║
echo  ║   Pode apagar a pasta _TESTE_AGENTE          ║
echo  ║   no Drive se quiser.                        ║
echo  ╚══════════════════════════════════════════════╝
echo.
pause
endlocal
