@echo off
setlocal EnableDelayedExpansion
set PROJETO=%~dp0
if "!PROJETO:~-1!"=="\" set PROJETO=!PROJETO:~0,-1!

title Instalando Agente de Orcamentos...
chcp 65001 >nul

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║    Instalador do Agente de Orcamentos        ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: ── PASSO 1: Baixar rclone ─────────────────────────────────────────────────
echo [1/4] Verificando rclone...
if exist "!PROJETO!\rclone.exe" (
    echo       Rclone ja instalado.
) else (
    echo       Baixando rclone ^(programa de sincronizacao com o Drive^)...
    powershell -Command "& {
        $url = 'https://downloads.rclone.org/rclone-current-windows-amd64.zip'
        $zip = '%PROJETO%\rclone.zip'
        $dest = '%PROJETO%'
        Write-Host '      Baixando...' -NoNewline
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
        Write-Host ' OK'
        Write-Host '      Extraindo...' -NoNewline
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $z = [System.IO.Compression.ZipFile]::OpenRead($zip)
        $entry = $z.Entries | Where-Object { $_.Name -eq 'rclone.exe' } | Select-Object -First 1
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, (Join-Path $dest 'rclone.exe'), $true)
        $z.Dispose()
        Remove-Item $zip -Force
        Write-Host ' OK'
    }"
    if not exist "!PROJETO!\rclone.exe" (
        echo.
        echo  [ERRO] Nao foi possivel baixar o rclone.
        echo         Verifique sua conexao com a internet e tente novamente.
        pause
        exit /b 1
    )
    echo       Rclone baixado com sucesso.
)

:: ── PASSO 2: Configurar a pasta de orcamentos ──────────────────────────────
echo.
echo [2/4] Configurando pasta de orcamentos...

:: Verificar se ja tem config com pasta valida
set PASTA_OK=0
if exist "!PROJETO!\config.json" (
    for /f "tokens=2 delims=:," %%a in ('findstr "pasta_orcamentos" "!PROJETO!\config.json"') do (
        set PASTA=%%~a
        set PASTA=!PASTA: =!
        set PASTA=!PASTA:"=!
        if not "!PASTA!"=="" if not "!PASTA!"=="CSeuNomeDocumentsOramentos" (
            set PASTA_OK=1
        )
    )
)

if "!PASTA_OK!"=="0" (
    echo.
    echo       Digite o caminho completo da sua pasta de orcamentos.
    echo       Exemplo: C:\Users\Joao\Documents\Orcamentos
    echo.
    set /p PASTA_INPUT="      Caminho: "
    set PASTA_INPUT=!PASTA_INPUT:"=!

    if not exist "!PASTA_INPUT!" (
        echo       Pasta nao existe. Criando...
        mkdir "!PASTA_INPUT!" 2>nul
    )

    :: Converter barras para JSON (usar /)
    set PASTA_JSON=!PASTA_INPUT:\=/!

    (
        echo {
        echo   "pasta_orcamentos": "!PASTA_JSON!",
        echo   "extensoes": [".pdf"],
        echo   "ano": "2026"
        echo }
    ) > "!PROJETO!\config.json"
    echo       Pasta salva: !PASTA_INPUT!
) else (
    echo       Pasta ja configurada.
)

:: ── PASSO 3: Autorizar acesso ao Google Drive ──────────────────────────────
echo.
echo [3/4] Autorizando acesso ao Google Drive...
echo.
echo       O navegador vai abrir para voce fazer login no Google.
echo       So precisa fazer isso UMA VEZ.
echo.

:: Criar config do rclone com a pasta raiz "Pedidos e Contratos"
(
    echo [egemap]
    echo type = drive
    echo scope = drive
    echo root_folder_id = 1qtOmTr3KXqSFBwPJyidVcMvEvg7w86L3
) > "!PROJETO!\rclone.conf"

:: Fazer a autorizacao OAuth (abre o navegador)
"!PROJETO!\rclone.exe" config reconnect egemap: --config "!PROJETO!\rclone.conf"

if errorlevel 1 (
    echo.
    echo  [ERRO] Autorizacao nao concluida. Tente novamente.
    pause
    exit /b 1
)
echo.
echo       Autorizacao concluida!

:: ── PASSO 4: Criar tarefa no Agendador do Windows ──────────────────────────
echo.
echo [4/4] Configurando inicio automatico com o Windows...

schtasks /delete /tn "EgemapDriveWatcher" /f >nul 2>&1
schtasks /create ^
    /tn "EgemapDriveWatcher" ^
    /tr "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File \"!PROJETO!\watcher.ps1\"" ^
    /sc ONLOGON ^
    /ru "%USERNAME%" ^
    /f >nul 2>&1

if errorlevel 1 (
    echo  [AVISO] Nao foi possivel criar tarefa automatica.
    echo          O agente pode ser iniciado manualmente com INICIAR.bat
) else (
    echo       Agente configurado para iniciar com o Windows.
)

:: ── Iniciar o agente agora ─────────────────────────────────────────────────
echo.
echo  Iniciando o agente agora...
powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "!PROJETO!\watcher.ps1"

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   Pronto! O agente esta rodando.             ║
echo  ║                                              ║
echo  ║   Salve PDFs na estrutura:                   ║
echo  ║   Orcamentos / Cidade / Cliente / arq.pdf    ║
echo  ║                                              ║
echo  ║   O arquivo vai para o Drive automaticamente ║
echo  ╚══════════════════════════════════════════════╝
echo.
pause
endlocal
