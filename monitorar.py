#!/usr/bin/env python3
"""
EGEMAP - Monitor de Propostas
Janela de console que fica rodando em segundo plano monitorando a pasta.
"""

import sys
import time
import re
import os
import threading
import unicodedata
from pathlib import Path
from datetime import date

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "watchdog"])
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

try:
    import fitz
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pymupdf"])
    import fitz

# Integracao com o CRM (opcional -- o monitor funciona sem ela)
try:
    import crm as crm_egemap
except Exception:
    crm_egemap = None

# Integracao com o Google Drive (opcional -- o monitor funciona sem ela)
try:
    import drive as drive_egemap
except Exception:
    drive_egemap = None

# ── Config salva em arquivo texto simples ─────────────────────────────────────

CONFIG_FILE = Path.home() / ".egemap_monitor_config.txt"

def load_config():
    if CONFIG_FILE.exists():
        lines = CONFIG_FILE.read_text(encoding="utf-8").splitlines()
        if len(lines) >= 2:
            return lines[0].strip(), lines[1].strip()
    return "", ""

def save_config(capa, pasta):
    CONFIG_FILE.write_text(f"{capa}\n{pasta}\n", encoding="utf-8")

# ── Codigos de material no nome do arquivo ────────────────────────────────────
#
# PVC, ALM e MAD so valem como PALAVRA INTEIRA, e so no pedaco do nome que vem
# DEPOIS da data. Sem isso o nome do cliente entrava na conta: "Almeida" tem
# "ALM" dentro e "Madalena" tem "MAD". A proposta de um cliente desses era
# lida como madeira+aluminio, virava "peca esperando o COMPLETO" -- o card
# nunca andava, o arquivo nao subia pro Drive, e o COMPLETO seguinte ainda
# juntava o arquivo errado. O crm.py ja comparava por palavra inteira; aqui
# faltava.

CODIGOS_DE_MATERIAL = {"PVC", "ALM", "MAD"}

# "Proposta Comercial Maria Teresa Silva 24-08 BRANCO" -> "BRANCO"
_DATA_NO_NOME = re.compile(r"\b\d{2}-\d{2}\b")


def _sufixo_do_nome(pdf_path):
    """Pedaco do nome onde o codigo do material pode aparecer.

    Depois da data, quando o arquivo ja passou pela montagem ("Proposta
    Comercial <cliente> 26-08 MAD ALM") -- assim o nome do cliente fica de
    fora. Num orcamento cru, que ainda nao tem data, vale o nome todo.
    """
    stem = Path(pdf_path).stem
    m = _DATA_NO_NOME.search(stem)
    return stem[m.end():] if m else stem


def codigos_no_nome(pdf_path):
    """Codigos de material no nome do arquivo, comparados por palavra inteira."""
    palavras = re.split(r"[^0-9A-Za-zÀ-ÖØ-öø-ÿ]+", _sufixo_do_nome(pdf_path).upper())
    return {p for p in palavras if p in CODIGOS_DE_MATERIAL}


# ── Lógica de PDF ─────────────────────────────────────────────────────────────

def detect_pdf_type(pdf_path):
    """PVC (Sintegra) ou ALM (W-Vetro).

    Quem manda e o CONTEUDO; o nome do arquivo so decide quando o conteudo
    nao diz nada (orcamento digitalizado, por exemplo). Antes era o
    contrario, e numa pasta de cliente chamado "Almeida" TODO PDF era lido
    como aluminio -- inclusive o PVC do Sintegra, que entrava no lugar
    errado do COMPLETO.
    """
    try:
        doc = fitz.open(pdf_path)
        try:
            text = "".join(p.get_text() for p in doc)
        finally:
            doc.close()

        if "OAD-" in text or "TOTAL GERAL (R$)" in text or "Archicentro" in text:
            return "pvc"
        if "w.vetro" in text.lower() or "wvetro" in text.lower():
            return "alm"
        if "TOTAL:" in text and "EGEMAP" in text:
            return "alm"
    except Exception:
        pass

    codigos = codigos_no_nome(pdf_path)
    if "PVC" in codigos:
        return "pvc"
    if codigos & {"ALM", "MAD"}:
        return "alm"
    return None


def _mtime(path):
    try:
        return Path(path).stat().st_mtime
    except OSError:
        return 0.0


def dia_do_arquivo(pdf_path):
    """A que dia de trabalho o PDF pertence.

    A data escrita no nome (DD-MM) manda, porque ela nao muda quando o
    OneDrive mexe no arquivo para sincronizar. So quando nao ha data no nome
    (orcamento cru, recem-salvo) e que vale a data de gravacao.
    """
    m = _DATA_NO_NOME.search(Path(pdf_path).stem)
    if m:
        dia, mes = m.group(0).split("-")
        try:
            return date(date.today().year, int(mes), int(dia))
        except ValueError:
            return None
    ts = _mtime(pdf_path)
    return date.fromtimestamp(ts) if ts else None


def find_pdfs_in_folder(folder):
    """PDFs da pasta separados por tipo, do mais novo para o mais antigo.

    A ordem importa: quem monta o COMPLETO pega o primeiro de cada tipo, e
    antes vinha na ordem que o Windows entregava -- podia ser o de qualquer
    dia.
    """
    result = {"pvc": [], "alm": [], "other": []}
    for p in sorted(Path(folder).glob("*.pdf"), key=_mtime, reverse=True):
        tipo = detect_pdf_type(str(p))
        result[tipo if tipo in ("pvc", "alm") else "other"].append(str(p))
    return result


def extract_total_pvc(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = "".join(p.get_text() for p in doc)
        match = re.search(r"TOTAL GERAL \(R\$\)\s*([\d.,]+)", text)
        return match.group(1) if match else ""
    except Exception:
        return ""


def extract_total_alm(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = "".join(p.get_text() for p in doc)
        matches = re.findall(r"TOTAL:\s*([\d.,]+)", text)
        return matches[-1] if matches else ""
    except Exception:
        return ""


def parse_brl(value_str):
    cleaned = value_str.strip().replace("R$", "").replace(" ", "")
    return float(cleaned.replace(".", "").replace(",", "."))


def format_brl(value):
    s = f"{value:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def format_brl_investimento(value):
    """Formata o valor grande da pagina final (Proposta de Investimento),
    com centavos -- soma exata de PVC + ALM (ex: 121.125,19)."""
    return format_brl(value)


def output_path_do_dia(folder, name, client=""):
    """Caminho de saida da proposta. O nome ja inclui a data (DD-MM), entao
    se ja existe um arquivo com esse nome e porque a proposta deste cliente
    foi refeita hoje (ex: cliente pediu alteracao) -- substitui a versao
    anterior de hoje em vez de criar um "(1)" duplicado.

    Nao apaga a versao anterior aqui: quem grava (_salvar_pdf) troca o arquivo
    de uma vez so. Apagar antes abria duas brechas -- ficar sem proposta
    nenhuma se a gravacao falhasse, e a retentativa em segundo plano apagar
    depois justamente a proposta nova."""
    return str(Path(folder) / f"{name}.pdf")


def _salvar_pdf(doc, output_path, tentativas=6, espera=2):
    """Grava a proposta por cima da anterior sem depender do arquivo antigo
    estar livre na hora.

    A pasta de orcamentos fica no OneDrive, que trava o arquivo enquanto
    sincroniza. Gravar direto por cima falha com "Permission denied" e derruba
    a montagem inteira -- foi o que aconteceu ao refazer uma proposta ja
    enviada. Entao grava num temporario (fora do alcance do monitor, que so
    olha .pdf) e so no fim troca pelo definitivo, insistindo enquanto o
    OneDrive nao solta.
    """
    destino = Path(output_path)
    temporario = destino.with_name(destino.name + ".tmp")

    doc.save(str(temporario))
    doc.close()

    erro = None
    for tentativa in range(tentativas):
        try:
            os.replace(temporario, destino)
            return
        except OSError as e:
            erro = e
            if tentativa == 0:
                log(f"Arquivo anterior em uso, aguardando liberar: {destino.name}")
            time.sleep(espera)

    # Nao soltou: joga fora o temporario e deixa o erro subir. O orcamento
    # original nao e apagado, entao e so salvar de novo depois.
    try:
        temporario.unlink()
    except Exception:
        pass
    raise erro


def suggest_client_name(folder_path):
    return Path(folder_path).name or "Cliente"


def _color_tuple(c):
    """Converte cor int (0xRRGGBB) para tupla (r,g,b) 0-1."""
    if isinstance(c, int):
        return ((c >> 16 & 0xFF) / 255, (c >> 8 & 0xFF) / 255, (c & 0xFF) / 255)
    return c


CAMPOS_LABEL_VAZIO = ("EMAIL:", "TELEFONE:", "CELULAR:", "CEP:")


def limpar_campos_vazios_alm(doc, page_index=0):
    """Remove do cabecalho do W-Vetro os campos sem resposta (EMAIL/TELEFONE/
    CELULAR/CEP). So remove o que realmente esta vazio -- se o cliente
    preencheu o campo, ele permanece intocado."""
    if page_index >= len(doc):
        return
    page = doc[page_index]

    linhas = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            texto = "".join(s["text"] for s in line["spans"]).strip()
            if texto:
                linhas.append({"text": texto, "bbox": line["bbox"], "spans": line["spans"]})

    def _rect_encolhido(bbox):
        # O bbox de uma linha inclui folga de entrelinha que pode encostar na
        # linha vizinha (acima/abaixo); encolhe para nao redatar o vizinho.
        x0, y0, x1, y1 = bbox
        return fitz.Rect(x0, y0 + 2, x1, y1 - 1)

    to_redact = []
    to_insert = []  # (origin, texto, fontname, size, color)

    for linha in linhas:
        texto = linha["text"]
        x0, y0, x1, y1 = linha["bbox"]
        ymid = (y0 + y1) / 2

        if texto in CAMPOS_LABEL_VAZIO:
            # So remove se nao houver nenhum valor a direita, na mesma linha.
            # Outro rotulo (ex: "CELULAR:" do lado de "TELEFONE:") nao conta
            # como valor -- senao os dois nunca seriam removidos.
            tem_valor = any(
                o is not linha
                and o["text"] not in CAMPOS_LABEL_VAZIO
                and abs((o["bbox"][1] + o["bbox"][3]) / 2 - ymid) < 3
                and o["bbox"][0] >= x1 - 1
                for o in linhas
            )
            if not tem_valor:
                to_redact.append(_rect_encolhido(linha["bbox"]))
            continue

        # Linha "CEP: - CIDADE/UF -" ou "CEP: - CIDADE/UF - complemento" com
        # numero do CEP vazio (o rotulo "CEP:" vem embutido nesta linha de
        # novo, junto com a cidade/UF e as vezes um complemento de endereco).
        # O traco final e opcional -- nem sempre aparece.
        m = re.match(r"^CEP:\s*-\s*(.+?)\s*-?\s*$", texto)
        if m:
            to_redact.append(_rect_encolhido(linha["bbox"]))
            span = linha["spans"][0]
            fontname = "hebo" if "Bold" in span["font"] else "helv"
            to_insert.append((span["origin"], m.group(1), fontname, span["size"], _color_tuple(span["color"])))

    if not to_redact:
        return

    for r in to_redact:
        page.add_redact_annot(r, fill=(1, 1, 1))
    page.apply_redactions()

    for origin, texto, fontname, size, color in to_insert:
        page.insert_text(origin, texto, fontname=fontname, fontsize=size, color=color)


# ── Capa dinâmica (Capa 1 / Capa 2 / Página Final) ─────────────────────────────
#
# A Capa tem 3 páginas:
#   1. Capa 1  — "[nome do vendedor]", "[nome do cliente]", "[número do pedido]"
#   2. Capa 2  — institucional, sem nada dinâmico
#   3. Página final — "[NOME DO CLIENTE]" (dentro de uma frase) + "R$ 000.000"
#      (valor total do investimento = PVC + ALM somados)

#   - Capa 1 (vendedor/cliente/pedido) usa News Cycle (Bold)
#   - Página final (nome do cliente na frase + valor) usa DM Sans
_FONTES_BUNDLED = {
    "newscycle": "NewsCycle-Bold.ttf",
    "dmsans":    "DMSans-Regular.ttf",
}


def _caminho_fonte_bundled(chave):
    """Caminho da fonte (completa) que vem empacotada junto com o programa --
    funciona tanto rodando via "python monitorar.py" quanto no .exe gerado
    pelo PyInstaller (--add-data)."""
    nome_arquivo = _FONTES_BUNDLED.get(chave)
    if not nome_arquivo:
        return None
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    caminho = base / nome_arquivo
    return str(caminho) if caminho.exists() else None


_CAPA_FONT_CACHE: dict = {}

def _extrair_fonte_da_capa(capa_pdf_path, chave):
    """Fallback: extrai a fonte direto do PDF da capa. So usado se a fonte
    empacotada nao for encontrada -- a fonte dentro do PDF costuma vir
    "picotada" (so tem as letras que ja apareciam no texto original dos
    placeholders, faltando letras/numeros/simbolos necessarios pra inserir
    nomes e valores novos)."""
    cache_key = (str(capa_pdf_path), chave)
    if cache_key in _CAPA_FONT_CACHE:
        return _CAPA_FONT_CACHE[cache_key]
    result = None
    try:
        import tempfile
        doc = fitz.open(capa_pdf_path)
        paginas = {0, len(doc) - 1}
        for page_idx in paginas:
            if page_idx < 0 or page_idx >= len(doc):
                continue
            for finfo in doc[page_idx].get_fonts():
                xref, ext, _t, basename, _name, _enc = finfo[:6]
                nome_chave = basename.lower().replace(" ", "").replace("-", "")
                if chave in nome_chave:
                    data = doc.extract_font(xref)
                    if data and data[3]:
                        tmp = Path(tempfile.gettempdir()) / f"egemap_{chave}.{ext or 'ttf'}"
                        tmp.write_bytes(data[3])
                        result = str(tmp)
                        break
            if result:
                break
    except Exception:
        pass
    _CAPA_FONT_CACHE[cache_key] = result
    return result


def _get_capa_dinamica_font(capa_pdf_path, chave):
    """Fonte usada nos textos dinamicos da capa. Prioriza a fonte completa
    empacotada com o programa; so cai pro fallback (extrair do PDF, que pode
    vir com letras faltando) se ela nao existir."""
    return _caminho_fonte_bundled(chave) or _extrair_fonte_da_capa(capa_pdf_path, chave)


def _medir_texto(texto, fontfile, size):
    try:
        fonte = fitz.Font(fontfile=fontfile) if fontfile else fitz.Font("helv")
        return fonte.text_length(texto, fontsize=size)
    except Exception:
        return len(texto) * size * 0.5


def _inserir_texto(page, origem, texto, fontfile, size, color):
    if fontfile:
        # fontname precisa ser explicito: sem ele o PyMuPDF ignora o fontfile
        # e cai no Helvetica padrao (fontname="helv" e o default).
        alias = re.sub(r"[^A-Za-z0-9]+", "_", Path(fontfile).stem)
        page.insert_text(origem, texto, fontfile=fontfile, fontname=alias, fontsize=size, color=color)
    else:
        page.insert_text(origem, texto, fontname="helv", fontsize=size, color=color)


# ── Onde escrever na Capa ─────────────────────────────────────────────────────
#
# Os campos da Capa sao marcados entre colchetes. O jeito de escrever muda
# quando o layout e refeito: ja foi "[nome do vendedor]" e virou
# "[NOME DO VENDEDOR]", e o pedido virou so "[N°]". Como a busca era por texto
# exato, a Capa de setembro/2026 saiu com os tres campos em branco e ninguem
# ficou sabendo -- a proposta ia pro cliente com "[NOME DO CLIENTE]" escrito.
#
# Entao a comparacao ignora maiuscula, acento e pontuacao, e cada campo aceita
# varias grafias. Se um dia mudar de novo pra algo fora desta lista, o log
# avisa em vez de deixar passar em branco.

_MARCA = re.compile(r"^\[([^\]]+)\]$")
_MARCA_NA_LINHA = re.compile(r"\[[^\]]+\]")

MARCAS_VENDEDOR = {"nome do vendedor", "vendedor"}
MARCAS_CLIENTE = {"nome do cliente", "cliente"}
MARCAS_PEDIDO = {"numero do pedido", "n do pedido", "no do pedido",
                 "numero", "pedido", "n", "no"}


def _chave_marca(texto):
    """Chave de comparacao de um campo da Capa. None se nao for um campo.

    "[Número do Pedido]", "[NUMERO DO PEDIDO]" e "[numero do pedido]" dao a
    mesma chave. Exige os colchetes de proposito: sem eles, o rotulo
    "Vendedor" impresso na Capa seria confundido com o campo a preencher.
    """
    m = _MARCA.match((texto or "").strip())
    if not m:
        return None
    t = unicodedata.normalize("NFKD", m.group(1))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def _no_estilo_da_marca(marca, valor):
    """Escreve o valor do jeito que o campo estava escrito: se o campo esta
    todo em maiuscula ("[NOME DO CLIENTE]"), o nome tambem sai em maiuscula."""
    letras = [c for c in marca if c.isalpha()]
    return valor.upper() if letras and all(c.isupper() for c in letras) else valor


def _trocar_linha(page, line, texto_novo, fontfile):
    """Reescreve a linha inteira mantendo posicao, tamanho e cor originais."""
    span = line["spans"][0]
    ox, oy = span["origin"]
    size = span["size"]
    color = _color_tuple(span["color"])
    page.add_redact_annot(fitz.Rect(line["bbox"]), fill=(1, 1, 1))
    page.apply_redactions()
    _inserir_texto(page, (ox, oy), texto_novo, fontfile, size, color)


def _linhas(page):
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            yield line, "".join(s["text"] for s in line["spans"])


def _substituir_linha_inteira(page, texto_antigo, texto_novo, fontfile):
    """Troca uma linha que e SO o campo (ex.: "[NOME DO VENDEDOR]",
    "R$ 000.000") pelo valor.

    texto_antigo pode ser o texto exato (usado no "R$ 000.000") ou um
    conjunto de chaves de campo aceitas (MARCAS_VENDEDOR e companhia).
    """
    for line, bruto in _linhas(page):
        t = bruto.strip()
        if isinstance(texto_antigo, (set, frozenset)):
            if _chave_marca(t) not in texto_antigo:
                continue
            valor = _no_estilo_da_marca(t, texto_novo)
        else:
            if t != texto_antigo:
                continue
            valor = texto_novo
        _trocar_linha(page, line, valor, fontfile)
        return True
    return False


def _substituir_dentro_da_linha(page, chaves, texto_novo, fontfile):
    """Troca so o campo dentro de uma linha maior (ex.: "[NOME DO CLIENTE], é
    uma honra fazer parte do seu projeto."), mantendo o resto da frase."""
    for line, bruto in _linhas(page):
        for achado in _MARCA_NA_LINHA.finditer(bruto):
            if _chave_marca(achado.group(0)) not in chaves:
                continue
            valor = _no_estilo_da_marca(achado.group(0), texto_novo)
            _trocar_linha(page, line,
                          bruto[:achado.start()] + valor + bruto[achado.end():],
                          fontfile)
            return True
    return False


def montar_paginas_capa(capa_pdf_path, vendedor, cliente, pedido, total_str):
    """Monta a Capa completa (3 paginas) com os dados do cliente:
    Capa 1 (vendedor/cliente/pedido) e a pagina final (cliente + valor do
    investimento) editadas; Capa 2 (institucional) fica intocada. Retorna um
    doc de 3 paginas -- as paginas 0-1 vao no inicio da proposta final e a
    pagina 2 vai no fim."""
    fonte_capa1 = _get_capa_dinamica_font(capa_pdf_path, "newscycle")
    fonte_final = _get_capa_dinamica_font(capa_pdf_path, "dmsans")
    doc = fitz.open()
    doc.insert_pdf(fitz.open(capa_pdf_path))

    p1 = doc[0]
    pf = doc[len(doc) - 1]

    # (o que e, onde procurar, como procurar, valor). Campo sem valor fica
    # como esta na Capa -- escrever por cima com o proprio placeholder so
    # trocaria o estilo dele.
    campos = [
        ("vendedor na Capa", p1, MARCAS_VENDEDOR, vendedor, _substituir_linha_inteira),
        ("cliente na Capa", p1, MARCAS_CLIENTE, cliente, _substituir_linha_inteira),
        ("numero do pedido na Capa", p1, MARCAS_PEDIDO, pedido, _substituir_linha_inteira),
        ("cliente na Pagina Final", pf, MARCAS_CLIENTE, cliente, _substituir_dentro_da_linha),
        ("valor na Pagina Final", pf, "R$ 000.000", total_str and f"R$ {total_str}",
         _substituir_linha_inteira),
    ]
    for o_que, pagina, marca, valor, substituir in campos:
        if not valor:
            log(f"AVISO: sem {o_que} para preencher (o orcamento nao trouxe esse dado).")
            continue
        if not substituir(pagina, marca, valor, fonte_capa1 if pagina is p1 else fonte_final):
            log(f"AVISO: nao achei onde escrever o {o_que} — a Capa "
                f"'{Path(capa_pdf_path).name}' deve ter mudado o nome do campo. "
                f"A proposta sai com o campo em branco.")

    return doc


def _valor_ao_lado(page, label_exato):
    """Acha o texto que esta na mesma linha, a direita, de um rotulo exato
    (ex: "VENDEDOR:", "CLIENTE:"). Usado pra extrair dados do cabecalho do
    W-Vetro (segundo bloco de cabecalho, o dos dados do cliente)."""
    linhas = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            t = "".join(s["text"] for s in line["spans"]).strip()
            if t:
                linhas.append({"text": t, "bbox": line["bbox"]})
    alvo = next((l for l in linhas if l["text"] == label_exato), None)
    if not alvo:
        return ""
    x0, y0, x1, y1 = alvo["bbox"]
    ymid = (y0 + y1) / 2
    candidatos = [
        l for l in linhas
        if l is not alvo
        and l["bbox"][0] >= x1 - 1
        and abs((l["bbox"][1] + l["bbox"][3]) / 2 - ymid) < 4
    ]
    if not candidatos:
        return ""
    candidatos.sort(key=lambda l: l["bbox"][0])
    return candidatos[0]["text"]


def extrair_vendedor_alm(alm_doc, page_index):
    """VENDEDOR: no primeiro bloco de cabecalho do W-Vetro."""
    try:
        return _valor_ao_lado(alm_doc[page_index], "VENDEDOR:")
    except Exception:
        return ""


def extrair_cliente_alm(alm_doc, page_index):
    """CLIENTE: no segundo bloco de cabecalho do W-Vetro."""
    try:
        return _valor_ao_lado(alm_doc[page_index], "CLIENTE:")
    except Exception:
        return ""


def extrair_pedido_alm(alm_doc, page_index):
    """Numero do orcamento do W-Vetro (ex: "ORÇAMENTO: 2335") vira o Numero
    do Pedido na capa."""
    try:
        text = alm_doc[page_index].get_text()
        # cuidado: "DATA DO ORÇAMENTO:" tambem contem "ORÇAMENTO:" -- exige
        # que o valor capturado seja numerico pra nao pegar esse rotulo errado
        m = re.search(r"OR[ÇC]AMENTO:\s*(\d+)", text, re.IGNORECASE)
        return m.group(1) if m else ""
    except Exception:
        return ""


def extrair_pedido_pvc(pvc_doc, start_page, end_page):
    """Codigo do orcamento do sistema de PVC (ex: "OAD-2506015-00") vira o
    Numero do Pedido na capa quando nao tem W-Vetro no orcamento."""
    try:
        text = "".join(pvc_doc[i].get_text() for i in range(start_page, min(end_page, len(pvc_doc) - 1) + 1))
        m = re.search(r"OAD-[\d-]+", text)
        return m.group(0) if m else ""
    except Exception:
        return ""


PALAVRAS_RESERVADAS_NOME_ARQUIVO = {"COMPLETO", "PVC", "MAD", "ALM", "PROPOSTA", "COMERCIAL"}


def extrair_vendedor_do_nome_arquivo(pdf_path):
    """PVC sozinho nao vem com VENDEDOR: no PDF -- o usuario digita o nome
    do vendedor como a ULTIMA palavra do nome do arquivo ao salvar (ex:
    "orcamento cliente completo JACKSON.pdf")."""
    stem = Path(pdf_path).stem
    palavras = [p for p in re.split(r"[ _]+", stem) if p]
    if not palavras:
        return ""
    ultima = palavras[-1]
    if ultima.upper() in PALAVRAS_RESERVADAS_NOME_ARQUIVO:
        return ""
    if not re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", ultima):
        return ""
    return ultima


def detect_alm_subtipo(pdf_path):
    """Se o W-Vetro veio como aluminio, madeira, ou os dois.

    Compara palavra inteira: "orcamento Almeida MAD.pdf" e madeira, e nao
    madeira+aluminio -- antes o "ALM" de "Almeida" contava, o arquivo saia
    marcado "MAD ALM" e virava peca esperando um COMPLETO que nunca vinha.

    Quando o nome vem colado, sem separador nenhum ("orcamentoALM.pdf"),
    ainda vale o codigo que estiver bem no FIM do nome -- e onde voce escreve.
    Procurar em qualquer lugar da palavra e que nao da: "Palmeira" viraria
    aluminio e "Amadeu" viraria madeira.
    """
    codigos = codigos_no_nome(pdf_path)
    if not codigos:
        fim = re.sub(r"[^A-Z]", "", _sufixo_do_nome(pdf_path).upper())
        if fim.endswith("MADALM") or fim.endswith("ALMMAD"):
            codigos = {"MAD", "ALM"}
        else:
            codigos = {c for c in CODIGOS_DE_MATERIAL if fim.endswith(c)}
    has_alm = "ALM" in codigos
    has_mad = "MAD" in codigos
    if has_alm and has_mad:
        return "alm_mad"
    if has_alm:
        return "alm"
    if has_mad:
        return "mad"
    return "alm_mad"


def _has_system_capa(doc):
    if len(doc) == 0:
        return False
    return "PROPOSTA" in doc[0].get_text().upper()


def _saida_valida(output_path, minimo_paginas):
    """Confere se a proposta final saiu com um numero razoavel de paginas
    antes de apagar os originais -- protege contra perder o orcamento do
    cliente se algo der errado na montagem."""
    try:
        doc = fitz.open(output_path)
        n = len(doc)
        doc.close()
        return n >= minimo_paginas
    except Exception:
        return False


def _content_range(doc):
    """Paginas de conteudo de um PDF ja envolvido por este programa (pula as
    2 paginas de Capa no inicio e a Pagina Final no fim)."""
    n = len(doc)
    if n > 3:
        start = 2
    elif n > 1:
        start = 1
    else:
        start = 0
    end = n - 2 if n > 2 else max(n - 1, 0)
    return start, end


def _alm_range(alm_doc, alm_pdf_path):
    """Paginas de conteudo W-Vetro: todas se original, sem capa/pagina final se ja e wrap."""
    if _is_proposta_gerada(alm_pdf_path):
        return _content_range(alm_doc)
    return 0, len(alm_doc) - 1


def merge_pvc(capa_pdf_path, pvc_pdf_path, alm_pdf_path, pvc_total, alm_total, output_path,
              vendedor="", cliente="", pedido=""):
    pvc_doc = fitz.open(pvc_pdf_path)
    alm_doc = fitz.open(alm_pdf_path)
    total = parse_brl(pvc_total) + parse_brl(alm_total)
    capa_editada = montar_paginas_capa(capa_pdf_path, vendedor, cliente, pedido, format_brl_investimento(total))

    result = fitz.open()
    result.insert_pdf(capa_editada, from_page=0, to_page=1)  # Capa 1 + Capa 2

    if _is_proposta_gerada(pvc_pdf_path):
        # Wrap nosso: pula nossas 2 paginas de Capa e a Pagina Final
        pvc_start = 2
        pvc_end   = len(pvc_doc) - 2
    else:
        # PDF original do Sintegra: pula capa do sistema se houver
        pvc_start = 1 if _has_system_capa(pvc_doc) else 0
        pvc_end   = len(pvc_doc) - 1
    if pvc_start <= pvc_end:
        result.insert_pdf(pvc_doc, from_page=pvc_start, to_page=pvc_end)

    alm_start, alm_end = _alm_range(alm_doc, alm_pdf_path)
    if not _is_proposta_gerada(alm_pdf_path):
        limpar_campos_vazios_alm(alm_doc, alm_start)
    if alm_start <= alm_end:
        result.insert_pdf(alm_doc, from_page=alm_start, to_page=alm_end)

    result.insert_pdf(capa_editada, from_page=2, to_page=2)  # Pagina Final
    _salvar_pdf(result, output_path)


def merge_alm(capa_pdf_path, alm_pdf_path, output_path, vendedor="", cliente="", pedido="", alm_total=""):
    alm_doc = fitz.open(alm_pdf_path)
    total = parse_brl(alm_total) if alm_total else 0.0
    capa_editada = montar_paginas_capa(capa_pdf_path, vendedor, cliente, pedido, format_brl_investimento(total))

    result = fitz.open()
    result.insert_pdf(capa_editada, from_page=0, to_page=1)

    alm_start, alm_end = _alm_range(alm_doc, alm_pdf_path)
    if not _is_proposta_gerada(alm_pdf_path):
        limpar_campos_vazios_alm(alm_doc, alm_start)
    if alm_start <= alm_end:
        result.insert_pdf(alm_doc, from_page=alm_start, to_page=alm_end)

    result.insert_pdf(capa_editada, from_page=2, to_page=2)
    _salvar_pdf(result, output_path)

# ── Watchdog handler ──────────────────────────────────────────────────────────

WAIT_SECONDS = 8  # espera 8s apos o ultimo evento para garantir que o PDF foi salvo
# Teto para o COMPLETO esperar um orcamento cru da mesma pasta ser envolvido.
ESPERA_MAXIMA_COMPLETO = 120
# Espera maior antes de mandar a proposta ao CRM: da tempo de voce renomear o
# arquivo pronto antes, e o nome do arquivo e que vira o nome da linha no CRM.
CRM_WAIT_SECONDS = 10
# Mesma espera antes de mandar a proposta para o Drive -- da tempo de voce
# renomear o arquivo antes, e o nome vira o nome do arquivo la tambem.
DRIVE_WAIT_SECONDS = 10

def log(msg):
    hora = time.strftime("%H:%M:%S")
    print(f"[{hora}] {msg}", flush=True)


# ── CRM ───────────────────────────────────────────────────────────────────────

def _valor(total_str):
    """Converte o total lido do PDF em numero. 0.0 se nao veio nada."""
    try:
        return parse_brl(total_str) if total_str else 0.0
    except Exception:
        return 0.0


def _palavras(texto):
    return set(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{4,}", (texto or "").upper()))


def proposta_tem_capa(pdf_path, capa_pdf_path):
    """Confere se o PDF e mesmo uma proposta montada, com Capa e Pagina Final.

    So proposta completa pode ir para o CRM. Compara o texto da primeira e da
    ultima pagina com o da Capa configurada -- orcamento cru do Sintegra ou do
    W-Vetro nao tem esse texto e e barrado.
    """
    try:
        proposta = fitz.open(pdf_path)
        capa = fitz.open(capa_pdf_path)
    except Exception:
        return False

    try:
        if len(proposta) < 4 or len(capa) < 3:
            return False

        def parecido(pagina, referencia):
            a, b = _palavras(pagina.get_text()), _palavras(referencia.get_text())
            if len(b) < 3:
                # Capa desenhada em imagem, quase sem texto legivel: da pra
                # comparar so o formato da pagina. Melhor isso do que barrar
                # todas as propostas por nao conseguir conferir o texto.
                return (round(pagina.rect.width), round(pagina.rect.height)) == \
                       (round(referencia.rect.width), round(referencia.rect.height))
            # Ignora os campos que a montagem preenche (vendedor, cliente,
            # pedido, valor): compara so o texto fixo da capa.
            return len(a & b) >= max(3, int(len(b) * 0.5))

        return (parecido(proposta[0], capa[0])
                and parecido(proposta[len(proposta) - 1], capa[2]))
    except Exception:
        return False
    finally:
        proposta.close()
        capa.close()


def nome_da_linha(pdf_path, materiais=None):
    """Nome que a proposta vai ter na lista de orcamentos do CRM.

    Vem do que estiver depois da data no nome do arquivo, entao renomear a
    proposta renomeia a linha -- e assim que duas opcoes do mesmo material
    (ex.: BRANCO e CINZA) viram duas linhas separadas.

    Enquanto o nome so tiver os codigos que a montagem usa (PVC/ALM/MAD), ou
    nem isso, vale o nome bonito do material ("Madeira + Aluminio").
    """
    stem = Path(pdf_path).stem
    m = _DATA_NO_NOME.search(stem)
    sufixo = stem[m.end():].strip(" -_") if m else ""
    palavras = sufixo.split()

    so_codigo = not palavras or all(p.upper() in CODIGOS_DE_MATERIAL for p in palavras)
    if so_codigo and materiais and crm_egemap is not None:
        return crm_egemap.nome_do_orcamento(materiais)

    if not palavras:
        return "Orcamento"
    return " ".join(p.capitalize() for p in palavras)


def valor_da_proposta(pdf_path):
    """Le o total na Pagina Final da proposta ("R$ 162.717,22").

    E o mesmo numero que a montagem escreveu ali, entao vale tanto para uma
    proposta individual quanto para o COMPLETO (que ja soma PVC + ALM).
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return 0.0
    try:
        if not len(doc):
            return 0.0
        texto = doc[len(doc) - 1].get_text()
        valores = re.findall(r"R\$\s*([\d.]+,\d{2}|[\d.]+)", texto)
        return max((_valor(v) for v in valores), default=0.0)
    except Exception:
        return 0.0
    finally:
        doc.close()


def materiais_do_nome_do_arquivo(pdf_path):
    """Materiais pelos codigos que a montagem usa no nome (PVC/ALM/MAD).

    Vazio quando o arquivo foi renomeado para algo como "... 24-08 BRANCO".
    """
    codigos = codigos_no_nome(pdf_path)
    return {m for c, m in (("PVC", "pvc"), ("ALM", "aluminio"), ("MAD", "madeira"))
            if c in codigos}


def e_peca_de_completo(pdf_path):
    """Diz se a proposta e so uma peca, esperando ser juntada num COMPLETO.

    O sinal e ter mais de um material no nome. "MAD ALM" sai do W-Vetro para
    ser juntado com o PVC; ja "ALM", "MAD" ou "PVC" sozinho e obra so daquele
    material e a proposta esta pronta.

    Peca nao vai para o CRM nem para o Drive: ela nao e a proposta do
    cliente, e so ficava guardada no card sem servir pra nada. Quem vai e a
    proposta final, quando o COMPLETO ficar pronto.
    """
    return len(materiais_do_nome_do_arquivo(pdf_path)) >= 2


def materiais_da_proposta(pdf_path):
    """Quais materiais a proposta cobre.

    So faz diferenca quando o negocio tem mais de um orcamento cadastrado no
    CRM, pra saber qual deles acabou de sair. Numa proposta renomeada (ex.:
    "... 24-08 BRANCO") o nome nao diz nada, entao olha o conteudo.
    """
    materiais = materiais_do_nome_do_arquivo(pdf_path)
    if materiais:
        return materiais

    try:
        doc = fitz.open(pdf_path)
        texto = "".join(p.get_text() for p in doc)
        doc.close()
    except Exception:
        return materiais

    if "OAD-" in texto or "TOTAL GERAL (R$)" in texto or "Archicentro" in texto:
        materiais.add("pvc")
    if "w.vetro" in texto.lower() or "wvetro" in texto.lower():
        materiais.add("aluminio")
    return materiais


# Proposta ja mandada ao CRM: caminho -> (mtime, tamanho)
_JA_ENVIADO = {}
# Proposta ja mandada ao Drive: caminho -> (mtime, tamanho)
_JA_ENVIADO_DRIVE = {}


def _lancar_no_crm(pdf_path, capa_pdf, origem_antiga=None):
    """Manda a proposta pronta para o CRM, sem travar o monitor.

    Roda em segundo plano: se a internet cair ou o CRM demorar, o monitor
    continua montando as proximas propostas normalmente.

    origem_antiga vem preenchido quando a proposta acabou de ser renomeada --
    ai a linha no CRM e renomeada junto, em vez de virar uma linha nova. O
    nome antigo e calculado aqui, com os mesmos materiais, senao "MAD ALM"
    viraria "Mad Alm" na busca e "Madeira + Aluminio" na criacao.
    """
    if crm_egemap is None or not crm_egemap.configurado():
        return

    arquivo = Path(pdf_path).name
    client = suggest_client_name(Path(pdf_path).parent)

    # O OneDrive mexe nos arquivos ao sincronizar e isso dispara evento sem
    # nada ter mudado. Se e o mesmo arquivo de antes, nao reenvia.
    try:
        st = Path(pdf_path).stat()
        assinatura = (st.st_mtime_ns, st.st_size)
    except OSError:
        return
    chave = _norm(pdf_path)
    if origem_antiga is None and _JA_ENVIADO.get(chave) == assinatura:
        return

    # Peca esperando o COMPLETO (ex.: "MAD ALM") nao entra no CRM. Ela nao e
    # a proposta do cliente: ficava anexada no card atoa e depois tinha que
    # ser limpa na mao. Quem entra e a proposta final, quando o COMPLETO
    # ficar pronto. Marca como "ja visto" so pra nao repetir o aviso a cada
    # vez que o OneDrive toca no arquivo.
    if e_peca_de_completo(pdf_path):
        _JA_ENVIADO[chave] = assinatura
        log(f"[{client}] CRM: {arquivo} e peca para juntar no COMPLETO — nao enviei.")
        return

    # So proposta completa vai para o CRM: nunca um orcamento cru, sem capa.
    if not proposta_tem_capa(pdf_path, capa_pdf):
        log(f"[{client}] CRM: {arquivo} nao esta com Capa e Pagina Final — nao enviei.")
        return

    valor = valor_da_proposta(pdf_path)
    if valor <= 0:
        log(f"[{client}] CRM: nao lancei — nao achei o valor na Pagina Final de {arquivo}.")
        return

    _JA_ENVIADO[chave] = assinatura
    materiais = materiais_da_proposta(pdf_path)

    # O nome antigo tem que ser calculado como ele foi criado. Os codigos
    # ficam no nome do arquivo antigo ("MAD ALM"), e nao no conteudo, entao
    # e de la que eles saem -- senao a busca erraria a linha e duplicaria.
    nome_antigo = None
    if origem_antiga:
        nome_antigo = nome_da_linha(
            origem_antiga, materiais_do_nome_do_arquivo(origem_antiga) or materiais)

    threading.Thread(
        target=crm_egemap.lancar_proposta,
        args=(pdf_path, client, valor, materiais),
        kwargs={"log": log,
                "nome_linha": nome_da_linha(pdf_path, materiais),
                "nome_antigo": nome_antigo,
                "parcial": e_peca_de_completo(pdf_path)},
        daemon=True,
    ).start()


# ── Google Drive ─────────────────────────────────────────────────────────────

# "de", "da", "dos"... ficam minusculos, como se escreve em portugues.
# Sem isso "Passo de Torres" virava "Passo De Torres" -- e como pro Google
# Drive isso e outra pasta, o monitor criava uma nova ao lado da que voce ja
# usava ha meses, e a proposta sumia da vista. Quem garante mesmo que a pasta
# certa vai ser reaproveitada e o drive.py, que procura antes de criar; isto
# aqui so serve pra pasta nova nascer com o nome escrito direito.
LIGACOES_MINUSCULAS = {"de", "da", "do", "das", "dos", "e", "di", "du", "del", "y"}


_E_UF = re.compile(r"[A-Za-z]{2}")


def _nome_canonico_cliente(nome):
    """Arruma maiusculas/minusculas do nome ("felipe DOS santos coelho" vira
    "Felipe dos Santos Coelho")."""
    palavras = nome.split()
    if not palavras:
        return "Cliente"
    return " ".join(
        p.capitalize() if i == 0 or p.lower() not in LIGACOES_MINUSCULAS else p.lower()
        for i, p in enumerate(palavras)
    )


def _destino_drive(pdf_path, pasta_raiz=""):
    """Ano/Cidade/Cliente na raiz do Drive.

    O ano vem da data de hoje (nunca muda de fonte). Cidade e Cliente vem
    da pasta local (pasta_raiz/Cidade/Cliente/arquivo.pdf) -- confiavel
    porque so um computador roda o monitor, entao nao tem mais o
    problema de cada vendedor organizar a pasta raiz de um jeito
    diferente (o motivo de antes ter dado pasta duplicada).

    Se o PDF estiver direto na pasta raiz (sem nivel de cidade), cai em
    Ano/Cliente, sem inventar uma "cidade" errada.
    """
    ano = str(date.today().year)
    pasta_cliente = Path(pdf_path).parent
    cliente = _nome_canonico_cliente(suggest_client_name(pasta_cliente))

    pasta_cidade = pasta_cliente.parent
    tem_cidade = bool(pasta_cidade.name)
    if pasta_raiz:
        try:
            tem_cidade = pasta_cidade.resolve() != Path(pasta_raiz).resolve()
        except OSError:
            pass

    # Proposta salva direto na pasta da cidade, sem pasta de cliente: a pasta
    # "de cima" e o estado (SC, RS), nao uma cidade. Mandar assim criava uma
    # cidade fantasma chamada "SC" no Drive. Manda pra propria cidade.
    if tem_cidade and _E_UF.fullmatch(pasta_cidade.name.strip()):
        return f"{ano}/{cliente}"

    if tem_cidade:
        cidade = _nome_canonico_cliente(pasta_cidade.name)
        return f"{ano}/{cidade}/{cliente}"
    return f"{ano}/{cliente}"


def _lancar_no_drive(pdf_path, capa_pdf, pasta_raiz=""):
    """Manda a proposta pronta para o Drive, sem travar o monitor.

    Mesmas regras de seguranca do CRM: nunca um orcamento cru, e uma peca
    isolada esperando o COMPLETO (ex.: "MAD ALM") nao sobe sozinha -- sobe
    a proposta final, quando ela ficar pronta.
    """
    if drive_egemap is None or not drive_egemap.configurado():
        return
    if e_peca_de_completo(pdf_path):
        return

    try:
        st = Path(pdf_path).stat()
        assinatura = (st.st_mtime_ns, st.st_size)
    except OSError:
        return
    chave = _norm(pdf_path)
    if _JA_ENVIADO_DRIVE.get(chave) == assinatura:
        return

    if not proposta_tem_capa(pdf_path, capa_pdf):
        return  # mesma regra do CRM: so proposta pronta, nunca orcamento cru

    _JA_ENVIADO_DRIVE[chave] = assinatura
    client = suggest_client_name(Path(pdf_path).parent)
    destino = _destino_drive(pdf_path, pasta_raiz)
    materiais = materiais_do_nome_do_arquivo(pdf_path)

    threading.Thread(
        target=drive_egemap.enviar,
        args=(pdf_path, destino, materiais),
        kwargs={"client": client, "log": log},
        daemon=True,
    ).start()


# Arquivos que nao conseguimos apagar de cara ficam aqui, e o tick() do
# monitor vai tentando de novo em segundo plano (sem travar o programa) por
# alguns minutos -- cobre o caso do OneDrive segurar o arquivo travado por
# muito tempo sincronizando com a nuvem.
_PENDING_DELETE: dict = {}   # path_norm -> (primeira_tentativa, caminho, client)
_PENDING_DELETE_TIMEOUT = 300  # desiste depois de ~5 minutos tentando


def _apagar(path, client=""):
    # Tenta rapido algumas vezes (pode ser so um instante de gravacao ainda
    # nao liberada). Se nao conseguir, agenda pra tentar de novo em segundo
    # plano em vez de travar o programa esperando.
    for tentativa in range(3):
        try:
            Path(path).unlink()
            log(f"[{client}] Removido original: {Path(path).name}")
            return
        except FileNotFoundError:
            return  # ja saiu da pasta (movido, ou o OneDrive levou): nada a fazer
        except Exception:
            if tentativa < 2:
                time.sleep(1)

    chave = _norm(path)
    if chave not in _PENDING_DELETE:
        log(f"[{client}] {Path(path).name} ainda em uso — vou continuar tentando apagar em segundo plano (pode ser sincronizacao do OneDrive)...")
    _PENDING_DELETE[chave] = (time.time(), path, client)


def _processar_pendentes_apagar():
    """Chamado a cada tick(): tenta de novo apagar os arquivos que ficaram
    presos, sem travar o resto do monitor."""
    agora = time.time()
    for chave in list(_PENDING_DELETE.keys()):
        inicio, path, client = _PENDING_DELETE[chave]
        try:
            Path(path).unlink()
            log(f"[{client}] Removido original (apos aguardar liberacao do arquivo): {Path(path).name}")
            del _PENDING_DELETE[chave]
        except FileNotFoundError:
            del _PENDING_DELETE[chave]  # sumiu sozinho, missao cumprida
        except Exception as e:
            if agora - inicio > _PENDING_DELETE_TIMEOUT:
                log(f"[{client}] Nao foi possivel remover {Path(path).name} apos varios minutos (pode estar sincronizando no OneDrive) — apague manualmente: {e}")
                del _PENDING_DELETE[chave]


def _norm(path):
    return str(Path(path).resolve()).upper()


def _is_proposta_gerada(path):
    """Ignora PDFs que já foram gerados por este programa."""
    return Path(path).stem.startswith("Proposta Comercial")


def _is_proposta_final(path):
    """Proposta final completa (sem sufixo PVC/ALM/MAD) — nao usar como fonte no COMPLETO."""
    stem = Path(path).stem
    if not stem.startswith("Proposta Comercial"):
        return False
    # Verifica as ultimas palavras: cobre "... PVC", "... PVC NOME" (vendedor
    # digitado no arquivo) e "... MAD ALM" (wrap individual do W-Vetro)
    palavras = stem.upper().split()
    if any(p in ("PVC", "ALM", "MAD") for p in palavras[-3:]):
        return False
    return True


def merge_individual(capa_pdf_path, src_pdf_path, output_path,
                      vendedor="", cliente="", pedido="", total_str=""):
    """Envolve um unico PDF (PVC ou ALM) com Capa 1 + Capa 2 + conteudo + Pagina Final."""
    src_doc = fitz.open(src_pdf_path)
    total = parse_brl(total_str) if total_str else 0.0
    capa_editada = montar_paginas_capa(capa_pdf_path, vendedor, cliente, pedido, format_brl_investimento(total))

    result = fitz.open()
    result.insert_pdf(capa_editada, from_page=0, to_page=1)

    tipo = detect_pdf_type(src_pdf_path)
    if tipo == "pvc":
        start = 1 if _has_system_capa(src_doc) else 0
        if start < len(src_doc):
            result.insert_pdf(src_doc, from_page=start)
    else:
        start, end = _alm_range(src_doc, src_pdf_path)
        if not _is_proposta_gerada(src_pdf_path):
            limpar_campos_vazios_alm(src_doc, start)
        if start <= end:
            result.insert_pdf(src_doc, from_page=start, to_page=end)

    result.insert_pdf(capa_editada, from_page=2, to_page=2)
    _salvar_pdf(result, output_path)


class PropostaHandler(FileSystemEventHandler):
    def __init__(self, capa_pdf, pasta_raiz=""):
        self.capa_pdf = capa_pdf
        self.pasta_raiz = pasta_raiz
        self._pending_single   = {}  # pdf_norm   -> (timestamp, caminho)
        self._pending_completo = {}  # folder_norm -> (timestamp, pasta, trigger)
        self._pending_crm      = {}  # pdf_norm   -> (timestamp, caminho, nome_antigo)
        self._pending_drive    = {}  # pdf_norm   -> (timestamp, caminho)

    def _fila_crm(self, path, origem_antiga=None):
        """Proposta pronta na pasta -- vai para o CRM.

        Serve tanto para a que o monitor acabou de montar (que ja sai com o
        nome certo) quanto para uma que voce renomeou depois. Renomear e
        opcional: o que vale e o nome que o arquivo tiver na hora do envio.
        """
        chave = _norm(path)
        anterior = self._pending_crm.get(chave)
        # Se ja estava na fila por um rename, preserva de onde ela veio
        if anterior and anterior[2] and not origem_antiga:
            origem_antiga = anterior[2]
        self._pending_crm[chave] = (time.time(), str(path), origem_antiga)

    def _fila_drive(self, path):
        self._pending_drive[_norm(path)] = (time.time(), str(path))

    def _queue(self, path):
        p = Path(path)
        if p.suffix.lower() != ".pdf":
            return
        if _is_proposta_gerada(str(p)):
            self._fila_crm(str(p))    # nao remonta, mas mantem o CRM em dia
            self._fila_drive(str(p))  # e o Drive tambem
            return

        stem_upper = p.stem.upper()

        # Ja processamos esse arquivo com sucesso e so estamos esperando o
        # OneDrive soltar pra apagar (fila em segundo plano). Se ele disparar
        # outro evento nesse meio tempo (o proprio OneDrive costuma tocar o
        # arquivo de novo ao terminar de sincronizar), NAO remonta de novo --
        # senao a mesma proposta e refeita repetidas vezes até o arquivo
        # finalmente sumir.
        if _norm(str(p)) in _PENDING_DELETE:
            return

        if "COMPLETO" in stem_upper:
            folder_norm = _norm(p.parent)
            self._pending_completo[folder_norm] = (time.time(), str(p.parent), str(p))
        else:
            tipo = detect_pdf_type(str(p))
            if tipo in ("pvc", "alm"):
                self._pending_single[_norm(str(p))] = (time.time(), str(p))

    def on_created(self, event):
        if not event.is_directory:
            self._queue(event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        origem, destino = Path(event.src_path), Path(event.dest_path)

        # Renomeou a proposta pronta (ex.: "... 24-08 PVC" -> "... 24-08 BRANCO"):
        # a linha no CRM muda de nome junto, em vez de duplicar.
        if (origem.suffix.lower() == ".pdf" and destino.suffix.lower() == ".pdf"
                and _is_proposta_gerada(str(origem)) and _is_proposta_gerada(str(destino))
                and _norm(origem.parent) == _norm(destino.parent)
                and origem.name != destino.name):
            self._fila_crm(str(destino), origem_antiga=str(origem))
            self._fila_drive(str(destino))
            return

        self._queue(event.dest_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._queue(event.src_path)

    def tick(self):
        import traceback
        now = time.time()

        # Retentativa em segundo plano de arquivos que ficaram presos ao apagar
        try:
            _processar_pendentes_apagar()
        except Exception as e:
            log(f"ERRO ao tentar apagar pendentes: {e}")

        # PDFs individuais: envolve com Capa + Pagina Final (6s de espera)
        prontos = [k for k, (t, _) in list(self._pending_single.items()) if now - t >= 6]
        for key in prontos:
            _, src_path = self._pending_single.pop(key)
            try:
                self._wrap_individual(src_path)
            except Exception as e:
                log(f"ERRO ao envolver {src_path}: {e}")
                log(traceback.format_exc())

        # Propostas prontas na pasta: vao para o CRM (10s, tempo de voce
        # terminar de renomear antes de sair lancando)
        prontos = [k for k, (t, _, __) in list(self._pending_crm.items()) if now - t >= CRM_WAIT_SECONDS]
        for key in prontos:
            _, pdf_path, origem_antiga = self._pending_crm.pop(key)
            try:
                if Path(pdf_path).exists():
                    _lancar_no_crm(pdf_path, self.capa_pdf, origem_antiga)
            except Exception as e:
                log(f"ERRO ao enviar {Path(pdf_path).name} ao CRM: {e}")

        # Propostas prontas na pasta: vao para o Drive (mesma espera do CRM)
        prontos = [k for k, (t, _) in list(self._pending_drive.items()) if now - t >= DRIVE_WAIT_SECONDS]
        for key in prontos:
            _, pdf_path = self._pending_drive.pop(key)
            try:
                if Path(pdf_path).exists():
                    _lancar_no_drive(pdf_path, self.capa_pdf, self.pasta_raiz)
            except Exception as e:
                log(f"ERRO ao enviar {Path(pdf_path).name} ao Drive: {e}")

        # COMPLETO: junta tudo (8s de espera)
        prontos = [k for k, (t, _, __) in list(self._pending_completo.items()) if now - t >= WAIT_SECONDS]
        for key in prontos:
            t0, folder, trigger_path = self._pending_completo[key]
            # Ainda tem orcamento cru dessa mesma pasta na fila de envolver:
            # espera ele virar proposta antes de juntar. Senao o COMPLETO
            # pega um arquivo que ainda esta sendo gravado, ou o envolve
            # depois e sobra uma proposta solta na pasta. Desiste de esperar
            # em 2 minutos, para nunca ficar preso.
            if (now - t0 < ESPERA_MAXIMA_COMPLETO
                    and any(_norm(Path(p).parent) == key
                            for _, p in self._pending_single.values())):
                continue
            del self._pending_completo[key]
            try:
                self._process_completo(folder, trigger_path)
            except Exception as e:
                log(f"ERRO COMPLETO em {folder}: {e}")
                log(traceback.format_exc())

    def _descartar_single(self, *caminhos):
        """Tira da fila de "envolver individualmente" os orcamentos que o
        COMPLETO acabou de consumir -- senao o monitor montaria depois uma
        proposta individual de um arquivo que ja virou proposta final."""
        for caminho in caminhos:
            self._pending_single.pop(_norm(caminho), None)

    def _wrap_individual(self, src_path):
        """Envolve PVC ou ALM com Capa 1 + Capa 2 + Pagina Final."""
        tipo = detect_pdf_type(src_path)
        if tipo not in ("pvc", "alm"):
            return

        folder = str(Path(src_path).parent)
        client = suggest_client_name(folder)
        today  = date.today().strftime("%d-%m")

        if tipo == "pvc":
            vendedor = extrair_vendedor_do_nome_arquivo(src_path)
            cliente_capa = client
            doc_tmp = fitz.open(src_path)
            start_tmp = 1 if _has_system_capa(doc_tmp) else 0
            pedido = extrair_pedido_pvc(doc_tmp, start_tmp, len(doc_tmp) - 1)
            total_str = extract_total_pvc(src_path)
            sufixo = f"PVC {vendedor}" if vendedor else "PVC"
        else:
            # Preserva MAD/ALM do nome original no arquivo renomeado, senao a
            # informacao de madeira+aluminio se perde e o COMPLETO usa so "ALM"
            subtipo = detect_alm_subtipo(src_path)
            sufixo = {"mad": "MAD", "alm": "ALM", "alm_mad": "MAD ALM"}[subtipo]
            doc_tmp = fitz.open(src_path)
            start_tmp, _end_tmp = _alm_range(doc_tmp, src_path)
            vendedor = extrair_vendedor_alm(doc_tmp, start_tmp)
            cliente_capa = extrair_cliente_alm(doc_tmp, start_tmp) or client
            pedido = extrair_pedido_alm(doc_tmp, start_tmp)
            total_str = extract_total_alm(src_path)

        out_name = f"Proposta Comercial {client} {today} {sufixo}"
        output_path = output_path_do_dia(folder, out_name, client)

        log(f"[{client}] {sufixo} detectado — adicionando Capa e Pagina Final...")
        merge_individual(self.capa_pdf, src_path, output_path,
                          vendedor=vendedor, cliente=cliente_capa, pedido=pedido, total_str=total_str)
        if not _saida_valida(output_path, 4):
            log(f"[{client}] ATENCAO: arquivo envolvido saiu com poucas paginas — mantendo o original por seguranca.")
            return
        log(f"[{client}] SALVO: {Path(output_path).name}")
        _apagar(src_path, client)

    def _process_completo(self, folder, trigger_path):
        """Junta PVC + ALM com Capa/Pagina Final, somando os totais."""
        pdfs = find_pdfs_in_folder(folder)
        trigger_norm = _norm(trigger_path)
        client = suggest_client_name(folder)
        hoje = date.today()

        def elegivel(caminho):
            """Diz se esse PDF pode entrar no COMPLETO.

            Fica de fora a proposta final (ja montada) e, principalmente,
            tudo que e de OUTRO DIA. A pasta do cliente guarda as propostas
            dos dias anteriores, e o COMPLETO pegava qualquer uma delas --
            juntava o PVC de hoje com o aluminio da semana passada. No mesmo
            dia pode ter mais de um (proposta refeita): find_pdfs_in_folder
            entrega do mais novo para o mais antigo, entao vale o mais novo.
            """
            if _norm(caminho) == trigger_norm:
                return True
            if _is_proposta_final(caminho):
                return False
            dia = dia_do_arquivo(caminho)
            if dia != hoje:
                quando = f" ({dia.strftime('%d-%m')})" if dia else ""
                log(f"[{client}] COMPLETO: deixei de fora {Path(caminho).name}"
                    f" — e de outro dia{quando}.")
                return False
            return True

        for key in ("pvc", "alm"):
            pdfs[key] = [p for p in pdfs[key] if elegivel(p)]

        # Se o trigger nao aparece como PVC/ALM (nenhum conteudo reconhecivel), remove-o
        trigger_in_pvc = any(_norm(p) == trigger_norm for p in pdfs["pvc"])
        trigger_in_alm = any(_norm(p) == trigger_norm for p in pdfs["alm"])
        if not trigger_in_pvc and not trigger_in_alm:
            # Trigger e arquivo de sinal sem conteudo — apaga apos a mesclagem
            trigger_is_signal = True
        else:
            trigger_is_signal = False

        has_pvc = bool(pdfs["pvc"])
        has_alm = bool(pdfs["alm"])
        today   = hoje.strftime("%d-%m")

        log(f"[{client}] COMPLETO detectado — PVC={has_pvc} ALM={has_alm} — montando proposta final...")
        for rotulo in ("pvc", "alm"):
            if pdfs[rotulo]:
                log(f"[{client}] COMPLETO: usando como {rotulo.upper()} -> {Path(pdfs[rotulo][0]).name}")
                for descartado in pdfs[rotulo][1:]:
                    log(f"[{client}] COMPLETO: tinha outro {rotulo.upper()} de hoje "
                        f"({Path(descartado).name}) — usei o mais novo.")

        if has_pvc and has_alm:
            pvc_path  = pdfs["pvc"][0]
            alm_path  = pdfs["alm"][0]
            pvc_total = extract_total_pvc(pvc_path)
            alm_total = extract_total_alm(alm_path)

            if not pvc_total or not alm_total:
                log(f"[{client}] Nao foi possivel extrair totais. PVC={pvc_total or 'N/A'}  ALM={alm_total or 'N/A'}")
                return

            # Vendedor/Cliente/Pedido sempre seguem o W-Vetro quando ele existe
            alm_doc_tmp = fitz.open(alm_path)
            alm_start_tmp, _ = _alm_range(alm_doc_tmp, alm_path)
            vendedor = extrair_vendedor_alm(alm_doc_tmp, alm_start_tmp)
            cliente_capa = extrair_cliente_alm(alm_doc_tmp, alm_start_tmp) or client
            pedido = extrair_pedido_alm(alm_doc_tmp, alm_start_tmp)

            out_name = f"Proposta Comercial {client} {today}"
            output_path = output_path_do_dia(folder, out_name, client)
            log(f"[{client}] PVC R${pvc_total} + ALM R${alm_total} — montando proposta final...")
            merge_pvc(self.capa_pdf, pvc_path, alm_path, pvc_total, alm_total, output_path,
                      vendedor=vendedor, cliente=cliente_capa, pedido=pedido)
            if not _saida_valida(output_path, 5):
                log(f"[{client}] ATENCAO: proposta final saiu com poucas paginas — mantendo os arquivos originais por seguranca.")
                return
            log(f"[{client}] SALVO: {Path(output_path).name}")
            self._descartar_single(pvc_path, alm_path)
            _apagar(pvc_path, client)
            _apagar(alm_path, client)
            if trigger_is_signal:
                _apagar(trigger_path, client)

        elif has_alm:
            alm_path  = pdfs["alm"][0]
            alm_total = extract_total_alm(alm_path)
            alm_doc_tmp = fitz.open(alm_path)
            alm_start_tmp, _ = _alm_range(alm_doc_tmp, alm_path)
            vendedor = extrair_vendedor_alm(alm_doc_tmp, alm_start_tmp)
            cliente_capa = extrair_cliente_alm(alm_doc_tmp, alm_start_tmp) or client
            pedido = extrair_pedido_alm(alm_doc_tmp, alm_start_tmp)

            out_name = f"Proposta Comercial {client} {today}"
            output_path = output_path_do_dia(folder, out_name, client)
            log(f"[{client}] Aluminio — montando Capa + Conteudo + Pagina Final...")
            merge_alm(self.capa_pdf, alm_path, output_path,
                      vendedor=vendedor, cliente=cliente_capa, pedido=pedido, alm_total=alm_total)
            if not _saida_valida(output_path, 4):
                log(f"[{client}] ATENCAO: proposta final saiu com poucas paginas — mantendo os arquivos originais por seguranca.")
                return
            log(f"[{client}] SALVO: {Path(output_path).name}")
            self._descartar_single(alm_path)
            _apagar(alm_path, client)
            if trigger_is_signal:
                _apagar(trigger_path, client)

        elif has_pvc:
            log(f"[{client}] So PVC encontrado — falta o ALM (portas internas).")
        else:
            log(f"[{client}] Nenhum PDF de orcamento encontrado na pasta.")

# ── Main ──────────────────────────────────────────────────────────────────────

def validar_capa(capa_pdf):
    """Retorna None se ok, ou mensagem de erro."""
    if not Path(capa_pdf).exists():
        return f"Arquivo nao encontrado: {capa_pdf}"
    try:
        doc = fitz.open(capa_pdf)
        n = len(doc)
        doc.close()
        if n < 3:
            return (f"O PDF de Capa precisa ter 3 paginas (Capa 1 / Capa 2 / Pagina Final).\n"
                    f"  '{Path(capa_pdf).name}' tem apenas {n} pagina(s).")
    except Exception as e:
        return f"Erro ao abrir PDF de Capa: {e}"
    return None


def registrar_inicio_automatico():
    """Registra o proprio exe para abrir com o Windows (so no Windows)."""
    if os.name != "nt":
        return
    try:
        exe = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
        import winreg
        chave = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(chave, "EGEMAP-Monitor", 0, winreg.REG_SZ, str(exe))
        winreg.CloseKey(chave)
    except Exception:
        pass  # nao critico se falhar


def _perguntar_com_tempo(pergunta, segundos=20):
    """input() que desiste sozinho depois de alguns segundos.

    Precisa desistir porque o monitor abre junto com o Windows: se ficasse
    parado esperando resposta, nunca comecaria a monitorar a pasta.
    """
    print(pergunta, end="", flush=True)

    if os.name != "nt":
        try:
            return input().strip()
        except EOFError:
            return ""

    import msvcrt
    digitado = ""
    limite = time.time() + segundos
    while time.time() < limite:
        if msvcrt.kbhit():
            tecla = msvcrt.getwche()
            if tecla in ("\r", "\n"):
                print()
                return digitado.strip()
            if tecla == "\b":
                digitado = digitado[:-1]
            else:
                digitado += tecla
            limite = time.time() + segundos  # esta digitando: renova o prazo
        time.sleep(0.05)
    print()
    return ""


def oferecer_conexao_crm():
    """Pergunta uma vez, na abertura, se quer conectar o CRM.

    Some sozinha depois de conectado. Se ninguem responder, o monitor segue
    normalmente sem o CRM.
    """
    if crm_egemap is None or crm_egemap.configurado():
        return

    print()
    print("  " + "-" * 51)
    print("  O CRM ainda nao esta conectado.")
    print()
    print("  Conectando, a proposta pronta vai sozinha para o CRM:")
    print("  lanca o valor, anexa o PDF e move o cliente de coluna.")
    print("  " + "-" * 51)
    print()

    resposta = _perguntar_com_tempo(
        "  Digite 1 e ENTER para conectar agora (ou aguarde para pular): ", 20
    )
    if resposta != "1":
        print("\n  Pulado. Da pra conectar depois: e so abrir este programa de novo.")
        return

    print()
    try:
        crm_egemap.configurar()
    except Exception as e:
        print(f"\n  Nao consegui conectar: {e}")
    print()
    input("  Pressione ENTER para comecar a monitorar.")


def oferecer_conexao_drive():
    """Pergunta uma vez, na abertura, se quer conectar o Google Drive.

    Se voce ja usava o agente separado do Drive, ele fica conectado
    sozinho (mesma pasta de configuracao) e esta pergunta nem aparece.
    """
    if drive_egemap is None or drive_egemap.configurado():
        return

    print()
    print("  " + "-" * 51)
    print("  O Google Drive ainda nao esta conectado.")
    print()
    print("  Conectando, cada proposta pronta sobe sozinha para o")
    print("  Drive, na mesma estrutura de pastas do computador.")
    print("  " + "-" * 51)
    print()

    resposta = _perguntar_com_tempo(
        "  Digite 1 e ENTER para conectar agora (ou aguarde para pular): ", 20
    )
    if resposta != "1":
        print("\n  Pulado. Da pra conectar depois: e so abrir este programa de novo.")
        return

    print()
    try:
        drive_egemap.configurar()
    except Exception as e:
        print(f"\n  Nao consegui conectar: {e}")
    print()
    input("  Pressione ENTER para comecar a monitorar.")


# Marca que a faxina das pastas do Drive ja foi oferecida nesta maquina, pra
# nao ficar perguntando toda vez que o monitor abre.
FAXINA_JA_OFERECIDA = Path.home() / ".egemap_faxina_drive_ok"


def oferecer_faxina_drive():
    """Pergunta uma vez so, na abertura, se quer arrumar as pastas repetidas.

    Enquanto o monitor criava pasta nova por causa de maiuscula ("Passo De
    Torres" ao lado de "Passo de Torres"), o Drive juntou pastas repetidas.
    Isso ja foi corrigido; esta pergunta existe pra limpar o que ficou pra
    tras, e some depois de respondida.

    Como toda pergunta da abertura, desiste sozinha em 20 segundos -- o
    monitor abre junto com o Windows e nao pode ficar parado esperando.
    """
    if drive_egemap is None or not drive_egemap.configurado():
        return
    if FAXINA_JA_OFERECIDA.exists():
        return

    print()
    print("  " + "-" * 51)
    print("  Arrumar as pastas do Google Drive?")
    print()
    print("  Ate a versao passada o monitor criava pasta nova quando o")
    print("  nome so mudava de maiuscula, entao pode ter ficado uma")
    print("  'Passo De Torres' ao lado da 'Passo de Torres' que voce usa.")
    print()
    print("  Ele mostra tudo o que vai fazer ANTES e so mexe se voce")
    print("  confirmar. O que sair vai pra Lixeira do Drive.")
    print("  " + "-" * 51)
    print()

    resposta = _perguntar_com_tempo(
        "  Digite 1 e ENTER para arrumar agora (ou aguarde para pular): ", 20
    )
    if resposta != "1":
        print("\n  Pulado. Vou perguntar de novo na proxima vez que abrir.")
        return

    print()
    try:
        import limpar_drive
        # 2 = viu a previa e preferiu nao aplicar agora. Nesse caso nao marca
        # como feita, pra ele poder decidir na proxima vez que abrir.
        if limpar_drive.main([]) != 2:
            FAXINA_JA_OFERECIDA.write_text("feita\n", encoding="utf-8")
    except Exception as e:
        print(f"\n  Nao consegui arrumar: {e}")
    print()
    input("  Pressione ENTER para comecar a monitorar.")


def main():
    # "EGEMAP-Monitor.exe --limpar-drive" faz a faxina nas pastas do Drive
    # (LIMPAR_DRIVE.bat). Mostra tudo antes e so mexe se voce confirmar.
    if "--limpar-drive" in sys.argv[1:]:
        try:
            import limpar_drive
        except Exception as e:
            print(f"Faxina do Drive indisponivel nesta versao: {e}")
            input("\nPressione ENTER para fechar.")
            sys.exit(1)
        codigo = limpar_drive.main([a for a in sys.argv[1:] if a != "--limpar-drive"])
        input("\nPressione ENTER para fechar.")
        sys.exit(codigo)

    # "EGEMAP-Monitor.exe --crm" abre so a conexao com o CRM (CONECTAR_CRM.bat)
    if "--crm" in sys.argv[1:]:
        if crm_egemap is None:
            print("Integracao com o CRM indisponivel nesta versao.")
            input("\nPressione ENTER para fechar.")
            sys.exit(1)
        codigo = crm_egemap.configurar()
        input("\nPressione ENTER para fechar.")
        sys.exit(codigo)

    # "EGEMAP-Monitor.exe --drive" abre so a conexao com o Google Drive
    if "--drive" in sys.argv[1:]:
        if drive_egemap is None:
            print("Integracao com o Drive indisponivel nesta versao.")
            input("\nPressione ENTER para fechar.")
            sys.exit(1)
        ok = drive_egemap.configurar()
        input("\nPressione ENTER para fechar.")
        sys.exit(0 if ok else 1)

    os.system("cls" if os.name == "nt" else "clear")
    print("=" * 55)
    print("   EGEMAP - Monitor de Propostas Comerciais")
    print("=" * 55)
    print()

    saved_capa, saved_pasta = load_config()
    config_ok = (
        saved_capa and saved_pasta
        and Path(saved_capa).exists()
        and Path(saved_pasta).is_dir()
        and validar_capa(saved_capa) is None
    )

    if config_ok:
        capa_pdf   = saved_capa
        pasta_raiz = saved_pasta
        print(f"  Capa : {Path(capa_pdf).name}")
        print(f"  Pasta: {pasta_raiz}")
        print()
    else:
        # Primeira vez: faz as duas perguntas e nunca mais pergunta
        if saved_capa and not Path(saved_capa).exists():
            print(f"Aviso: capa anterior nao encontrada.")
            print()

        print("PRIMEIRA CONFIGURACAO (so precisa fazer uma vez)\n")

        capa_pdf = input("1. Cole o caminho do PDF de Capa e aperte Enter:\n> ").strip().strip('"').strip("'")
        erro = validar_capa(capa_pdf)
        if erro:
            print(f"\nERRO: {erro}")
            input("\nPressione ENTER para fechar.")
            sys.exit(1)

        pasta_raiz = input("\n2. Cole o caminho da pasta de orcamentos e aperte Enter:\n> ").strip().strip('"').strip("'")
        if not Path(pasta_raiz).is_dir():
            print(f"\nERRO: Pasta nao encontrada: {pasta_raiz}")
            input("\nPressione ENTER para fechar.")
            sys.exit(1)

        save_config(capa_pdf, pasta_raiz)
        registrar_inicio_automatico()
        print("\nPronto! A partir de agora abre automaticamente com o Windows.\n")

    oferecer_conexao_crm()
    oferecer_conexao_drive()
    oferecer_faxina_drive()

    if drive_egemap is not None:
        # Se o agente separado do Drive ainda estiver instalado, desliga a
        # tarefa antiga dele -- agora e este programa que cuida disso, e os
        # dois rodando juntos duplicaria os envios.
        try:
            drive_egemap.desativar_agente_antigo(log=log)
        except Exception:
            pass

    print()
    print("=" * 55)
    print(f"  Monitorando: {pasta_raiz}")
    print(f"  Capa: {Path(capa_pdf).name}")
    if crm_egemap is not None:
        email_crm = crm_egemap.carregar_config()[0]
        print(f"  CRM: {email_crm}" if email_crm else "  CRM: nao conectado")
    if drive_egemap is not None:
        print("  Drive: conectado" if drive_egemap.configurado() else "  Drive: nao conectado")
    print()
    print("  Salve qualquer PDF com COMPLETO no nome para")
    print("  disparar a montagem automatica da proposta.")
    print()
    print("  Pressione Ctrl+C para parar.")
    print("=" * 55)
    print()

    handler  = PropostaHandler(capa_pdf, pasta_raiz)
    observer = Observer()
    observer.schedule(handler, str(pasta_raiz), recursive=True)
    observer.start()

    log("Monitor iniciado. Aguardando arquivos COMPLETO...")

    try:
        while True:
            handler.tick()
            time.sleep(1)
    except KeyboardInterrupt:
        log("Parando monitor...")
        observer.stop()

    observer.join()
    print("\nMonitor encerrado.")


if __name__ == "__main__":
    main()
