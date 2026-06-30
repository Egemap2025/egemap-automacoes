# watcher.ps1
# Monitora a pasta de orcamentos e envia PDFs automaticamente para o Google Drive.
# Roda em segundo plano. Nao feche esta janela enquanto quiser o agente ativo.

param(
    [string]$ConfigFile = "$PSScriptRoot\config.json"
)

# ── Carregar configuracao ────────────────────────────────────────────────────
if (-not (Test-Path $ConfigFile)) {
    Write-Host "[ERRO] config.json nao encontrado. Execute INSTALAR.bat primeiro." -ForegroundColor Red
    Read-Host "Pressione Enter para fechar"
    exit 1
}

$config          = Get-Content $ConfigFile -Raw | ConvertFrom-Json
$pastaLocal      = $config.pasta_orcamentos
$rclone          = "$PSScriptRoot\rclone.exe"
$rcloneConf      = "$PSScriptRoot\rclone.conf"
$logFile         = "$PSScriptRoot\watcher.log"
$processados     = "$PSScriptRoot\processados.json"
$ano             = (Get-Date).Year.ToString()

# ── Funcoes ──────────────────────────────────────────────────────────────────
function Registrar($msg) {
    $linha = "$(Get-Date -Format 'yyyy-MM-dd HH:mm')  $msg"
    Add-Content -Path $logFile -Value $linha -Encoding UTF8
    Write-Host $linha
}

function EnviarDrive($arquivo, $cidade, $cliente) {
    $destino = "$ano/$cidade/$cliente"
    $resultado = & $rclone copy $arquivo "egemap:$destino" --config $rcloneConf 2>&1
    return $LASTEXITCODE -eq 0
}

function CarregarProcessados() {
    if (Test-Path $processados) {
        return (Get-Content $processados -Raw | ConvertFrom-Json -AsHashtable)
    }
    return @{}
}

function SalvarProcessados($hash) {
    $hash | ConvertTo-Json | Set-Content $processados -Encoding UTF8
}

# ── Verificacoes iniciais ────────────────────────────────────────────────────
if (-not (Test-Path $pastaLocal)) {
    Registrar "[ERRO] Pasta nao encontrada: $pastaLocal"
    Registrar "       Corrija o caminho em config.json e reinicie."
    Read-Host "Pressione Enter para fechar"
    exit 1
}

if (-not (Test-Path $rclone)) {
    Registrar "[ERRO] rclone.exe nao encontrado. Execute INSTALAR.bat novamente."
    Read-Host "Pressione Enter para fechar"
    exit 1
}

# ── Inicio ───────────────────────────────────────────────────────────────────
Registrar "===================================================="
Registrar "  Agente de Orcamentos - Drive (em execucao)"
Registrar "===================================================="
Registrar "Pasta monitorada: $pastaLocal"
Registrar "Aguardando novos arquivos..."
Registrar ""

$vistos = CarregarProcessados

# ── Loop principal ───────────────────────────────────────────────────────────
while ($true) {
    # Atualiza ano automaticamente na virada
    $anoAtual = (Get-Date).Year.ToString()
    if ($ano -ne $anoAtual) {
        $ano = $anoAtual
        Registrar "Ano atualizado para $ano"
    }

    # Busca todos os PDFs na pasta
    Get-ChildItem -Path $pastaLocal -Filter "*.pdf" -Recurse -ErrorAction SilentlyContinue |
    ForEach-Object {
        $arquivo = $_.FullName

        # Pula arquivos ja processados
        if ($vistos.ContainsKey($arquivo)) { return }

        # Extrai cidade e cliente do caminho
        # Estrutura: {pastaLocal}\{Cidade}\{Cliente}\arquivo.pdf
        $relativo = $arquivo.Substring($pastaLocal.Length).TrimStart("\", "/")
        $partes   = $relativo -split "[\\/]"

        if ($partes.Count -lt 3) {
            $vistos[$arquivo] = "ignorado"
            SalvarProcessados $vistos
            return
        }

        $cidade  = $partes[0]
        $cliente = $partes[1]
        $nome    = $partes[-1]

        # Aguarda o arquivo terminar de ser gravado
        Start-Sleep -Seconds 2
        if (-not (Test-Path $arquivo)) { return }

        Registrar "Novo arquivo: $nome"
        Registrar "  Cidade:  $cidade"
        Registrar "  Cliente: $cliente"

        $ok = EnviarDrive $arquivo $cidade $cliente

        if ($ok) {
            Registrar "  [ENVIADO] $nome"
            $vistos[$arquivo] = "enviado"
        } else {
            Registrar "  [ERRO] Falha ao enviar. Vai tentar novamente em breve."
            # Nao marca como processado para tentar de novo
            return
        }
        Registrar ""
        SalvarProcessados $vistos
    }

    Start-Sleep -Seconds 10
}
