@echo off
echo =============================================
echo   EGEMAP - Instalando Montador de Propostas
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

echo Instalando dependencias...
pip install pymupdf

echo.
echo =============================================
echo   Instalacao concluida!
echo   Execute o arquivo "iniciar.bat" para abrir.
echo =============================================
pause
