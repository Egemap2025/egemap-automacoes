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

function EnviarParaDrive($arq, $nome, $destino, $reenvio) {
    Start-Sleep 3
    if (-not (Test-Path $arq)) { return }

    # Remove PDFs do mesmo dia ja existentes na pasta do cliente no Drive
    $hoje = (Get-Date).ToString("yyyy-MM-dd")
    $jsonDrive = (& $rclone lsjson "egemap:$destino" --config $conf 2>&1) | Out-String
    if ($LASTEXITCODE -eq 0 -and $jsonDrive -match '\[') {
        try {
            $arquivos = $jsonDrive | ConvertFrom-Json
            foreach ($f in $arquivos) {
                if ($f.Name -like "*.pdf" -and $f.Name -ne $nome) {
                    $modTime = [DateTime]::Parse($f.ModTime, $null, [System.Globalization.DateTimeStyles]::RoundtripKind)
                    if ($modTime.ToLocalTime().ToString("yyyy-MM-dd") -eq $hoje) {
                        Log "  Apagando PDF anterior do mesmo dia: $($f.Name)"
                        & $rclone deletefile "egemap:$destino/$($f.Name)" --config $conf 2>&1 | Out-Null
                    }
                }
            }
        } catch {}
    }

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
}

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

        if ($nome -notlike "*Proposta Comercial*" -and $nome -notlike "*Proposta_Comercial*") {
            $ok[$arq] = "ignorado"
            Salvar $ok
            return
        }

        $nomeSemExt = [System.IO.Path]::GetFileNameWithoutExtension($nome)

        # PDF completo: nome termina com data DD-MM (ex: "Proposta Comercial Joao 17-07")
        $ehCompleto = $nomeSemExt -match '\d{2}-\d{2}$'

        # PDF de material: nome termina com pvc ou alm
        $ehMaterial = $nomeSemExt -match '(?i)(pvc|alm)$'

        $destino = "$ano/$cidade/$cliente"

        if ($ehCompleto) {
            # PDF final com dois orcamentos unidos - envia imediatamente
            # Marca os PDFs pvc/alm desta pasta como ignorados (nao precisam mais subir)
            $pastaCliente = Split-Path $arq -Parent
            Get-ChildItem -Path $pastaCliente -Filter "*.pdf" -ErrorAction SilentlyContinue | ForEach-Object {
                $outro = $_.FullName
                if ($outro -ne $arq) {
                    $outroSemExt = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
                    if ($outroSemExt -match '(?i)(pvc|alm)$') {
                        $ok[$outro] = "ignorado"
                    }
                }
            }
            Salvar $ok

            if ($reenvio) { Log "PDF completo atualizado: $nome" } else { Log "PDF completo (dois orcamentos): $nome" }
            Log "  Cliente: $cliente | Cidade: $cidade"
            EnviarParaDrive $arq $nome $destino $reenvio

        } elseif ($ehMaterial) {
            # PDF de material (pvc ou alm)
            # Verifica se ja existe PDF completo (com data) na pasta local do cliente
            $pastaCliente = Split-Path $arq -Parent
            $temCompleto = Get-ChildItem -Path $pastaCliente -Filter "*.pdf" -ErrorAction SilentlyContinue |
                           Where-Object { [System.IO.Path]::GetFileNameWithoutExtension($_.Name) -match '\d{2}-\d{2}$' } |
                           Select-Object -First 1

            if ($temCompleto) {
                # PDF completo ja existe na pasta - este e intermediario, ignora
                $ok[$arq] = "ignorado"
                Salvar $ok
                return
            }

            # Sem PDF completo: envia imediatamente
            # Se vier um PDF completo depois no mesmo dia, o cleanup apaga este do Drive automaticamente
            if ($reenvio) { Log "PDF material atualizado: $nome" } else { Log "PDF material (pvc/alm): $nome" }
            Log "  Cliente: $cliente | Cidade: $cidade"
            EnviarParaDrive $arq $nome $destino $reenvio

        } else {
            # Nome nao reconhecido como PDF final - ignora
            $ok[$arq] = "ignorado"
            Salvar $ok
        }
    }
    Start-Sleep 10
}
