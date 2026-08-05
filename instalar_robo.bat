@echo off
echo =============================================
echo   EGEMAP - Instalando o Robo de Orcamentos
echo =============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado.
    echo Instale o Python em https://www.python.org/downloads/
    echo Marque a opcao "Add Python to PATH" durante a instalacao.
    pause
    exit /b 1
)

echo Instalando o Playwright...
pip install playwright

echo.
echo =============================================
echo   Instalacao concluida!
echo   Execute "iniciar_robo.bat" para abrir o robo.
echo =============================================
pause
