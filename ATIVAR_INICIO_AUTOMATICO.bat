@echo off
:: Registra o EGEMAP-Monitor para abrir automaticamente quando o Windows ligar.
:: Execute este arquivo UMA VEZ, com o EGEMAP-Monitor.exe na mesma pasta.

SET "EXE=%~dp0EGEMAP-Monitor.exe"

IF NOT EXIST "%EXE%" (
    echo.
    echo ERRO: EGEMAP-Monitor.exe nao encontrado nesta pasta.
    echo Coloque este arquivo BAT na mesma pasta do EGEMAP-Monitor.exe
    echo e execute novamente.
    echo.
    pause
    exit /b 1
)

REG ADD "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" ^
    /v "EGEMAP-Monitor" /t REG_SZ /d "\"%EXE%\"" /f >nul

echo.
echo ============================================================
echo   EGEMAP-Monitor configurado para iniciar com o Windows!
echo ============================================================
echo.
echo   O monitor vai abrir automaticamente toda vez que
echo   voce ligar ou reiniciar o computador.
echo.
echo   Para desativar o inicio automatico, execute:
echo   DESATIVAR_INICIO_AUTOMATICO.bat
echo.
pause
