@echo off
cd /d "%~dp0"

echo.
echo  ==========================================
echo   W-vetro - Automacao de Orcamentos
echo  ==========================================
echo.

if not exist "node_modules" (
    echo  Primeira execucao: instalando dependencias...
    echo  (isso so acontece uma vez, aguarde)
    echo.
    npm install
    if errorlevel 1 (
        echo.
        echo  ERRO ao instalar dependencias.
        echo  Verifique se o Node.js esta instalado: https://nodejs.org/
        echo.
        pause
        exit /b 1
    )
    echo.
    echo  Instalacao concluida!
    echo.
)

npm start

echo.
pause
