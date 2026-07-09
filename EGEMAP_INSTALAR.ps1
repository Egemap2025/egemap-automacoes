$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'
$Destino = "$env:USERPROFILE\EgemapDrive"

function Passo($n, $txt) { Write-Host ""; Write-Host "  [$n/4] $txt" -ForegroundColor Cyan }
function Ok   { Write-Host "        OK." -ForegroundColor Green }
function Erro ($msg) { Write-Host "  [ERRO] $msg" -ForegroundColor Red; Read-Host "Enter para fechar"; exit 1 }

Write-Host ""
Write-Host "  =============================================" -ForegroundColor Yellow
Write-Host "    Agente de Orcamentos - Egemap" -ForegroundColor Yellow
Write-Host "  =============================================" -ForegroundColor Yellow
Write-Host ""

New-Item -ItemType Directory -Force -Path $Destino | Out-Null

# 1. Baixar rclone
Passo 1 "Baixando programa de conexao com o Drive..."
if (Test-Path "$Destino\rclone.exe") {
    Write-Host "        Ja instalado, pulando."
} else {
    try {
        Invoke-WebRequest "https://downloads.rclone.org/rclone-current-windows-amd64.zip" -OutFile "$Destino\rc.zip"
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $z = [System.IO.Compression.ZipFile]::OpenRead("$Destino\rc.zip")
        $e = $z.Entries | Where-Object { $_.Name -eq "rclone.exe" } | Select-Object -First 1
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($e, "$Destino\rclone.exe", $true)
        $z.Dispose()
        Remove-Item "$Destino\rc.zip"
        Ok
    } catch {
        Erro "Nao foi possivel baixar o rclone. Verifique a internet. Detalhe: $_"
    }
}

# 2. Escrever watcher.ps1
Passo 2 "Instalando agente..."
$b64 = "cGFyYW0oW3N0cmluZ10kQ29uZmlnID0gIiRQU1NjcmlwdFJvb3RcY29uZmlnLmpzb24iKQoKJGNmZyAgICA9IEdldC1Db250ZW50ICRDb25maWcgLVJhdyB8IENvbnZlcnRGcm9tLUpzb24KJHBhc3RhICA9ICRjZmcucGFzdGFfb3JjYW1lbnRvcy5UcmltRW5kKCIvXCIpCiRyY2xvbmUgPSAiJFBTU2NyaXB0Um9vdFxyY2xvbmUuZXhlIgokY29uZiAgID0gIiRQU1NjcmlwdFJvb3RccmNsb25lLmNvbmYiCiRsb2cgICAgPSAiJFBTU2NyaXB0Um9vdFx3YXRjaGVyLmxvZyIKJHZpc3RvcyA9ICIkUFNTY3JpcHRSb290XGVudmlhZG9zLmpzb24iCgpmdW5jdGlvbiBMb2coJG0pIHsKICAgICRsID0gIiQoR2V0LURhdGUgLWYgJ3l5eXktTU0tZGQgSEg6bW0nKSAgJG0iCiAgICBBZGQtQ29udGVudCAkbG9nICRsIC1FbmNvZGluZyBVVEY4CiAgICBXcml0ZS1Ib3N0ICRsCn0KCmZ1bmN0aW9uIEVudmlhZG9zIHsKICAgIGlmIChUZXN0LVBhdGggJHZpc3RvcykgewogICAgICAgIHRyeSB7IHJldHVybiAoR2V0LUNvbnRlbnQgJHZpc3RvcyAtUmF3IHwgQ29udmVydEZyb20tSnNvbiAtQXNIYXNodGFibGUpIH0gY2F0Y2gge30KICAgIH0KICAgIHJldHVybiBAe30KfQoKZnVuY3Rpb24gU2FsdmFyKCRoKSB7ICRoIHwgQ29udmVydFRvLUpzb24gfCBTZXQtQ29udGVudCAkdmlzdG9zIC1FbmNvZGluZyBVVEY4IH0KCmlmICgtbm90IChUZXN0LVBhdGggJHBhc3RhKSkgIHsgTG9nICJFUlJPOiBwYXN0YSBuYW8gZW5jb250cmFkYTogJHBhc3RhIjsgUmVhZC1Ib3N0ICJFbnRlciBwYXJhIGZlY2hhciI7IGV4aXQgMSB9CmlmICgtbm90IChUZXN0LVBhdGggJHJjbG9uZSkpIHsgTG9nICJFUlJPOiByY2xvbmUuZXhlIGF1c2VudGUuIFJvZGUgRUdFTUFQX0lOU1RBTEFSLmJhdCI7IFJlYWQtSG9zdCAiRW50ZXIgcGFyYSBmZWNoYXIiOyBleGl0IDEgfQoKTG9nICI9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09IgpMb2cgIiAgQWdlbnRlIEVnZW1hcCAtIERyaXZlIgpMb2cgIj09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0iCkxvZyAiTW9uaXRvcmFuZG86ICRwYXN0YSIKTG9nICJFc3RydXR1cmE6ICAgT3JjYW1lbnRvcyAvIDIwMjYgLyBDaWRhZGUgLyBDbGllbnRlIC8gUERGIgpMb2cgIiIKCiRvayA9IEVudmlhZG9zCgp3aGlsZSAoJHRydWUpIHsKICAgIEdldC1DaGlsZEl0ZW0gLVBhdGggJHBhc3RhIC1GaWx0ZXIgIioucGRmIiAtUmVjdXJzZSAtRXJyb3JBY3Rpb24gU2lsZW50bHlDb250aW51ZSB8IEZvckVhY2gtT2JqZWN0IHsKICAgICAgICAkYXJxID0gJF8uRnVsbE5hbWUKICAgICAgICBpZiAoJG9rLkNvbnRhaW5zS2V5KCRhcnEpKSB7IHJldHVybiB9CgogICAgICAgICMgRXN0cnV0dXJhIGVzcGVyYWRhOgogICAgICAgICMgIHtwYXN0YX0gLyB7QW5vfSAvIHtDaWRhZGV9IC8ge0NsaWVudGV9IC8gYXJxdWl2by5wZGYKICAgICAgICAjICBwYXJ0ZXM6ICAgIFswXSAgICAgIFsxXSAgICAgICAgWzJdICAgICAgICAgWzM9bm9tZV0KICAgICAgICAkcmVsICAgPSAkYXJxLlN1YnN0cmluZygkcGFzdGEuTGVuZ3RoKS5UcmltU3RhcnQoIlwiLCAiLyIpCiAgICAgICAgJHAgICAgID0gJHJlbCAtc3BsaXQgIltcXC9dIgoKICAgICAgICBpZiAoJHAuQ291bnQgLWx0IDQpIHsKICAgICAgICAgICAgIyBBcnF1aXZvIGZvcmEgZGEgZXN0cnV0dXJhIGNvcnJldGEg4oCUIGlnbm9yYSBzZW0gbG9nYXIKICAgICAgICAgICAgJG9rWyRhcnFdID0gImlnbm9yYWRvIgogICAgICAgICAgICBTYWx2YXIgJG9rCiAgICAgICAgICAgIHJldHVybgogICAgICAgIH0KCiAgICAgICAgJGFubyAgICAgPSAkcFswXQogICAgICAgICRjaWRhZGUgID0gJHBbMV0KICAgICAgICAkY2xpZW50ZSA9ICRwWzJdCiAgICAgICAgJG5vbWUgICAgPSAkcFstMV0KCiAgICAgICAgIyBBZ3VhcmRhIG8gYXJxdWl2byB0ZXJtaW5hciBkZSBzZXIgZ3JhdmFkbwogICAgICAgIFN0YXJ0LVNsZWVwIDMKICAgICAgICBpZiAoLW5vdCAoVGVzdC1QYXRoICRhcnEpKSB7IHJldHVybiB9CgogICAgICAgIExvZyAiQXJxdWl2byBub3ZvOiAkbm9tZSIKICAgICAgICBMb2cgIiAgQW5vOiAgICAgJGFubyIKICAgICAgICBMb2cgIiAgQ2lkYWRlOiAgJGNpZGFkZSIKICAgICAgICBMb2cgIiAgQ2xpZW50ZTogJGNsaWVudGUiCgogICAgICAgICRkZXN0aW5vID0gIiRhbm8vJGNpZGFkZS8kY2xpZW50ZSIKCiAgICAgICAgJHIgPSAmICRyY2xvbmUgY29weSAkYXJxICJlZ2VtYXA6JGRlc3Rpbm8iIC0tY29uZmlnICRjb25mIDI+JjEKICAgICAgICBpZiAoJExBU1RFWElUQ09ERSAtZXEgMCkgewogICAgICAgICAgICBMb2cgIiAgW09LXSBFbnZpYWRvIHBhcmEgbyBEcml2ZSIKICAgICAgICAgICAgJG9rWyRhcnFdID0gIm9rIgogICAgICAgICAgICBTYWx2YXIgJG9rCiAgICAgICAgfSBlbHNlIHsKICAgICAgICAgICAgTG9nICIgIFtFUlJPXSBGYWxoYSAtIHZhaSB0ZW50YXIgZGUgbm92byBlbSAxMHMiCiAgICAgICAgICAgIExvZyAiICBEZXRhbGhlOiAkciIKICAgICAgICB9CiAgICAgICAgTG9nICIiCiAgICB9CiAgICBTdGFydC1TbGVlcCAxMAp9Cg=="
[IO.File]::WriteAllBytes("$Destino\watcher.ps1", [Convert]::FromBase64String($b64))
Ok

# 3. Configurar acesso ao Drive
Passo 3 "Conectando ao Google Drive..."

@"
[egemap]
type = drive
scope = drive
root_folder_id = 1P0EpUNY7F6-j2FX0MmJ0hQZxIQq9nvN5
"@ | Set-Content "$Destino\rclone.conf" -Encoding ASCII

Write-Host ""
Write-Host "  Qual e o caminho da sua pasta de orcamentos no computador?" -ForegroundColor White
Write-Host "  (a que tem as subpastas de cidade e cliente)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Exemplo: C:\Users\T-GAMER\OneDrive\Desktop\ORCAMENTOS" -ForegroundColor Gray
Write-Host ""
$Pasta = (Read-Host "  Caminho").Trim('"').Trim()

if (-not $Pasta) { Erro "Caminho nao informado." }
if (-not (Test-Path $Pasta)) {
    Write-Host "  Pasta nao existe. Criando..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $Pasta | Out-Null
}

$PastaJson = $Pasta -replace '\\', '/'
@"
{
  "pasta_orcamentos": "$PastaJson",
  "extensoes": [".pdf"],
  "ano": "2026"
}
"@ | Set-Content "$Destino\config.json" -Encoding UTF8

Write-Host ""
Write-Host "  Agora vai abrir o NAVEGADOR para fazer login no Google." -ForegroundColor White
Write-Host "  So precisa fazer isso UMA VEZ." -ForegroundColor Gray
Write-Host "  Clique em PERMITIR quando aparecer." -ForegroundColor Gray
Write-Host ""
Read-Host "  Pressione Enter para abrir o navegador"

& "$Destino\rclone.exe" config reconnect egemap: --config "$Destino\rclone.conf"
if ($LASTEXITCODE -ne 0) { Erro "Login nao concluido. Tente novamente." }
Write-Host "  Conectado ao Drive!" -ForegroundColor Green

# 4. Agendador de tarefas
Passo 4 "Configurando inicio automatico com o Windows..."

try {
    $action  = New-ScheduledTaskAction -Execute "powershell.exe" `
                 -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Destino\watcher.ps1`""
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0
    Register-ScheduledTask -TaskName "EgemapDriveWatcher" -Action $action -Trigger $trigger `
        -Settings $settings -RunLevel Highest -Force | Out-Null
    Write-Host "  Agente vai iniciar sozinho toda vez que ligar o computador." -ForegroundColor Green
} catch {
    Write-Host "  [AVISO] Nao foi possivel criar tarefa automatica. Use INICIAR_AGENTE.bat." -ForegroundColor Yellow
}

# Atalho na area de trabalho
"@echo off`npowershell -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Destino\watcher.ps1`"" |
    Set-Content "$env:USERPROFILE\Desktop\INICIAR_AGENTE.bat" -Encoding ASCII

# Iniciar agora
Write-Host ""
Write-Host "  Iniciando o agente..." -ForegroundColor White
Start-Process powershell -ArgumentList "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Destino\watcher.ps1`""

Write-Host ""
Write-Host "  =============================================" -ForegroundColor Green
Write-Host "    PRONTO! O agente esta rodando." -ForegroundColor Green
Write-Host ""
Write-Host "    Salve PDFs assim:" -ForegroundColor White
Write-Host "    ORCAMENTOS\Ano\Estado\Cidade\Cliente\arq.pdf" -ForegroundColor Gray
Write-Host ""
Write-Host "    O Drive e atualizado automaticamente." -ForegroundColor White
Write-Host "    Log em: $Destino\watcher.log" -ForegroundColor Gray
Write-Host "  =============================================" -ForegroundColor Green
Write-Host ""
Read-Host "  Pressione Enter para fechar"
