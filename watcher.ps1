param([string]$Config = "$PSScriptRoot\config.json")

$cfg     = Get-Content $Config -Raw | ConvertFrom-Json
$pasta   = $cfg.pasta_orcamentos
$rclone  = "$PSScriptRoot\rclone.exe"
$conf    = "$PSScriptRoot\rclone.conf"
$log     = "$PSScriptRoot\watcher.log"
$vistos  = "$PSScriptRoot\enviados.json"
$ano     = (Get-Date).Year.ToString()

function Log($m) {
    $l = "$(Get-Date -f 'yyyy-MM-dd HH:mm')  $m"
    Add-Content $log $l
    Write-Host $l
}

function Enviados {
    if (Test-Path $vistos) {
        try { return (Get-Content $vistos -Raw | ConvertFrom-Json -AsHashtable) } catch {}
    }
    return @{}
}

function Salvar($h) { $h | ConvertTo-Json | Set-Content $vistos -Encoding UTF8 }

if (-not (Test-Path $pasta))  { Log "ERRO: pasta nao encontrada: $pasta"; Read-Host; exit 1 }
if (-not (Test-Path $rclone)) { Log "ERRO: rclone.exe nao encontrado. Rode INSTALAR.bat"; Read-Host; exit 1 }

Log "===================================================="
Log "  Agente Egemap - Drive rodando"
Log "===================================================="
Log "Pasta: $pasta"
Log ""

$ok = Enviados

while ($true) {
    $anoAtual = (Get-Date).Year.ToString()
    if ($ano -ne $anoAtual) { $ano = $anoAtual; Log "Ano: $ano" }

    Get-ChildItem -Path $pasta -Filter "*.pdf" -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
        $arq = $_.FullName
        if ($ok.ContainsKey($arq)) { return }

        $rel   = $arq.Substring($pasta.TrimEnd("/\").Length).TrimStart("\", "/")
        $p     = $rel -split "[\\/]"
        if ($p.Count -lt 3) { $ok[$arq] = "ignorado"; Salvar $ok; return }

        $cidade  = $p[0]
        $cliente = $p[1]
        $nome    = $p[-1]

        Start-Sleep 2
        if (-not (Test-Path $arq)) { return }

        Log "Novo: $nome"
        Log "  $cidade / $cliente"

        $r = & $rclone copy $arq "egemap:$ano/$cidade/$cliente" --config $conf 2>&1
        if ($LASTEXITCODE -eq 0) {
            Log "  [OK] Enviado"
            $ok[$arq] = "ok"
            Salvar $ok
        } else {
            Log "  [ERRO] Vai tentar de novo"
        }
        Log ""
    }
    Start-Sleep 10
}
