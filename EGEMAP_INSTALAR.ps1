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
$b64 = "cGFyYW0oW3N0cmluZ10kQ29uZmlnID0gIiRQU1NjcmlwdFJvb3RcY29uZmlnLmpzb24iKQoKJGNmZyAgICA9IEdldC1Db250ZW50ICRDb25maWcgLVJhdyB8IENvbnZlcnRGcm9tLUpzb24KJHBhc3RhICA9ICRjZmcucGFzdGFfb3JjYW1lbnRvcy5UcmltRW5kKCIvXCIpCiRyY2xvbmUgPSAiJFBTU2NyaXB0Um9vdFxyY2xvbmUuZXhlIgokY29uZiAgID0gIiRQU1NjcmlwdFJvb3RccmNsb25lLmNvbmYiCiRsb2cgICAgPSAiJFBTU2NyaXB0Um9vdFx3YXRjaGVyLmxvZyIKJHZpc3RvcyA9ICIkUFNTY3JpcHRSb290XGVudmlhZG9zLmpzb24iCgpmdW5jdGlvbiBMb2coJG0pIHsKICAgICRsID0gIiQoR2V0LURhdGUgLWYgJ3l5eXktTU0tZGQgSEg6bW0nKSAgJG0iCiAgICBBZGQtQ29udGVudCAkbG9nICRsIC1FbmNvZGluZyBVVEY4CiAgICBXcml0ZS1Ib3N0ICRsCn0KCmZ1bmN0aW9uIEVudmlhZG9zIHsKICAgIGlmIChUZXN0LVBhdGggJHZpc3RvcykgewogICAgICAgIHRyeSB7IHJldHVybiAoR2V0LUNvbnRlbnQgJHZpc3RvcyAtUmF3IHwgQ29udmVydEZyb20tSnNvbiAtQXNIYXNodGFibGUpIH0gY2F0Y2gge30KICAgIH0KICAgIHJldHVybiBAe30KfQoKZnVuY3Rpb24gU2FsdmFyKCRoKSB7ICRoIHwgQ29udmVydFRvLUpzb24gfCBTZXQtQ29udGVudCAkdmlzdG9zIC1FbmNvZGluZyBVVEY4IH0KCmlmICgtbm90IChUZXN0LVBhdGggJHBhc3RhKSkgIHsgTG9nICJFUlJPOiBwYXN0YSBuYW8gZW5jb250cmFkYTogJHBhc3RhIjsgUmVhZC1Ib3N0ICJFbnRlciBwYXJhIGZlY2hhciI7IGV4aXQgMSB9CmlmICgtbm90IChUZXN0LVBhdGggJHJjbG9uZSkpIHsgTG9nICJFUlJPOiByY2xvbmUuZXhlIGF1c2VudGUuIFJvZGUgRUdFTUFQX0lOU1RBTEFSLmJhdCI7IFJlYWQtSG9zdCAiRW50ZXIgcGFyYSBmZWNoYXIiOyBleGl0IDEgfQoKTG9nICI9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09IgpMb2cgIiAgQWdlbnRlIEVnZW1hcCAtIERyaXZlIgpMb2cgIj09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0iCkxvZyAiTW9uaXRvcmFuZG86ICRwYXN0YSIKTG9nICJFc3RydXR1cmE6ICAgT3JjYW1lbnRvcyAvIDIwMjYgLyBDaWRhZGUgLyBDbGllbnRlIC8gUERGIgpMb2cgIiIKCiRvayA9IEVudmlhZG9zCgojIE5hIHByaW1laXJhIGV4ZWN1Y2FvIChvdSBhcG9zIGF0dWFsaXphY2FvKTogbWFyY2EgYXJxdWl2b3MgZXhpc3RlbnRlcyBjb21vIGphIHZpc3RvcyBzZW0gZW52aWFyCmlmICgkb2suQ291bnQgLWVxIDApIHsKICAgIExvZyAiSW5pY2lhbGl6YW5kbzogcmVnaXN0cmFuZG8gYXJxdWl2b3MgZXhpc3RlbnRlcyAobmFvIHNlcmFvIGVudmlhZG9zKS4uLiIKICAgIEdldC1DaGlsZEl0ZW0gLVBhdGggJHBhc3RhIC1GaWx0ZXIgIioucGRmIiAtUmVjdXJzZSAtRXJyb3JBY3Rpb24gU2lsZW50bHlDb250aW51ZSB8IEZvckVhY2gtT2JqZWN0IHsKICAgICAgICAkb2tbJF8uRnVsbE5hbWVdID0gImlnbm9yYWRvIgogICAgfQogICAgU2FsdmFyICRvawogICAgTG9nICJQcm9udG8uIE1vbml0b3JhbmRvIGFwZW5hcyBhcnF1aXZvcyBub3ZvcyBhIHBhcnRpciBkZSBhZ29yYS4iCiAgICBMb2cgIiIKfQoKd2hpbGUgKCR0cnVlKSB7CiAgICBHZXQtQ2hpbGRJdGVtIC1QYXRoICRwYXN0YSAtRmlsdGVyICIqLnBkZiIgLVJlY3Vyc2UgLUVycm9yQWN0aW9uIFNpbGVudGx5Q29udGludWUgfCBGb3JFYWNoLU9iamVjdCB7CiAgICAgICAgJGFycSA9ICRfLkZ1bGxOYW1lCiAgICAgICAgaWYgKCRvay5Db250YWluc0tleSgkYXJxKSkgeyByZXR1cm4gfQoKICAgICAgICAjIEVzdHJ1dHVyYSBlc3BlcmFkYToKICAgICAgICAjICB7cGFzdGF9IC8ge0Fub30gLyB7Q2lkYWRlfSAvIHtDbGllbnRlfSAvIGFycXVpdm8ucGRmCiAgICAgICAgIyAgcGFydGVzOiAgICBbMF0gICAgICBbMV0gICAgICAgIFsyXSAgICAgICAgIFszPW5vbWVdCiAgICAgICAgJHJlbCAgID0gJGFycS5TdWJzdHJpbmcoJHBhc3RhLkxlbmd0aCkuVHJpbVN0YXJ0KCJcIiwgIi8iKQogICAgICAgICRwICAgICA9ICRyZWwgLXNwbGl0ICJbXFwvXSIKCiAgICAgICAgaWYgKCRwLkNvdW50IC1sdCA0KSB7CiAgICAgICAgICAgICMgQXJxdWl2byBmb3JhIGRhIGVzdHJ1dHVyYSBjb3JyZXRhIOKAlCBpZ25vcmEgc2VtIGxvZ2FyCiAgICAgICAgICAgICRva1skYXJxXSA9ICJpZ25vcmFkbyIKICAgICAgICAgICAgU2FsdmFyICRvawogICAgICAgICAgICByZXR1cm4KICAgICAgICB9CgogICAgICAgICRhbm8gICAgID0gJHBbMF0KICAgICAgICAkY2lkYWRlICA9ICRwWzFdCiAgICAgICAgJGNsaWVudGUgPSAkcFsyXQogICAgICAgICRub21lICAgID0gJHBbLTFdCgogICAgICAgICMgU29tZW50ZSBhcnF1aXZvcyBjb20gIlByb3Bvc3RhIENvbWVyY2lhbCIgbm8gbm9tZQogICAgICAgIGlmICgkbm9tZSAtbm90bGlrZSAiKlByb3Bvc3RhIENvbWVyY2lhbCoiKSB7CiAgICAgICAgICAgICRva1skYXJxXSA9ICJpZ25vcmFkbyIKICAgICAgICAgICAgU2FsdmFyICRvawogICAgICAgICAgICByZXR1cm4KICAgICAgICB9CgogICAgICAgICMgQWd1YXJkYSBvIGFycXVpdm8gdGVybWluYXIgZGUgc2VyIGdyYXZhZG8KICAgICAgICBTdGFydC1TbGVlcCAzCiAgICAgICAgaWYgKC1ub3QgKFRlc3QtUGF0aCAkYXJxKSkgeyByZXR1cm4gfQoKICAgICAgICBMb2cgIkFycXVpdm8gbm92bzogJG5vbWUiCiAgICAgICAgTG9nICIgIEFubzogICAgICRhbm8iCiAgICAgICAgTG9nICIgIENpZGFkZTogICRjaWRhZGUiCiAgICAgICAgTG9nICIgIENsaWVudGU6ICRjbGllbnRlIgoKICAgICAgICAkZGVzdGlubyA9ICIkYW5vLyRjaWRhZGUvJGNsaWVudGUiCgogICAgICAgICRyID0gJiAkcmNsb25lIGNvcHkgJGFycSAiZWdlbWFwOiRkZXN0aW5vIiAtLWNvbmZpZyAkY29uZiAyPiYxCiAgICAgICAgaWYgKCRMQVNURVhJVENPREUgLWVxIDApIHsKICAgICAgICAgICAgTG9nICIgIFtPS10gRW52aWFkbyBwYXJhIG8gRHJpdmUiCiAgICAgICAgICAgICRva1skYXJxXSA9ICJvayIKICAgICAgICAgICAgU2FsdmFyICRvawogICAgICAgIH0gZWxzZSB7CiAgICAgICAgICAgIExvZyAiICBbRVJST10gRmFsaGEgLSB2YWkgdGVudGFyIGRlIG5vdm8gZW0gMTBzIgogICAgICAgICAgICBMb2cgIiAgRGV0YWxoZTogJHIiCiAgICAgICAgfQogICAgICAgIExvZyAiIgogICAgfQogICAgU3RhcnQtU2xlZXAgMTAKfQo="
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
