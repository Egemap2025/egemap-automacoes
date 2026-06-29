@echo off
:: Instala o agente para rodar automaticamente quando o Windows ligar.
:: Execute este arquivo UMA VEZ como Administrador.

echo ============================================
echo   Instalando Agente de Orcamentos
echo ============================================
echo.

:: Instalar dependencias Python
echo Instalando dependencias...
pip install -r "%~dp0requirements.txt"
pip install watchdog
echo.

:: Criar atalho na pasta de Inicializacao do Windows
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set ATALHO=%STARTUP%\AgenteDriveOrcamentos.bat

echo Criando atalho em Inicializacao do Windows...
copy /Y "%~dp0iniciar_agente.bat" "%ATALHO%"

if exist "%ATALHO%" (
    echo.
    echo [OK] Instalado com sucesso!
    echo      O agente vai iniciar automaticamente quando o Windows ligar.
    echo.
    echo Iniciando agente agora...
    start "" "%ATALHO%"
    echo [OK] Agente rodando em segundo plano.
) else (
    echo.
    echo [ERRO] Nao foi possivel criar o atalho.
    echo        Tente executar como Administrador.
)

echo.
pause
