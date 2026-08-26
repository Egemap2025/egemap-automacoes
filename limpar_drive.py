#!/usr/bin/env python3
"""
EGEMAP - Faxina nas pastas de orcamento do Google Drive

Junta as pastas repetidas e apaga o que ficou duplicado, deixando uma pasta
so para cada cidade e uma so para cada cliente.

O monitor criava pasta nova quando o nome so mudava de maiuscula ou acento --
para o Google Drive "Passo De Torres" e "Passo de Torres" sao duas pastas
diferentes. O monitor ja foi corrigido e nao faz mais isso; este programa
serve para arrumar o que ficou para tras.

  python limpar_drive.py            mostra o que vai fazer, SEM MEXER EM NADA
  python limpar_drive.py aplicar    faz a faxina de verdade
  python limpar_drive.py aplicar 2025    escolhe outro ano (padrao: o de hoje)

Nada e apagado de verdade: tudo vai para a Lixeira do Drive e da para
recuperar por 30 dias.

Roda pelo mesmo rclone que o monitor ja usa, entao nao precisa fazer login
de novo -- e importante que seja por ele, porque as pastas pertencem a conta
do rclone (orcamentosegemap), nao a que voce usa no navegador.
"""

import json
import subprocess
import sys
from datetime import date

import drive  # reaproveita o rclone ja configurado e a comparacao de nomes

# "de", "da", "dos"... escritos em minusculo sao o sinal da grafia certa:
# "Passo de Torres" e como voce escreve; "Passo De Torres" foi o monitor que
# inventou.
LIGACOES = {"de", "da", "do", "das", "dos", "e", "di", "du", "del", "y"}

APLICAR = False
feitos = {"movidos": 0, "apagados": 0, "pastas_removidas": 0}


def log(msg=""):
    print(msg, flush=True)


def rclone(*args, timeout=120, com_relatorio=False):
    """Roda o rclone. Devolve a saida normal, ou saida+relatorio quando
    com_relatorio=True.

    O rclone escreve o RESULTADO (json de listagem) na saida normal, mas o
    RELATORIO do que ele fez ("Merging N duplicate directories") na saida de
    erro -- mesmo quando deu tudo certo. Sem pedir as duas, o passo do dedupe
    dizia "nada a fazer" mesmo tendo o que fazer.
    """
    r = subprocess.run(
        [str(drive.RCLONE_EXE), *args, "--config", str(drive.RCLONE_CONF)],
        capture_output=True, timeout=timeout,
        # UTF-8 na marra: no Windows o padrao e cp1252, que nao sabe ler "Á"
        # (Alvaro) nem "Í". A leitura morria numa thread interna e a saida
        # voltava None.
        encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        detalhe = ((r.stderr or "") + (r.stdout or "")).strip().splitlines()
        raise RuntimeError(detalhe[-1] if detalhe else f"rclone falhou: {args}")
    if com_relatorio:
        return (r.stdout or "") + (r.stderr or "")
    return r.stdout or ""


def listar(caminho):
    """(pastas, arquivos) de uma pasta do Drive. Cada item e um dicionario
    com Name, Size e IsDir."""
    try:
        saida = rclone("lsjson", drive._remote(caminho))
    except Exception as e:
        log(f"    ! nao consegui ler {caminho}: {e}")
        return [], []
    itens = json.loads(saida) if saida.strip().startswith("[") else []
    return ([i for i in itens if i.get("IsDir")],
            [i for i in itens if not i.get("IsDir")])


def caminho(*partes):
    return "/".join(p for p in partes if p)


# ── Acoes (respeitam o modo "so mostrar") ────────────────────────────────────

def mover(origem, destino):
    log(f"    mover  {origem}")
    log(f"      -->  {destino}")
    if APLICAR:
        rclone("moveto", drive._remote(origem), drive._remote(destino))
    feitos["movidos"] += 1


def apagar_arquivo(caminho_arq, motivo):
    log(f"    apagar {caminho_arq}   ({motivo})")
    if APLICAR:
        rclone("deletefile", drive._remote(caminho_arq))
    feitos["apagados"] += 1


def remover_pasta(caminho_pasta):
    """So remove pasta VAZIA (rmdir, nunca purge).

    Se sobrou alguma coisa dentro, o rclone recusa e a pasta fica onde esta,
    com um aviso. E de proposito: apagar uma pasta com conteudo por engano e
    o unico erro aqui que nao teria conserto facil.
    """
    log(f"    remover pasta vazia  {caminho_pasta}")
    if APLICAR:
        try:
            rclone("rmdir", drive._remote(caminho_pasta))
        except Exception as e:
            log(f"    ! nao removi {caminho_pasta} (sobrou coisa dentro?): {e}")
            return
    feitos["pastas_removidas"] += 1


# ── Juntar duas pastas ───────────────────────────────────────────────────────

def juntar(origem, destino):
    """Passa tudo que esta em 'origem' para 'destino' e esvazia a origem.

    Arquivo que ja existe no destino com o mesmo nome e o mesmo tamanho e
    descartado em vez de virar uma segunda copia.
    """
    # Comparacao LITERAL de proposito: "Morro Da Fumaca" e "Morro da Fumaca"
    # sao caminhos diferentes e e exatamente isso que viemos juntar. O que nao
    # pode e mandar juntar uma pasta nela mesma -- isso acontece quando o Drive
    # tem duas pastas com o nome identico, caso que quem resolve e o
    # "rclone dedupe" la em cima.
    if origem == destino:
        log(f"    ! pulei: origem e destino sao o mesmo caminho ({origem})")
        return

    pastas_o, arquivos_o = listar(origem)
    pastas_d, arquivos_d = listar(destino)
    por_nome_d = {drive._normalizar(p["Name"]): p["Name"] for p in pastas_d}
    tamanhos_d = {a["Name"]: a.get("Size") for a in arquivos_d}

    for arq in arquivos_o:
        nome = arq["Name"]
        if nome in tamanhos_d and tamanhos_d[nome] == arq.get("Size"):
            apagar_arquivo(caminho(origem, nome), "copia identica ja esta no destino")
        else:
            mover(caminho(origem, nome), caminho(destino, nome))

    for pasta in pastas_o:
        nome = pasta["Name"]
        equivalente = por_nome_d.get(drive._normalizar(nome))
        if equivalente:
            juntar(caminho(origem, nome), caminho(destino, equivalente))
        else:
            mover(caminho(origem, nome), caminho(destino, nome))

    remover_pasta(origem)


# ── Escolher qual das repetidas fica ─────────────────────────────────────────

def _nota_grafia(nome):
    palavras = nome.split()
    minusculas = sum(1 for i, p in enumerate(palavras)
                     if i > 0 and p.lower() in LIGACOES and p == p.lower())
    caixa_alta = sum(1 for p in palavras if len(p) > 2 and p.isupper())
    return (minusculas, -caixa_alta)


def quanto_tem(caminho_pasta):
    pastas, arquivos = listar(caminho_pasta)
    return len(pastas) + len(arquivos)


def escolher_principal(base, nomes):
    """A que fica: primeiro a grafia escrita direito, depois a que tem mais
    coisa dentro."""
    return max(nomes, key=lambda n: (_nota_grafia(n), quanto_tem(caminho(base, n)), n))


def agrupar_repetidas(nomes):
    """{nome_normalizado: [nomes...]} so com os que aparecem mais de uma vez."""
    grupos = {}
    for n in nomes:
        grupos.setdefault(drive._normalizar(n), []).append(n)
    return {k: v for k, v in grupos.items() if len(v) > 1}


def limpar_repetidas(base, rotulo):
    """Junta as pastas repetidas que estao logo dentro de 'base'."""
    pastas, _ = listar(base)
    repetidas = agrupar_repetidas([p["Name"] for p in pastas])
    if not repetidas:
        return 0

    for _, nomes in sorted(repetidas.items()):
        principal = escolher_principal(base, nomes)
        outras = [n for n in nomes if n != principal]
        log(f"  {rotulo} repetida: fica {principal!r}")
        for outra in outras:
            log(f"    juntando {outra!r} em {principal!r}")
            juntar(caminho(base, outra), caminho(base, principal))
        log()
    return len(repetidas)


def juntar_nomes_identicos(ano):
    """Duas pastas com o nome EXATAMENTE igual no mesmo lugar.

    O Google Drive permite isso (o Windows nao), e foi o que aconteceu quando
    duas propostas subiam ao mesmo tempo e cada uma criava a pasta do cliente
    por conta -- dentro de Balneario Gaivota chegou a haver tres
    "Felipe Dos Santos Coelho". Nao da pra resolver pelo caminho, porque o
    caminho e o mesmo para as duas; quem resolve e o proprio rclone.
    """
    extra = [] if APLICAR else ["--dry-run"]
    saida = ""
    # O "dedupe" junta as pastas de nome igual sozinho, sempre -- nao existe
    # (e nao precisa de) um modo "merge". O modo diz o que fazer com ARQUIVO
    # repetido: "skip" e nao mexer em nenhum.
    passos = [
        # 1a passada: so juntar as pastas de nome igual, sem tocar em arquivo
        (["dedupe", "--dedupe-mode", "skip"], "juntando pastas de nome igual"),
        # 2a passada: dois arquivos com o MESMO NOME na MESMA pasta (o Drive
        # permite; foi o envio em paralelo que criou) -- fica o mais novo.
        #
        # De proposito sem --by-hash: por hash o rclone procura arquivo igual
        # na arvore inteira, e apagaria o PDF de um cliente so porque outro
        # cliente tem um identico. Arquivo repetido em pastas diferentes quem
        # trata e a funcao juntar(), que compara nome e tamanho dentro da
        # pasta de destino.
        (["dedupe", "--dedupe-mode", "newest"], "tirando arquivo repetido na mesma pasta"),
    ]
    for args, o_que in passos:
        try:
            saida += rclone(*args, drive._remote(ano), *extra,
                            timeout=600, com_relatorio=True)
        except Exception as e:
            if "insufficientFilePermissions" in str(e) or "Error 403" in str(e):
                # O rclone entra como orcamentosegemap. Arquivo que voce subiu
                # pelo navegador pertence a SUA conta, e o rclone nao pode
                # apagar arquivo dos outros -- nem sendo dono da pasta.
                log(f"   ! {o_que}: sobrou coisa que nao e da conta do monitor")
                log( "     (arquivo que voce subiu pelo navegador pertence a voce,")
                log( "      e o monitor nao pode apagar arquivo dos outros).")
                log( "      Esses precisam ser apagados por voce, no Drive.")
            else:
                log(f"   ! nao consegui ({o_que}): {e}")
    linhas = [l for l in saida.splitlines() if l.strip()]
    if linhas:
        for l in linhas[:40]:
            log(f"   {l}")
        if len(linhas) > 40:
            log(f"   ... e mais {len(linhas) - 40} linhas")
    else:
        log("   nada a fazer.")


# ── Pasta de estado (SC, RS) que virou "cidade" sem querer ───────────────────

def dissolver_estados(ano):
    """Pasta de duas letras dentro do ano e um estado, nao uma cidade.

    Nasceu quando uma proposta foi salva direto na pasta da cidade, sem pasta
    de cliente. As cidades que estao dentro dela sobem um nivel.
    """
    pastas, _ = listar(ano)
    estados = [p["Name"] for p in pastas if len(p["Name"].strip()) == 2]
    for estado in estados:
        log(f"  {estado!r} e um estado, nao uma cidade — subindo as cidades de dentro:")
        juntar(caminho(ano, estado), ano)
        log()
    return len(estados)


def limpar_soltos(cidade_caminho, cidade):
    """PDF largado direto na pasta da cidade, sem pasta de cliente.

    Se o mesmo arquivo (mesmo nome e mesmo tamanho) ja esta dentro da pasta
    de algum cliente daquela cidade, o solto e copia e sai. Se nao esta em
    lugar nenhum, fica onde esta e o programa avisa -- adivinhar de qual
    cliente ele e seria pior do que deixar voce olhar.
    """
    pastas, arquivos = listar(cidade_caminho)
    if not arquivos:
        return 0

    dentro = set()
    for cli in pastas:
        _, arqs = listar(caminho(cidade_caminho, cli["Name"]))
        dentro.update((a["Name"], a.get("Size")) for a in arqs)

    mexeu = 0
    for arq in arquivos:
        if (arq["Name"], arq.get("Size")) in dentro:
            log(f"  [{cidade}] solto na cidade, ja esta na pasta do cliente:")
            apagar_arquivo(caminho(cidade_caminho, arq["Name"]), "copia identica")
            mexeu += 1
        else:
            log(f"  [{cidade}] ! {arq['Name']} esta solto na cidade e nao achei "
                f"em nenhum cliente — deixei onde estava, confira.")
    return mexeu


# ── Principal ────────────────────────────────────────────────────────────────

def executar(ano):
    log("=" * 70)
    log(f"FAXINA DAS PASTAS DE {ano} NO GOOGLE DRIVE")
    log("MODO: APLICANDO DE VERDADE" if APLICAR else
        "MODO: SO MOSTRANDO (nada vai ser mexido)")
    log("=" * 70)
    log()

    pastas_antes, arquivos_antes = listar(ano)
    log(f"Hoje {ano} tem {len(pastas_antes)} pastas"
        + (f" e {len(arquivos_antes)} arquivos soltos" if arquivos_antes else "") + ".")
    log()

    log("1) Pastas com o nome IDENTICO (o Drive deixa ter duas iguais)")
    juntar_nomes_identicos(ano)
    log()

    log("2) Pastas de estado dentro do ano")
    if not dissolver_estados(ano):
        log("   nada a fazer.")
    log()

    log("3) Cidades repetidas")
    if not limpar_repetidas(ano, "cidade"):
        log("   nada a fazer.")
    log()

    log("4) Clientes repetidos dentro de cada cidade")
    cidades, _ = listar(ano)
    achou = 0
    for cidade in sorted(c["Name"] for c in cidades):
        achou += limpar_repetidas(caminho(ano, cidade), f"[{cidade}] cliente")
    if not achou:
        log("   nada a fazer.")
    log()

    log("5) PDF solto na pasta da cidade, sem pasta de cliente")
    soltos = 0
    for cidade in sorted(c["Name"] for c in cidades):
        soltos += limpar_soltos(caminho(ano, cidade), cidade)
    if not soltos:
        log("   nada a fazer.")
    log()

    log("=" * 70)
    log(f"Arquivos movidos ..... {feitos['movidos']}")
    log(f"Copias apagadas ...... {feitos['apagados']}")
    log(f"Pastas removidas ..... {feitos['pastas_removidas']}")
    if APLICAR:
        pastas_depois, _ = listar(ano)
        log(f"Cidades: {len(pastas_antes)} antes  ->  {len(pastas_depois)} depois")
    log("=" * 70)
    return feitos["movidos"] + feitos["apagados"] + feitos["pastas_removidas"]


def main(argv=None):
    global APLICAR
    args = list(argv if argv is not None else sys.argv[1:])
    ano = next((a for a in args if a.isdigit() and len(a) == 4), str(date.today().year))

    if not drive.configurado():
        log("O Google Drive ainda nao esta conectado nesta maquina.")
        log("Abra o monitor e responda 1 na pergunta do Drive.")
        return 1

    # Primeiro so mostra. Mexer no Drive de alguem sem ela ver antes o que vai
    # acontecer nao e uma boa ideia, ainda mais numa faxina.
    APLICAR = False
    if not executar(ano):
        log()
        log("Esta tudo organizado, nao achei nada para juntar nem para apagar.")
        return 0

    if "aplicar" in args:
        resposta = "1"
    else:
        log()
        log("Isso foi so a PREVIA — ate aqui nada foi mexido no Drive.")
        log("Digite 1 e ENTER para fazer de verdade, ou so ENTER para sair.")
        try:
            resposta = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            resposta = ""

    if resposta != "1":
        log("Saindo sem mexer em nada.")
        return 2   # nao quis agora: quem chamou pode oferecer de novo depois

    log()
    APLICAR = True
    for k in feitos:
        feitos[k] = 0
    executar(ano)
    log()
    log("Pronto. O que foi apagado esta na Lixeira do Drive e da para")
    log("recuperar por 30 dias, caso alguma coisa nao tenha ficado como voce queria.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
