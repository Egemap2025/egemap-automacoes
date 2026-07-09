@echo off
chcp 65001 >nul 2>&1
title Egemap - Iniciando Agente

echo.
echo  =============================================
echo    Egemap - Configurando e Iniciando Agente
echo  =============================================
echo.

set DESTINO=%USERPROFILE%\EgemapDrive

if not exist "%DESTINO%\watcher.ps1" (
    echo  [ERRO] Agente nao encontrado em %DESTINO%
    echo         Execute primeiro o EGEMAP_INSTALAR.bat
    pause & exit /b 1
)

echo  [1/3] Criando atalho na area de trabalho...
for /f "delims=" %%i in ('powershell -NoProfile -Command "[Environment]::GetFolderPath(\"Desktop\")"') do set DESKTOP=%%i
(
echo @echo off
echo start "" /B powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "%DESTINO%\watcher.ps1"
) > "%DESKTOP%\INICIAR_AGENTE.bat"
echo        OK. Atalho criado em: %DESKTOP%\INICIAR_AGENTE.bat

echo  [2/3] Configurando inicio automatico com o Windows...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "EgemapDriveWatcher" /t REG_SZ /d "powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File \"%DESTINO%\watcher.ps1\"" /f >nul 2>&1
if errorlevel 1 (
    echo        [AVISO] Nao foi possivel configurar inicio automatico.
) else (
    echo        OK. Agente vai iniciar sozinho ao ligar o computador.
)

echo  [3/3] Iniciando o agente agora...
start "" /B powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "%DESTINO%\watcher.ps1"
echo        OK. Agente rodando em segundo plano.

echo.
echo  =============================================
echo    PRONTO! Esta janela pode ser fechada.
echo.
echo    O agente esta rodando em segundo plano.
echo    Log em: %DESTINO%\watcher.log
echo  =============================================
echo.
pause
