@echo off
:: ============================================================
::  Instalador do Agente de Orcamentos no Drive
::  Execute UMA VEZ. Depois o agente inicia sozinho com o Windows.
:: ============================================================

setlocal
set PROJETO=%~dp0
:: Remove a barra final do caminho
if "%PROJETO:~-1%"=="\" set PROJETO=%PROJETO:~0,-1%

title Instalando Agente de Orcamentos...
echo ============================================================
echo   Instalando Agente de Orcamentos no Drive
echo ============================================================
echo.

:: ── Verificar se Python esta instalado ──────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado!
    echo.
    echo Instale o Python antes de continuar:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANTE: Marque a opcao "Add Python to PATH"
    echo durante a instalacao.
    echo.
    pause
    exit /b 1
)
echo [OK] Python encontrado.

:: ── Instalar dependencias ────────────────────────────────────
echo.
echo Instalando dependencias Python...
pip install -q -r "%PROJETO%\requirements.txt"
pip install -q watchdog
echo [OK] Dependencias instaladas.

:: ── Configurar credenciais do Drive ─────────────────────────
echo.
echo Abrindo configuracao do Google Drive...
echo (Sera pedido o caminho da sua pasta de orcamentos
echo  e depois vai abrir o navegador para fazer login)
echo.
python "%PROJETO%\configurar_credenciais.py"
if errorlevel 1 (
    echo.
    echo [ERRO] Configuracao nao concluida. Tente novamente.
    pause
    exit /b 1
)

:: ── Criar arquivo de inicializacao no Windows ───────────────
echo.
echo Configurando inicio automatico com o Windows...

set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set ATALHO=%STARTUP%\AgenteDriveOrcamentos.bat

:: Escreve o bat de startup com o caminho do projeto fixo
(
    echo @echo off
    echo cd /d "%PROJETO%"
    echo start "" /B pythonw.exe "%PROJETO%\watcher.py"
    echo if errorlevel 1 start "" /MIN python.exe "%PROJETO%\watcher.py"
) > "%ATALHO%"

if exist "%ATALHO%" (
    echo [OK] Agente configurado para iniciar com o Windows.
) else (
    echo [AVISO] Nao foi possivel criar o inicio automatico.
    echo         O agente ainda pode ser iniciado manualmente
    echo         clicando duas vezes em 'iniciar_agente.bat'
)

:: ── Iniciar o agente agora ───────────────────────────────────
echo.
echo Iniciando o agente agora...
start "" /B pythonw.exe "%PROJETO%\watcher.py"
if errorlevel 1 (
    start "" /MIN python.exe "%PROJETO%\watcher.py"
)

echo.
echo ============================================================
echo   Pronto! O agente esta rodando em segundo plano.
echo.
echo   A partir de agora, qualquer PDF salvo em:
echo   %PROJETO%\{Cidade}\{Cliente}\arquivo.pdf
echo.
echo   sera enviado automaticamente para o Google Drive.
echo ============================================================
echo.
pause
endlocal
