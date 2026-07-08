@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title Egemap - Instalando agente de orcamentos...

:: ── Pasta onde tudo fica instalado ──────────────────────────────────────────
set DESTINO=C:\EgemapDrive
if not exist "!DESTINO!" mkdir "!DESTINO!"
cd /d "!DESTINO!"

echo.
echo  =============================================
echo    Agente de Orcamentos - Egemap
echo  =============================================
echo.

:: ── 1. Baixar rclone ────────────────────────────────────────────────────────
echo  [1/4] Baixando programa de conexao com o Drive...
if exist "!DESTINO!\rclone.exe" (
    echo         Ja instalado, pulando.
) else (
    powershell -NoProfile -Command ^
        "$p='SilentlyContinue';$ProgressPreference=$p;$ErrorActionPreference='Stop';" ^
        "try{" ^
        "  Invoke-WebRequest 'https://downloads.rclone.org/rclone-current-windows-amd64.zip' -OutFile '!DESTINO!\rc.zip';" ^
        "  Add-Type -A System.IO.Compression.FileSystem;" ^
        "  $z=[System.IO.Compression.ZipFile]::OpenRead('!DESTINO!\rc.zip');" ^
        "  $e=$z.Entries|?{$_.Name -eq 'rclone.exe'}|select -f 1;" ^
        "  [System.IO.Compression.ZipFileExtensions]::ExtractToFile($e,'!DESTINO!\rclone.exe',$true);" ^
        "  $z.Dispose(); Remove-Item '!DESTINO!\rc.zip'" ^
        "}catch{Write-Host 'ERRO:'$_.Exception.Message}"
    if not exist "!DESTINO!\rclone.exe" (
        echo.
        echo  [ERRO] Nao foi possivel baixar. Verifique a internet e tente de novo.
        pause & exit /b 1
    )
    echo         OK.
)

:: ── 2. Escrever o agente watcher.ps1 ────────────────────────────────────────
echo.
echo  [2/4] Instalando agente...
powershell -NoProfile -Command ^
    "[IO.File]::WriteAllBytes('!DESTINO!\watcher.ps1'," ^
    "[Convert]::FromBase64String('cGFyYW0oW3N0cmluZ10kQ29uZmlnID0gIiRQU1NjcmlwdFJvb3RcY29uZmlnLmpzb24iKQoKJGNmZyAgICAgPSBHZXQtQ29udGVudCAkQ29uZmlnIC1SYXcgfCBDb252ZXJ0RnJvbS1Kc29uCiRwYXN0YSAgID0gJGNmZy5wYXN0YV9vcmNhbWVudG9zCiRyY2xvbmUgID0gIiRQU1NjcmlwdFJvb3RccmNsb25lLmV4ZSIKJGNvbmYgICAgPSAiJFBTU2NyaXB0Um9vdFxyY2xvbmUuY29uZiIKJGxvZyAgICAgPSAiJFBTU2NyaXB0Um9vdFx3YXRjaGVyLmxvZyIKJHZpc3RvcyAgPSAiJFBTU2NyaXB0Um9vdFxlbnZpYWRvcy5qc29uIgokYW5vICAgICA9IChHZXQtRGF0ZSkuWWVhci5Ub1N0cmluZygpCgpmdW5jdGlvbiBMb2coJG0pIHsKICAgICRsID0gIiQoR2V0LURhdGUgLWYgJ3l5eXktTU0tZGQgSEg6bW0nKSAgJG0iCiAgICBBZGQtQ29udGVudCAkbG9nICRsCiAgICBXcml0ZS1Ib3N0ICRsCn0KCmZ1bmN0aW9uIEVudmlhZG9zIHsKICAgIGlmIChUZXN0LVBhdGggJHZpc3RvcykgewogICAgICAgIHRyeSB7IHJldHVybiAoR2V0LUNvbnRlbnQgJHZpc3RvcyAtUmF3IHwgQ29udmVydEZyb20tSnNvbiAtQXNIYXNodGFibGUpIH0gY2F0Y2gge30KICAgIH0KICAgIHJldHVybiBAe30KfQoKZnVuY3Rpb24gU2FsdmFyKCRoKSB7ICRoIHwgQ29udmVydFRvLUpzb24gfCBTZXQtQ29udGVudCAkdmlzdG9zIC1FbmNvZGluZyBVVEY4IH0KCmlmICgtbm90IChUZXN0LVBhdGggJHBhc3RhKSkgIHsgTG9nICJFUlJPOiBwYXN0YSBuYW8gZW5jb250cmFkYTogJHBhc3RhIjsgUmVhZC1Ib3N0OyBleGl0IDEgfQppZiAoLW5vdCAoVGVzdC1QYXRoICRyY2xvbmUpKSB7IExvZyAiRVJSTzogcmNsb25lLmV4ZSBuYW8gZW5jb250cmFkby4gUm9kZSBJTlNUQUxBUi5iYXQiOyBSZWFkLUhvc3Q7IGV4aXQgMSB9CgpMb2cgIj09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0iCkxvZyAiICBBZ2VudGUgRWdlbWFwIC0gRHJpdmUgcm9kYW5kbyIKTG9nICI9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09IgpMb2cgIlBhc3RhOiAkcGFzdGEiCkxvZyAiIgoKJG9rID0gRW52aWFkb3MKCndoaWxlICgkdHJ1ZSkgewogICAgJGFub0F0dWFsID0gKEdldC1EYXRlKS5ZZWFyLlRvU3RyaW5nKCkKICAgIGlmICgkYW5vIC1uZSAkYW5vQXR1YWwpIHsgJGFubyA9ICRhbm9BdHVhbDsgTG9nICJBbm86ICRhbm8iIH0KCiAgICBHZXQtQ2hpbGRJdGVtIC1QYXRoICRwYXN0YSAtRmlsdGVyICIqLnBkZiIgLVJlY3Vyc2UgLUVycm9yQWN0aW9uIFNpbGVudGx5Q29udGludWUgfCBGb3JFYWNoLU9iamVjdCB7CiAgICAgICAgJGFycSA9ICRfLkZ1bGxOYW1lCiAgICAgICAgaWYgKCRvay5Db250YWluc0tleSgkYXJxKSkgeyByZXR1cm4gfQoKICAgICAgICAkcmVsICAgPSAkYXJxLlN1YnN0cmluZygkcGFzdGEuVHJpbUVuZCgiL1wiKS5MZW5ndGgpLlRyaW1TdGFydCgiXCIsICIvIikKICAgICAgICAkcCAgICAgPSAkcmVsIC1zcGxpdCAiW1xcL10iCiAgICAgICAgaWYgKCRwLkNvdW50IC1sdCAzKSB7ICRva1skYXJxXSA9ICJpZ25vcmFkbyI7IFNhbHZhciAkb2s7IHJldHVybiB9CgogICAgICAgICRjaWRhZGUgID0gJHBbMF0KICAgICAgICAkY2xpZW50ZSA9ICRwWzFdCiAgICAgICAgJG5vbWUgICAgPSAkcFstMV0KCiAgICAgICAgU3RhcnQtU2xlZXAgMgogICAgICAgIGlmICgtbm90IChUZXN0LVBhdGggJGFycSkpIHsgcmV0dXJuIH0KCiAgICAgICAgTG9nICJOb3ZvOiAkbm9tZSIKICAgICAgICBMb2cgIiAgJGNpZGFkZSAvICRjbGllbnRlIgoKICAgICAgICAkciA9ICYgJHJjbG9uZSBjb3B5ICRhcnEgImVnZW1hcDokYW5vLyRjaWRhZGUvJGNsaWVudGUiIC0tY29uZmlnICRjb25mIDI+JjEKICAgICAgICBpZiAoJExBU1RFWElUQ09ERSAtZXEgMCkgewogICAgICAgICAgICBMb2cgIiAgW09LXSBFbnZpYWRvIgogICAgICAgICAgICAkb2tbJGFycV0gPSAib2siCiAgICAgICAgICAgIFNhbHZhciAkb2sKICAgICAgICB9IGVsc2UgewogICAgICAgICAgICBMb2cgIiAgW0VSUk9dIFZhaSB0ZW50YXIgZGUgbm92byIKICAgICAgICB9CiAgICAgICAgTG9nICIiCiAgICB9CiAgICBTdGFydC1TbGVlcCAxMAp9Cg=='))"
echo         OK.

:: ── 3. Configurar acesso ao Drive ───────────────────────────────────────────
echo.
echo  [3/4] Conectando ao Google Drive...
echo.

:: Escrever config do rclone (pasta raiz = Pedidos e Contratos)
(
    echo [egemap]
    echo type = drive
    echo scope = drive
    echo root_folder_id = 1qtOmTr3KXqSFBwPJyidVcMvEvg7w86L3
) > "!DESTINO!\rclone.conf"

:: Perguntar pasta de orcamentos
echo  Qual e o caminho da sua pasta de orcamentos no computador?
echo  (a que tem as subpastas por cidade e cliente)
echo.
echo  Exemplo:  C:\Users\Egemap\Documents\Orcamentos
echo.
set /p PASTA="  Caminho: "
set PASTA=!PASTA:"=!
set PASTA=!PASTA: =!

if "!PASTA!"=="" (
    echo  [ERRO] Caminho nao informado.
    pause & exit /b 1
)

if not exist "!PASTA!" (
    echo.
    echo  Pasta nao existe. Criando...
    mkdir "!PASTA!" 2>nul
)

:: Salvar config.json
set PJ=!PASTA:\=/!
(
    echo {
    echo   "pasta_orcamentos": "!PJ!",
    echo   "extensoes": [".pdf"],
    echo   "ano": "2026"
    echo }
) > "!DESTINO!\config.json"

echo.
echo  Agora vai abrir o NAVEGADOR para voce fazer login no Google.
echo  So precisa fazer isso UMA VEZ.
echo  Clique em PERMITIR quando aparecer.
echo.
pause

"!DESTINO!\rclone.exe" config reconnect egemap: --config "!DESTINO!\rclone.conf"

if errorlevel 1 (
    echo.
    echo  [ERRO] Login nao concluido. Tente novamente.
    pause & exit /b 1
)
echo.
echo  Conectado ao Drive!

:: ── 4. Criar tarefa que inicia com o Windows ────────────────────────────────
echo.
echo  [4/4] Configurando inicio automatico com o Windows...

schtasks /delete /tn "EgemapDriveWatcher" /f >nul 2>&1
schtasks /create ^
    /tn "EgemapDriveWatcher" ^
    /tr "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File \"!DESTINO!\watcher.ps1\"" ^
    /sc ONLOGON ^
    /ru "%USERNAME%" ^
    /rl HIGHEST ^
    /f >nul 2>&1

if errorlevel 1 (
    echo  [AVISO] Nao foi possivel criar tarefa automatica.
    echo          Use o atalho INICIAR_AGENTE.bat para iniciar manualmente.
) else (
    echo  Agente vai iniciar sozinho toda vez que ligar o computador.
)

:: ── Criar atalho INICIAR_AGENTE.bat na area de trabalho ─────────────────────
(
    echo @echo off
    echo powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "!DESTINO!\watcher.ps1"
) > "%USERPROFILE%\Desktop\INICIAR_AGENTE.bat"

:: ── Iniciar o agente agora ───────────────────────────────────────────────────
echo.
echo  Iniciando o agente...
powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "!DESTINO!\watcher.ps1"

echo.
echo  =============================================
echo.
echo   PRONTO! O agente esta rodando.
echo.
echo   Salve PDFs assim:
echo   Orcamentos\Cidade\Cliente\arquivo.pdf
echo.
echo   O Drive e atualizado automaticamente.
echo   Log em: !DESTINO!\watcher.log
echo.
echo  =============================================
echo.
pause
endlocal
