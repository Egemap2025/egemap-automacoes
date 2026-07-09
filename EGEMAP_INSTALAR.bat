@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title Egemap - Instalando agente de orcamentos...

:: ── Pasta onde tudo fica instalado ──────────────────────────────────────────
set DESTINO=%USERPROFILE%\EgemapDrive
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
    "[Convert]::FromBase64String('cGFyYW0oW3N0cmluZ10kQ29uZmlnID0gIiRQU1NjcmlwdFJvb3RcY29uZmlnLmpzb24iKQoKJGNmZyAgICA9IEdldC1Db250ZW50ICRDb25maWcgLVJhdyB8IENvbnZlcnRGcm9tLUpzb24KJHBhc3RhICA9ICRjZmcucGFzdGFfb3JjYW1lbnRvcy5UcmltRW5kKCIvXCIpCiRyY2xvbmUgPSAiJFBTU2NyaXB0Um9vdFxyY2xvbmUuZXhlIgokY29uZiAgID0gIiRQU1NjcmlwdFJvb3RccmNsb25lLmNvbmYiCiRsb2cgICAgPSAiJFBTU2NyaXB0Um9vdFx3YXRjaGVyLmxvZyIKJHZpc3RvcyA9ICIkUFNTY3JpcHRSb290XGVudmlhZG9zLmpzb24iCgpmdW5jdGlvbiBMb2coJG0pIHsKICAgICRsID0gIiQoR2V0LURhdGUgLWYgJ3l5eXktTU0tZGQgSEg6bW0nKSAgJG0iCiAgICBBZGQtQ29udGVudCAkbG9nICRsIC1FbmNvZGluZyBVVEY4CiAgICBXcml0ZS1Ib3N0ICRsCn0KCmZ1bmN0aW9uIEVudmlhZG9zIHsKICAgIGlmIChUZXN0LVBhdGggJHZpc3RvcykgewogICAgICAgIHRyeSB7IHJldHVybiAoR2V0LUNvbnRlbnQgJHZpc3RvcyAtUmF3IHwgQ29udmVydEZyb20tSnNvbiAtQXNIYXNodGFibGUpIH0gY2F0Y2gge30KICAgIH0KICAgIHJldHVybiBAe30KfQoKZnVuY3Rpb24gU2FsdmFyKCRoKSB7ICRoIHwgQ29udmVydFRvLUpzb24gfCBTZXQtQ29udGVudCAkdmlzdG9zIC1FbmNvZGluZyBVVEY4IH0KCmlmICgtbm90IChUZXN0LVBhdGggJHBhc3RhKSkgIHsgTG9nICJFUlJPOiBwYXN0YSBuYW8gZW5jb250cmFkYTogJHBhc3RhIjsgUmVhZC1Ib3N0ICJFbnRlciBwYXJhIGZlY2hhciI7IGV4aXQgMSB9CmlmICgtbm90IChUZXN0LVBhdGggJHJjbG9uZSkpIHsgTG9nICJFUlJPOiByY2xvbmUuZXhlIGF1c2VudGUuIFJvZGUgRUdFTUFQX0lOU1RBTEFSLmJhdCI7IFJlYWQtSG9zdCAiRW50ZXIgcGFyYSBmZWNoYXIiOyBleGl0IDEgfQoKTG9nICI9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09IgpMb2cgIiAgQWdlbnRlIEVnZW1hcCAtIERyaXZlIgpMb2cgIj09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0iCkxvZyAiTW9uaXRvcmFuZG86ICRwYXN0YSIKTG9nICJFc3RydXR1cmE6ICAgT3JjYW1lbnRvcyAvIEFubyAvIEVzdGFkbyAvIENpZGFkZSAvIENsaWVudGUgLyBQREYiCkxvZyAiIgoKJG9rID0gRW52aWFkb3MKCndoaWxlICgkdHJ1ZSkgewogICAgR2V0LUNoaWxkSXRlbSAtUGF0aCAkcGFzdGEgLUZpbHRlciAiKi5wZGYiIC1SZWN1cnNlIC1FcnJvckFjdGlvbiBTaWxlbnRseUNvbnRpbnVlIHwgRm9yRWFjaC1PYmplY3QgewogICAgICAgICRhcnEgPSAkXy5GdWxsTmFtZQogICAgICAgIGlmICgkb2suQ29udGFpbnNLZXkoJGFycSkpIHsgcmV0dXJuIH0KCiAgICAgICAgIyBFc3RydXR1cmEgZXNwZXJhZGE6CiAgICAgICAgIyAge3Bhc3RhfSAvIHtBbm99IC8ge0VzdGFkb30gLyB7Q2lkYWRlfSAvIHtDbGllbnRlfSAvIGFycXVpdm8ucGRmCiAgICAgICAgIyAgcGFydGVzOiAgICBbMF0gICAgICBbMV0gICAgICAgIFsyXSAgICAgICAgWzNdICAgICAgICAgWzQ9bm9tZV0KICAgICAgICAkcmVsICAgPSAkYXJxLlN1YnN0cmluZygkcGFzdGEuTGVuZ3RoKS5UcmltU3RhcnQoIlwiLCAiLyIpCiAgICAgICAgJHAgICAgID0gJHJlbCAtc3BsaXQgIltcXC9dIgoKICAgICAgICBpZiAoJHAuQ291bnQgLWx0IDUpIHsKICAgICAgICAgICAgIyBBcnF1aXZvIGZvcmEgZGEgZXN0cnV0dXJhIGNvcnJldGEg4oCUIGlnbm9yYSBzZW0gbG9nYXIKICAgICAgICAgICAgJG9rWyRhcnFdID0gImlnbm9yYWRvIgogICAgICAgICAgICBTYWx2YXIgJG9rCiAgICAgICAgICAgIHJldHVybgogICAgICAgIH0KCiAgICAgICAgJGFubyAgICAgPSAkcFswXQogICAgICAgICMgJGVzdGFkbyA9ICRwWzFdICAjIGV4aXN0ZSBubyBjb21wdXRhZG9yIG1hcyBuYW8gdmFpIHBybyBEcml2ZQogICAgICAgICRjaWRhZGUgID0gJHBbMl0KICAgICAgICAkY2xpZW50ZSA9ICRwWzNdCiAgICAgICAgJG5vbWUgICAgPSAkcFstMV0KCiAgICAgICAgIyBBZ3VhcmRhIG8gYXJxdWl2byB0ZXJtaW5hciBkZSBzZXIgZ3JhdmFkbwogICAgICAgIFN0YXJ0LVNsZWVwIDMKICAgICAgICBpZiAoLW5vdCAoVGVzdC1QYXRoICRhcnEpKSB7IHJldHVybiB9CgogICAgICAgIExvZyAiQXJxdWl2byBub3ZvOiAkbm9tZSIKICAgICAgICBMb2cgIiAgQW5vOiAgICAgJGFubyIKICAgICAgICBMb2cgIiAgQ2lkYWRlOiAgJGNpZGFkZSIKICAgICAgICBMb2cgIiAgQ2xpZW50ZTogJGNsaWVudGUiCgogICAgICAgICMgRGVzdGlubyBubyBEcml2ZTogUGVkaWRvcyBlIENvbnRyYXRvcyAvIEFubyAvIENpZGFkZSAvIENsaWVudGUgLwogICAgICAgICRkZXN0aW5vID0gIiRhbm8vJGNpZGFkZS8kY2xpZW50ZSIKCiAgICAgICAgJHIgPSAmICRyY2xvbmUgY29weSAkYXJxICJlZ2VtYXA6JGRlc3Rpbm8iIC0tY29uZmlnICRjb25mIDI+JjEKICAgICAgICBpZiAoJExBU1RFWElUQ09ERSAtZXEgMCkgewogICAgICAgICAgICBMb2cgIiAgW09LXSBFbnZpYWRvIHBhcmEgbyBEcml2ZSIKICAgICAgICAgICAgJG9rWyRhcnFdID0gIm9rIgogICAgICAgICAgICBTYWx2YXIgJG9rCiAgICAgICAgfSBlbHNlIHsKICAgICAgICAgICAgTG9nICIgIFtFUlJPXSBGYWxoYSAtIHZhaSB0ZW50YXIgZGUgbm92byBlbSAxMHMiCiAgICAgICAgICAgIExvZyAiICBEZXRhbGhlOiAkciIKICAgICAgICB9CiAgICAgICAgTG9nICIiCiAgICB9CiAgICBTdGFydC1TbGVlcCAxMAp9Cg=='))"
echo         OK.

:: ── 3. Configurar acesso ao Drive ───────────────────────────────────────────
echo.
echo  [3/4] Conectando ao Google Drive...
echo.

:: Escrever config do rclone (pasta raiz = Orcamentos)
(
    echo [egemap]
    echo type = drive
    echo scope = drive
    echo root_folder_id = 1P0EpUNY7F6-j2FX0MmJ0hQZxIQq9nvN5
) > "!DESTINO!\rclone.conf"

:: Perguntar pasta de orcamentos
echo  Qual e o caminho da sua pasta de orcamentos no computador?
echo  (a que tem as subpastas por cidade e cliente)
echo.
echo  Exemplo:  C:\Users\Egemap\Documents\Orcamentos
echo.
set /p PASTA="  Caminho: "
set PASTA=!PASTA:"=!

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
