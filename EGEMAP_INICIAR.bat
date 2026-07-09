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
(
echo @echo off
echo powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "%DESTINO%\watcher.ps1"
) > "%USERPROFILE%\Desktop\INICIAR_AGENTE.bat"
echo        OK.

echo  [2/3] Configurando inicio automatico com o Windows...
powershell -ExecutionPolicy Bypass -Command ^
  "$a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-WindowStyle Hidden -ExecutionPolicy Bypass -File \"%DESTINO%\watcher.ps1\"'; $t = New-ScheduledTaskTrigger -AtLogOn; $s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0; Register-ScheduledTask -TaskName 'EgemapDriveWatcher' -Action $a -Trigger $t -Settings $s -RunLevel Highest -Force | Out-Null"
if errorlevel 1 (
    echo        [AVISO] Nao foi possivel criar tarefa automatica.
) else (
    echo        OK. Agente vai iniciar sozinho ao ligar o computador.
)

echo  [3/3] Iniciando o agente agora...
powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "%DESTINO%\watcher.ps1"
echo        OK. Agente rodando em segundo plano.

echo.
echo  =============================================
echo    PRONTO!
echo.
echo    O agente esta rodando agora.
echo    Salve PDFs assim:
echo    ORCAMENTOS\Ano\Estado\Cidade\Cliente\arq.pdf
echo.
echo    O Drive e atualizado automaticamente.
echo    Log em: %DESTINO%\watcher.log
echo  =============================================
echo.
pause
