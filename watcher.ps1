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

if ($ok.Count -eq 0) {
    Log "Inicializando: registrando arquivos existentes (nao serao enviados)..."
    Get-ChildItem -Path $pasta -Filter "*.pdf" -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
        $ok[$_.FullName] = "ignorado"
    }
    Salvar $ok
    Log "Pronto. Monitorando apenas arquivos novos a partir de agora."
    Log ""
}

# PDFs pvc/alm aguardam 5 minutos antes de enviar,
# para ver se aparece um PDF completo com data (dois orcamentos unidos)
$aguardando = @{}

while ($true) {
    Get-ChildItem -Path $pasta -Filter "*.pdf" -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
        $arq = $_.FullName

        $reenvio = $false
        if ($ok.ContainsKey($arq)) {
            if ($ok[$arq] -eq "ignorado") { return }
            $mtime = $_.LastWriteTime.ToString("o")
            if ($ok[$arq] -eq $mtime) { return }
            $reenvio = $true
        }

        $rel = $arq.Substring($pasta.Length).TrimStart("\", "/")
        $p   = $rel -split "[\\/]"

        if ($p.Count -lt 5) {
            $ok[$arq] = "ignorado"
            Salvar $ok
            return
        }

        $ano     = $p[0].Trim()
        $cidade  = $p[2].Trim()
        $cliente = $p[3].Trim()
        $nome    = $p[-1].Trim()

        if ($ano -ne $cfg.ano) {
            $ok[$arq] = "ignorado"
            Salvar $ok
            return
        }

        if ($nome -notlike "*Proposta Comercial*") {
            $ok[$arq] = "ignorado"
            Salvar $ok
            return
        }

        $nomeSemExt = [System.IO.Path]::GetFileNameWithoutExtension($nome)

        # PDF completo: nome termina com data DD-MM (ex: "Proposta Comercial Joao 17-07")
        $ehCompleto = $nomeSemExt -match '\d{2}-\d{2}$'

        # PDF de material: nome termina com pvc ou alm
        $ehMaterial = $nomeSemExt -match '(?i)(pvc|alm)$'

        if ($ehCompleto) {
            # PDF final com dois orcamentos unidos - envia imediatamente
            # Cancela e ignora os PDFs pvc/alm desta pasta de cliente
            $pastaCliente = Split-Path $arq -Parent
            Get-ChildItem -Path $pastaCliente -Filter "*.pdf" -ErrorAction SilentlyContinue | ForEach-Object {
                $outro = $_.FullName
                if ($outro -ne $arq) {
                    $outroSemExt = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
                    if ($outroSemExt -match '(?i)(pvc|alm)$') {
                        $ok[$outro] = "ignorado"
                        $aguardando.Remove($outro)
                    }
                }
            }
            Salvar $ok

            Start-Sleep 3
            if (-not (Test-Path $arq)) { return }
            if ($reenvio) { Log "PDF completo atualizado: $nome" } else { Log "PDF completo (dois orcamentos): $nome" }
            Log "  Cliente: $cliente | Cidade: $cidade"

            $destino = "$ano/$cidade/$cliente"
            $r = & $rclone copyto $arq "egemap:$destino/$nome" --config $conf --ignore-times 2>&1
            if ($LASTEXITCODE -eq 0) {
                Log "  [OK] Enviado para o Drive"
                $ok[$arq] = (Get-Item $arq).LastWriteTime.ToString("o")
                Salvar $ok
            } else {
                Log "  [ERRO] Falha no envio"
                Log "  Detalhe: $r"
            }
            Log ""

        } elseif ($ehMaterial) {
            # PDF de material unico (pvc ou alm)

            # Se o arquivo foi modificado apos ja ter sido enviado, reenvia diretamente
            if ($reenvio) {
                Start-Sleep 3
                if (-not (Test-Path $arq)) { return }
                Log "PDF material atualizado: $nome"
                Log "  Cliente: $cliente | Cidade: $cidade"
                $destino = "$ano/$cidade/$cliente"
                $r = & $rclone copyto $arq "egemap:$destino/$nome" --config $conf --ignore-times 2>&1
                if ($LASTEXITCODE -eq 0) {
                    Log "  [OK] Enviado para o Drive"
                    $ok[$arq] = (Get-Item $arq).LastWriteTime.ToString("o")
                    Salvar $ok
                } else {
                    Log "  [ERRO] Falha no envio"
                    Log "  Detalhe: $r"
                }
                Log ""
                return
            }

            # Verifica se ja existe PDF completo (com data) na pasta do cliente
            $pastaCliente = Split-Path $arq -Parent
            $temCompleto = Get-ChildItem -Path $pastaCliente -Filter "*.pdf" -ErrorAction SilentlyContinue |
                           Where-Object { [System.IO.Path]::GetFileNameWithoutExtension($_.Name) -match '\d{2}-\d{2}$' } |
                           Select-Object -First 1

            if ($temCompleto) {
                $ok[$arq] = "ignorado"
                $aguardando.Remove($arq)
                Salvar $ok
                return
            }

            # Aguarda 5 minutos para ver se aparece o PDF completo
            if (-not $aguardando.ContainsKey($arq)) {
                $aguardando[$arq] = Get-Date
                Log "Aguardando 5 min (verificando se sera gerado PDF completo): $nome"
                return
            }

            $elapsed = (Get-Date) - $aguardando[$arq]
            if ($elapsed.TotalMinutes -lt 5) { return }

            # Verifica novamente apos 5 minutos
            $temCompleto = Get-ChildItem -Path $pastaCliente -Filter "*.pdf" -ErrorAction SilentlyContinue |
                           Where-Object { [System.IO.Path]::GetFileNameWithoutExtension($_.Name) -match '\d{2}-\d{2}$' } |
                           Select-Object -First 1
            $aguardando.Remove($arq)

            if ($temCompleto) {
                $ok[$arq] = "ignorado"
                Salvar $ok
                return
            }

            # Confirmado: material unico, nenhum PDF completo apareceu - envia
            Start-Sleep 3
            if (-not (Test-Path $arq)) { return }
            Log "PDF material unico: $nome"
            Log "  Cliente: $cliente | Cidade: $cidade"
            $destino = "$ano/$cidade/$cliente"
            $r = & $rclone copyto $arq "egemap:$destino/$nome" --config $conf --ignore-times 2>&1
            if ($LASTEXITCODE -eq 0) {
                Log "  [OK] Enviado para o Drive"
                $ok[$arq] = (Get-Item $arq).LastWriteTime.ToString("o")
                Salvar $ok
            } else {
                Log "  [ERRO] Falha no envio"
                Log "  Detalhe: $r"
            }
            Log ""

        } else {
            # Nome nao reconhecido como PDF final - ignora
            $ok[$arq] = "ignorado"
            Salvar $ok
        }
    }
    Start-Sleep 10
}
