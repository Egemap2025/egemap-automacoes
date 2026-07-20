@echo off
chcp 65001 >nul 2>&1
title Egemap - Login no Google Drive

echo.
echo  =============================================
echo    Egemap - Conectar ao Google Drive
echo  =============================================
echo.

set DESTINO=%USERPROFILE%\EgemapDrive

if not exist "%DESTINO%\rclone.exe" (
    echo  [ERRO] Pasta C:\EgemapDrive nao encontrada.
    echo         Execute primeiro o EGEMAP_INSTALAR.bat
    pause & exit /b 1
)

if not exist "%DESTINO%\rclone.conf" (
    echo  [ERRO] Configuracao nao encontrada.
    echo         Execute primeiro o EGEMAP_INSTALAR.bat
    pause & exit /b 1
)

echo  Abrindo o navegador para login no Google...
echo  Faca login com egemapesquadrias@gmail.com e clique em PERMITIR.
echo.

"%DESTINO%\rclone.exe" config reconnect egemap: --config "%DESTINO%\rclone.conf"

if errorlevel 1 (
    echo.
    echo  [ERRO] Login nao concluido. Tente novamente.
    pause & exit /b 1
)

echo.
echo  Login feito com sucesso!
echo  Iniciando o agente...
echo.

powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "%DESTINO%\watcher.ps1"

echo.
echo  Agente rodando! PDFs serao enviados automaticamente.
echo.
pause
