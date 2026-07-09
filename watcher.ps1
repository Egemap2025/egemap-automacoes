param([string]$Config = "$PSScriptRoot\config.json")

$cfg    = Get-Content $Config -Raw | ConvertFrom-Json
$pasta  = $cfg.pasta_orcamentos.TrimEnd("/\")
$rclone = "$PSScriptRoot\rclone.exe"
$conf   = "$PSScriptRoot\rclone.conf"
$log    = "$PSScriptRoot\watcher.log"
$vistos = "$PSScriptRoot\enviados.json"

function Log($m) {
    $l = "$(Get-Date -f 'yyyy-MM-dd HH:mm')  $m"
    Add-Content $log $l -Encoding UTF8
    Write-Host $l
}

function Enviados {
    if (Test-Path $vistos) {
        try { return (Get-Content $vistos -Raw | ConvertFrom-Json -AsHashtable) } catch {}
    }
    return @{}
}

function Salvar($h) { $h | ConvertTo-Json | Set-Content $vistos -Encoding UTF8 }

if (-not (Test-Path $pasta))  { Log "ERRO: pasta nao encontrada: $pasta"; Read-Host "Enter para fechar"; exit 1 }
if (-not (Test-Path $rclone)) { Log "ERRO: rclone.exe ausente. Rode EGEMAP_INSTALAR.bat"; Read-Host "Enter para fechar"; exit 1 }

Log "======================================================="
Log "  Agente Egemap - Drive"
Log "======================================================="
Log "Monitorando: $pasta"
Log "Estrutura:   Orcamentos / 2026 / Estado / Cidade / Cliente / PDF"
Log ""

$ok = Enviados

# Na primeira execucao (ou apos atualizacao): marca arquivos existentes como ja vistos sem enviar
if ($ok.Count -eq 0) {
    Log "Inicializando: registrando arquivos existentes (nao serao enviados)..."
    Get-ChildItem -Path $pasta -Filter "*.pdf" -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
        $ok[$_.FullName] = "ignorado"
    }
    Salvar $ok
    Log "Pronto. Monitorando apenas arquivos novos a partir de agora."
    Log ""
}

while ($true) {
    Get-ChildItem -Path $pasta -Filter "*.pdf" -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
        $arq = $_.FullName

        # Ignora arquivos ja processados, a menos que tenham sido modificados
        $reenvio = $false
        if ($ok.ContainsKey($arq)) {
            if ($ok[$arq] -eq "ignorado") { return }
            $mtime = $_.LastWriteTime.ToString("o")
            if ($ok[$arq] -eq $mtime) { return }
            $reenvio = $true
        }

        # Estrutura esperada:
        #  {pasta} / {Ano} / {Estado} / {Cidade} / {Cliente} / arquivo.pdf
        #  partes:    [0]      [1]        [2]         [3]        [4=nome]
        $rel   = $arq.Substring($pasta.Length).TrimStart("\", "/")
        $p     = $rel -split "[\\/]"

        if ($p.Count -lt 5) {
            # Arquivo fora da estrutura correta — ignora sem logar
            $ok[$arq] = "ignorado"
            Salvar $ok
            return
        }

        $ano     = $p[0].Trim()
        $cidade  = $p[2].Trim()
        $cliente = $p[3].Trim()
        $nome    = $p[-1].Trim()

        # Somente o ano configurado (ignora pastas de anos anteriores)
        if ($ano -ne $cfg.ano) {
            $ok[$arq] = "ignorado"
            Salvar $ok
            return
        }

        # Somente arquivos com "Proposta Comercial" no nome
        if ($nome -notlike "*Proposta Comercial*") {
            $ok[$arq] = "ignorado"
            Salvar $ok
            return
        }

        # Aguarda o arquivo terminar de ser gravado
        Start-Sleep 3
        if (-not (Test-Path $arq)) { return }

        if ($reenvio) { Log "Arquivo atualizado: $nome" } else { Log "Arquivo novo: $nome" }
        Log "  Ano:     $ano"
        Log "  Cidade:  $cidade"
        Log "  Cliente: $cliente"

        $destino = "$ano/$cidade/$cliente"

        $r = & $rclone copyto $arq "egemap:$destino/$nome" --config $conf --ignore-times 2>&1
        if ($LASTEXITCODE -eq 0) {
            Log "  [OK] Enviado para o Drive"
            $ok[$arq] = (Get-Item $arq).LastWriteTime.ToString("o")
            Salvar $ok
        } else {
            Log "  [ERRO] Falha - vai tentar de novo em 10s"
            Log "  Detalhe: $r"
        }
        Log ""
    }
    Start-Sleep 10
}
