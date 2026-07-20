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
$b64 = "cGFyYW0oW3N0cmluZ10kQ29uZmlnID0gIiRQU1NjcmlwdFJvb3RcY29uZmlnLmpzb24iKQoKJGNmZyAgICA9IEdldC1Db250ZW50ICRDb25maWcgLVJhdyB8IENvbnZlcnRGcm9tLUpzb24KJHBhc3RhICA9ICRjZmcucGFzdGFfb3JjYW1lbnRvcy5UcmltRW5kKCIvXCIpCiRyY2xvbmUgPSAiJFBTU2NyaXB0Um9vdFxyY2xvbmUuZXhlIgokY29uZiAgID0gIiRQU1NjcmlwdFJvb3RccmNsb25lLmNvbmYiCiRsb2cgICAgPSAiJFBTU2NyaXB0Um9vdFx3YXRjaGVyLmxvZyIKJHZpc3RvcyA9ICIkUFNTY3JpcHRSb290XGVudmlhZG9zLmpzb24iCgpmdW5jdGlvbiBMb2coJG0pIHsKICAgICRsID0gIiQoR2V0LURhdGUgLWYgJ3l5eXktTU0tZGQgSEg6bW0nKSAgJG0iCiAgICBBZGQtQ29udGVudCAkbG9nICRsIC1FbmNvZGluZyBVVEY4CiAgICBXcml0ZS1Ib3N0ICRsCn0KCmZ1bmN0aW9uIEVudmlhZG9zIHsKICAgIGlmIChUZXN0LVBhdGggJHZpc3RvcykgewogICAgICAgIHRyeSB7IHJldHVybiAoR2V0LUNvbnRlbnQgJHZpc3RvcyAtUmF3IHwgQ29udmVydEZyb20tSnNvbiAtQXNIYXNodGFibGUpIH0gY2F0Y2gge30KICAgIH0KICAgIHJldHVybiBAe30KfQoKZnVuY3Rpb24gU2FsdmFyKCRoKSB7ICRoIHwgQ29udmVydFRvLUpzb24gfCBTZXQtQ29udGVudCAkdmlzdG9zIC1FbmNvZGluZyBVVEY4IH0KCmZ1bmN0aW9uIEVudmlhclBhcmFEcml2ZSgkYXJxLCAkbm9tZSwgJGRlc3Rpbm8sICRyZWVudmlvKSB7CiAgICBTdGFydC1TbGVlcCAzCiAgICBpZiAoLW5vdCAoVGVzdC1QYXRoICRhcnEpKSB7IHJldHVybiB9CgogICAgJGhvamUgPSAoR2V0LURhdGUpLlRvU3RyaW5nKCJ5eXl5LU1NLWRkIikKICAgICRub21lU2VtRXh0ID0gW1N5c3RlbS5JTy5QYXRoXTo6R2V0RmlsZU5hbWVXaXRob3V0RXh0ZW5zaW9uKCRub21lKQogICAgJGVoUFZDICAgICAgPSAkbm9tZVNlbUV4dCAtbWF0Y2ggJyg/aSlwdmMkJwogICAgJGVoQUxNICAgICAgPSAkbm9tZVNlbUV4dCAtbWF0Y2ggJyg/aSlhbG0kJwoKICAgICRqc29uRHJpdmUgPSAoJiAkcmNsb25lIGxzanNvbiAiZWdlbWFwOiRkZXN0aW5vIiAtLWNvbmZpZyAkY29uZiAyPiYxKSB8IE91dC1TdHJpbmcKICAgIGlmICgkTEFTVEVYSVRDT0RFIC1lcSAwIC1hbmQgJGpzb25Ecml2ZSAtbWF0Y2ggJ1xbJykgewogICAgICAgIHRyeSB7CiAgICAgICAgICAgICRhcnF1aXZvcyA9ICRqc29uRHJpdmUgfCBDb252ZXJ0RnJvbS1Kc29uCiAgICAgICAgICAgIGZvcmVhY2ggKCRmIGluICRhcnF1aXZvcykgewogICAgICAgICAgICAgICAgaWYgKCRmLk5hbWUgLWxpa2UgIioucGRmIiAtYW5kICRmLk5hbWUgLW5lICRub21lKSB7CiAgICAgICAgICAgICAgICAgICAgJG1vZFRpbWUgPSBbRGF0ZVRpbWVdOjpQYXJzZSgkZi5Nb2RUaW1lLCAkbnVsbCwgW1N5c3RlbS5HbG9iYWxpemF0aW9uLkRhdGVUaW1lU3R5bGVzXTo6Um91bmR0cmlwS2luZCkKICAgICAgICAgICAgICAgICAgICBpZiAoJG1vZFRpbWUuVG9Mb2NhbFRpbWUoKS5Ub1N0cmluZygieXl5eS1NTS1kZCIpIC1lcSAkaG9qZSkgewogICAgICAgICAgICAgICAgICAgICAgICAkZlNlbUV4dCA9IFtTeXN0ZW0uSU8uUGF0aF06OkdldEZpbGVOYW1lV2l0aG91dEV4dGVuc2lvbigkZi5OYW1lKQogICAgICAgICAgICAgICAgICAgICAgICAkYXBhZ2FyICA9ICRmYWxzZQogICAgICAgICAgICAgICAgICAgICAgICBpZiAoJGVoUFZDKSAgICAgIHsgJGFwYWdhciA9ICRmU2VtRXh0IC1tYXRjaCAnKD9pKXB2YyQnIH0KICAgICAgICAgICAgICAgICAgICAgICAgZWxzZWlmICgkZWhBTE0pICB7ICRhcGFnYXIgPSAkZlNlbUV4dCAtbWF0Y2ggJyg/aSlhbG0kJyB9CiAgICAgICAgICAgICAgICAgICAgICAgIGVsc2UgICAgICAgICAgICAgeyAkYXBhZ2FyID0gJGZTZW1FeHQgLW5vdG1hdGNoICcoP2kpKHB2Y3xhbG0pJCcgfSAgIyBjb21wbGV0bzogcmVtb3ZlIHPDsyBvdXRybyBjb21wbGV0byBkbyBkaWEKICAgICAgICAgICAgICAgICAgICAgICAgaWYgKCRhcGFnYXIpIHsKICAgICAgICAgICAgICAgICAgICAgICAgICAgIExvZyAiICBBcGFnYW5kbyBQREYgYW50ZXJpb3IgZG8gbWVzbW8gZGlhOiAkKCRmLk5hbWUpIgogICAgICAgICAgICAgICAgICAgICAgICAgICAgJiAkcmNsb25lIGRlbGV0ZWZpbGUgImVnZW1hcDokZGVzdGluby8kKCRmLk5hbWUpIiAtLWNvbmZpZyAkY29uZiAyPiYxIHwgT3V0LU51bGwKICAgICAgICAgICAgICAgICAgICAgICAgfQogICAgICAgICAgICAgICAgICAgIH0KICAgICAgICAgICAgICAgIH0KICAgICAgICAgICAgfQogICAgICAgIH0gY2F0Y2gge30KICAgIH0KCiAgICAkciA9ICYgJHJjbG9uZSBjb3B5dG8gJGFycSAiZWdlbWFwOiRkZXN0aW5vLyRub21lIiAtLWNvbmZpZyAkY29uZiAtLWlnbm9yZS10aW1lcyAyPiYxCiAgICBpZiAoJExBU1RFWElUQ09ERSAtZXEgMCkgewogICAgICAgIExvZyAiICBbT0tdIEVudmlhZG8gcGFyYSBvIERyaXZlIgogICAgICAgICRva1skYXJxXSA9IChHZXQtSXRlbSAkYXJxKS5MYXN0V3JpdGVUaW1lLlRvU3RyaW5nKCJvIikKICAgICAgICBTYWx2YXIgJG9rCiAgICB9IGVsc2UgewogICAgICAgIExvZyAiICBbRVJST10gRmFsaGEgbm8gZW52aW8iCiAgICAgICAgTG9nICIgIERldGFsaGU6ICRyIgogICAgfQogICAgTG9nICIiCn0KCmlmICgtbm90IChUZXN0LVBhdGggJHBhc3RhKSkgIHsgTG9nICJFUlJPOiBwYXN0YSBuYW8gZW5jb250cmFkYTogJHBhc3RhIjsgUmVhZC1Ib3N0ICJFbnRlciBwYXJhIGZlY2hhciI7IGV4aXQgMSB9CmlmICgtbm90IChUZXN0LVBhdGggJHJjbG9uZSkpIHsgTG9nICJFUlJPOiByY2xvbmUuZXhlIGF1c2VudGUuIFJvZGUgRUdFTUFQX0lOU1RBTEFSLmJhdCI7IFJlYWQtSG9zdCAiRW50ZXIgcGFyYSBmZWNoYXIiOyBleGl0IDEgfQoKTG9nICI9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09IgpMb2cgIiAgQWdlbnRlIEVnZW1hcCAtIERyaXZlIgpMb2cgIj09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0iCkxvZyAiTW9uaXRvcmFuZG86ICRwYXN0YSIKTG9nICJFc3RydXR1cmE6ICAgT3JjYW1lbnRvcyAvIDIwMjYgLyBFc3RhZG8gLyBDaWRhZGUgLyBDbGllbnRlIC8gUERGIgpMb2cgIiIKCiRvayA9IEVudmlhZG9zCgppZiAoJG9rLkNvdW50IC1lcSAwKSB7CiAgICBMb2cgIkluaWNpYWxpemFuZG86IHJlZ2lzdHJhbmRvIGFycXVpdm9zIGV4aXN0ZW50ZXMgKG5hbyBzZXJhbyBlbnZpYWRvcykuLi4iCiAgICBHZXQtQ2hpbGRJdGVtIC1QYXRoICRwYXN0YSAtRmlsdGVyICIqLnBkZiIgLVJlY3Vyc2UgLUVycm9yQWN0aW9uIFNpbGVudGx5Q29udGludWUgfCBGb3JFYWNoLU9iamVjdCB7CiAgICAgICAgJG9rWyRfLkZ1bGxOYW1lXSA9ICJpZ25vcmFkbyIKICAgIH0KICAgIFNhbHZhciAkb2sKICAgIExvZyAiUHJvbnRvLiBNb25pdG9yYW5kbyBhcGVuYXMgYXJxdWl2b3Mgbm92b3MgYSBwYXJ0aXIgZGUgYWdvcmEuIgogICAgTG9nICIiCn0KCndoaWxlICgkdHJ1ZSkgewogICAgR2V0LUNoaWxkSXRlbSAtUGF0aCAkcGFzdGEgLUZpbHRlciAiKi5wZGYiIC1SZWN1cnNlIC1FcnJvckFjdGlvbiBTaWxlbnRseUNvbnRpbnVlIHwgRm9yRWFjaC1PYmplY3QgewogICAgICAgICRhcnEgPSAkXy5GdWxsTmFtZQoKICAgICAgICAkcmVlbnZpbyA9ICRmYWxzZQogICAgICAgIGlmICgkb2suQ29udGFpbnNLZXkoJGFycSkpIHsKICAgICAgICAgICAgaWYgKCRva1skYXJxXSAtZXEgImlnbm9yYWRvIikgeyByZXR1cm4gfQogICAgICAgICAgICAkbXRpbWUgPSAkXy5MYXN0V3JpdGVUaW1lLlRvU3RyaW5nKCJvIikKICAgICAgICAgICAgaWYgKCRva1skYXJxXSAtZXEgJG10aW1lKSB7IHJldHVybiB9CiAgICAgICAgICAgICRyZWVudmlvID0gJHRydWUKICAgICAgICB9CgogICAgICAgICRyZWwgPSAkYXJxLlN1YnN0cmluZygkcGFzdGEuTGVuZ3RoKS5UcmltU3RhcnQoIlwiLCAiLyIpCiAgICAgICAgJHAgICA9ICRyZWwgLXNwbGl0ICJbXFwvXSIKCiAgICAgICAgaWYgKCRwLkNvdW50IC1sdCA1KSB7CiAgICAgICAgICAgICRva1skYXJxXSA9ICJpZ25vcmFkbyIKICAgICAgICAgICAgU2FsdmFyICRvawogICAgICAgICAgICByZXR1cm4KICAgICAgICB9CgogICAgICAgICRhbm8gICAgID0gJHBbMF0uVHJpbSgpCiAgICAgICAgJGNpZGFkZSAgPSAkcFsyXS5UcmltKCkKICAgICAgICAkY2xpZW50ZSA9ICRwWzNdLlRyaW0oKQogICAgICAgICRub21lICAgID0gJHBbLTFdLlRyaW0oKQoKICAgICAgICBpZiAoJGFubyAtbmUgJGNmZy5hbm8pIHsKICAgICAgICAgICAgJG9rWyRhcnFdID0gImlnbm9yYWRvIgogICAgICAgICAgICBTYWx2YXIgJG9rCiAgICAgICAgICAgIHJldHVybgogICAgICAgIH0KCiAgICAgICAgaWYgKCRub21lIC1ub3RsaWtlICIqUHJvcG9zdGEgQ29tZXJjaWFsKiIgLWFuZCAkbm9tZSAtbm90bGlrZSAiKlByb3Bvc3RhX0NvbWVyY2lhbCoiKSB7CiAgICAgICAgICAgICRva1skYXJxXSA9ICJpZ25vcmFkbyIKICAgICAgICAgICAgU2FsdmFyICRvawogICAgICAgICAgICByZXR1cm4KICAgICAgICB9CgogICAgICAgICRub21lU2VtRXh0ID0gW1N5c3RlbS5JTy5QYXRoXTo6R2V0RmlsZU5hbWVXaXRob3V0RXh0ZW5zaW9uKCRub21lKQoKICAgICAgICAjIFBERiBjb21wbGV0bzogbm9tZSB0ZXJtaW5hIGNvbSBkYXRhIERELU1NIChleDogIlByb3Bvc3RhIENvbWVyY2lhbCBKb2FvIDE3LTA3IikKICAgICAgICAkZWhDb21wbGV0byA9ICRub21lU2VtRXh0IC1tYXRjaCAnXGR7Mn0tXGR7Mn0kJwoKICAgICAgICAjIFBERiBkZSBtYXRlcmlhbDogbm9tZSB0ZXJtaW5hIGNvbSBwdmMgb3UgYWxtCiAgICAgICAgJGVoTWF0ZXJpYWwgPSAkbm9tZVNlbUV4dCAtbWF0Y2ggJyg/aSkocHZjfGFsbSkkJwoKICAgICAgICAkZGVzdGlubyA9ICIkYW5vLyRjaWRhZGUvJGNsaWVudGUiCgogICAgICAgIGlmICgkZWhDb21wbGV0bykgewogICAgICAgICAgICAjIFBERiBmaW5hbCBjb20gZG9pcyBvcmNhbWVudG9zIHVuaWRvcyAtIGVudmlhIGltZWRpYXRhbWVudGUKICAgICAgICAgICAgIyBNYXJjYSBvcyBQREZzIHB2Yy9hbG0gZGVzdGEgcGFzdGEgY29tbyBpZ25vcmFkb3MgKG5hbyBwcmVjaXNhbSBtYWlzIHN1YmlyKQogICAgICAgICAgICAkcGFzdGFDbGllbnRlID0gU3BsaXQtUGF0aCAkYXJxIC1QYXJlbnQKICAgICAgICAgICAgR2V0LUNoaWxkSXRlbSAtUGF0aCAkcGFzdGFDbGllbnRlIC1GaWx0ZXIgIioucGRmIiAtRXJyb3JBY3Rpb24gU2lsZW50bHlDb250aW51ZSB8IEZvckVhY2gtT2JqZWN0IHsKICAgICAgICAgICAgICAgICRvdXRybyA9ICRfLkZ1bGxOYW1lCiAgICAgICAgICAgICAgICBpZiAoJG91dHJvIC1uZSAkYXJxKSB7CiAgICAgICAgICAgICAgICAgICAgJG91dHJvU2VtRXh0ID0gW1N5c3RlbS5JTy5QYXRoXTo6R2V0RmlsZU5hbWVXaXRob3V0RXh0ZW5zaW9uKCRfLk5hbWUpCiAgICAgICAgICAgICAgICAgICAgaWYgKCRvdXRyb1NlbUV4dCAtbWF0Y2ggJyg/aSkocHZjfGFsbSkkJykgewogICAgICAgICAgICAgICAgICAgICAgICAkb2tbJG91dHJvXSA9ICJpZ25vcmFkbyIKICAgICAgICAgICAgICAgICAgICB9CiAgICAgICAgICAgICAgICB9CiAgICAgICAgICAgIH0KICAgICAgICAgICAgU2FsdmFyICRvawoKICAgICAgICAgICAgaWYgKCRyZWVudmlvKSB7IExvZyAiUERGIGNvbXBsZXRvIGF0dWFsaXphZG86ICRub21lIiB9IGVsc2UgeyBMb2cgIlBERiBjb21wbGV0byAoZG9pcyBvcmNhbWVudG9zKTogJG5vbWUiIH0KICAgICAgICAgICAgTG9nICIgIENsaWVudGU6ICRjbGllbnRlIHwgQ2lkYWRlOiAkY2lkYWRlIgogICAgICAgICAgICBFbnZpYXJQYXJhRHJpdmUgJGFycSAkbm9tZSAkZGVzdGlubyAkcmVlbnZpbwoKICAgICAgICB9IGVsc2VpZiAoJGVoTWF0ZXJpYWwpIHsKICAgICAgICAgICAgIyBQREYgZGUgbWF0ZXJpYWwgKHB2YyBvdSBhbG0pIC0gZW52aWEgaW1lZGlhdGFtZW50ZQogICAgICAgICAgICAjIFNlIHZpZXIgdW0gUERGIGNvbXBsZXRvIGRlcG9pcyBubyBtZXNtbyBkaWEsIG8gY2xlYW51cCBkbyBEcml2ZSBhcGFnYSBlc3RlIGF1dG9tYXRpY2FtZW50ZQogICAgICAgICAgICBpZiAoJHJlZW52aW8pIHsgTG9nICJQREYgbWF0ZXJpYWwgYXR1YWxpemFkbzogJG5vbWUiIH0gZWxzZSB7IExvZyAiUERGIG1hdGVyaWFsIChwdmMvYWxtKTogJG5vbWUiIH0KICAgICAgICAgICAgTG9nICIgIENsaWVudGU6ICRjbGllbnRlIHwgQ2lkYWRlOiAkY2lkYWRlIgogICAgICAgICAgICBFbnZpYXJQYXJhRHJpdmUgJGFycSAkbm9tZSAkZGVzdGlubyAkcmVlbnZpbwoKICAgICAgICB9IGVsc2UgewogICAgICAgICAgICAjIE5vbWUgbmFvIHJlY29uaGVjaWRvIGNvbW8gUERGIGZpbmFsIC0gaWdub3JhCiAgICAgICAgICAgICRva1skYXJxXSA9ICJpZ25vcmFkbyIKICAgICAgICAgICAgU2FsdmFyICRvawogICAgICAgIH0KICAgIH0KICAgIFN0YXJ0LVNsZWVwIDEwCn0K"
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
