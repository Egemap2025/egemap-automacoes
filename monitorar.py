#!/usr/bin/env python3
"""
EGEMAP - Monitor de Propostas
Janela de console que fica rodando em segundo plano monitorando a pasta.
"""

import sys
import time
import re
import os
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

# ── Lógica de PDF ─────────────────────────────────────────────────────────────

def detect_pdf_type(pdf_path):
    try:
        name = Path(pdf_path).name.upper()
        if "PVC" in name:
            return "pvc"
        if "ALM" in name or "MAD" in name:
            return "alm"

        doc = fitz.open(pdf_path)
        text = "".join(p.get_text() for p in doc)

        if "OAD-" in text or "TOTAL GERAL (R$)" in text or "Archicentro" in text:
            return "pvc"
        if "w.vetro" in text.lower() or "wvetro" in text.lower():
            return "alm"
        if "TOTAL:" in text and "EGEMAP" in text:
            return "alm"
    except Exception:
        pass
    return None


def find_pdfs_in_folder(folder):
    result = {"pvc": [], "alm": [], "other": []}
    for p in Path(folder).glob("*.pdf"):
        tipo = detect_pdf_type(str(p))
        if tipo == "pvc":
            result["pvc"].append(str(p))
        elif tipo == "alm":
            result["alm"].append(str(p))
        else:
            result["other"].append(str(p))
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
    """Formata o valor grande da pagina final (Proposta de Investimento) --
    sem centavos, so os milhares (ex: 75.090), igual ao padrao "R$ 000.000"
    do template novo."""
    return f"{round(value):,}".replace(",", ".")


def output_path_do_dia(folder, name, client=""):
    """Caminho de saida da proposta. O nome ja inclui a data (DD-MM), entao
    se ja existe um arquivo com esse nome e porque a proposta deste cliente
    foi refeita hoje (ex: cliente pediu alteracao) -- substitui a versao
    anterior de hoje em vez de criar um "(1)" duplicado."""
    path = Path(folder) / f"{name}.pdf"
    if path.exists():
        _apagar(str(path), client)
    return str(path)


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

def _caminho_fonte_bundled():
    """Caminho da fonte DM Sans (completa) que vem empacotada junto com o
    programa -- funciona tanto rodando via "python monitorar.py" quanto no
    .exe gerado pelo PyInstaller (--add-data)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    caminho = base / "DMSans-Regular.ttf"
    return str(caminho) if caminho.exists() else None


_CAPA_FONT_CACHE: dict = {}

def _extrair_fonte_da_capa(capa_pdf_path):
    """Fallback: extrai a fonte DM Sans direto do PDF da capa. So usado se a
    fonte empacotada (DMSans-Regular.ttf) nao for encontrada -- a fonte
    dentro do PDF costuma vir "picotada" (so tem as letras que ja apareciam
    no texto original dos placeholders, faltando letras/numeros/simbolos
    necessarios pra inserir nomes e valores novos)."""
    cache_key = str(capa_pdf_path)
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
                chave = basename.lower().replace(" ", "").replace("-", "")
                if "dmsans" in chave:
                    data = doc.extract_font(xref)
                    if data and data[3]:
                        tmp = Path(tempfile.gettempdir()) / f"egemap_dmsans.{ext or 'ttf'}"
                        tmp.write_bytes(data[3])
                        result = str(tmp)
                        break
            if result:
                break
    except Exception:
        pass
    _CAPA_FONT_CACHE[cache_key] = result
    return result


def _get_capa_dinamica_font(capa_pdf_path):
    """Fonte usada nos textos dinamicos da capa (DM Sans). Prioriza a fonte
    completa empacotada com o programa; so cai pro fallback (extrair do PDF,
    que pode vir com letras faltando) se ela nao existir."""
    return _caminho_fonte_bundled() or _extrair_fonte_da_capa(capa_pdf_path)


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


def _substituir_linha_inteira(page, texto_antigo, texto_novo, fontfile):
    """Troca uma linha cujo texto e EXATAMENTE texto_antigo por texto_novo,
    mantendo posicao, tamanho e cor originais. Usado para os placeholders
    que ocupam a linha toda (ex: "[nome do vendedor]", "R$ 000.000")."""
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            t = "".join(s["text"] for s in line["spans"]).strip()
            if t == texto_antigo:
                span = line["spans"][0]
                ox, oy = span["origin"]
                size = span["size"]
                color = _color_tuple(span["color"])
                page.add_redact_annot(fitz.Rect(line["bbox"]), fill=(1, 1, 1))
                page.apply_redactions()
                _inserir_texto(page, (ox, oy), texto_novo, fontfile, size, color)
                return True
    return False


def _substituir_dentro_da_linha(page, marcador, texto_novo, fontfile):
    """Troca so a parte "marcador" de uma linha maior (ex: "[NOME DO CLIENTE],
    é uma honra fazer parte do seu projeto."), preservando o resto da frase
    que vem depois do marcador."""
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            t = "".join(s["text"] for s in line["spans"])
            if marcador in t:
                idx = t.find(marcador)
                resto = t[idx + len(marcador):]
                span = line["spans"][0]
                ox, oy = span["origin"]
                size = span["size"]
                color = _color_tuple(span["color"])
                page.add_redact_annot(fitz.Rect(line["bbox"]), fill=(1, 1, 1))
                page.apply_redactions()
                _inserir_texto(page, (ox, oy), texto_novo, fontfile, size, color)
                if resto:
                    largura = _medir_texto(texto_novo, fontfile, size)
                    _inserir_texto(page, (ox + largura, oy), resto, fontfile, size, color)
                return True
    return False


def montar_paginas_capa(capa_pdf_path, vendedor, cliente, pedido, total_str):
    """Monta a Capa completa (3 paginas) com os dados do cliente:
    Capa 1 (vendedor/cliente/pedido) e a pagina final (cliente + valor do
    investimento) editadas; Capa 2 (institucional) fica intocada. Retorna um
    doc de 3 paginas -- as paginas 0-1 vao no inicio da proposta final e a
    pagina 2 vai no fim."""
    fontfile = _get_capa_dinamica_font(capa_pdf_path)
    doc = fitz.open()
    doc.insert_pdf(fitz.open(capa_pdf_path))

    p1 = doc[0]
    _substituir_linha_inteira(p1, "[nome do vendedor]", vendedor or "[nome do vendedor]", fontfile)
    _substituir_linha_inteira(p1, "[nome do cliente]", cliente or "[nome do cliente]", fontfile)
    _substituir_linha_inteira(p1, "[número do pedido]", pedido or "[número do pedido]", fontfile)

    pf = doc[len(doc) - 1]
    _substituir_dentro_da_linha(pf, "[NOME DO CLIENTE]", (cliente or "[NOME DO CLIENTE]").upper(), fontfile)
    _substituir_linha_inteira(pf, "R$ 000.000", f"R$ {total_str}", fontfile)

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
    """Detecta pelo nome do arquivo se é ALM, MAD ou ambos."""
    name = Path(pdf_path).name.upper()
    has_alm = "ALM" in name
    has_mad = "MAD" in name
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
    result.save(output_path)
    result.close()


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
    result.save(output_path)
    result.close()

# ── Watchdog handler ──────────────────────────────────────────────────────────

WAIT_SECONDS = 8  # espera 8s apos o ultimo evento para garantir que o PDF foi salvo

def log(msg):
    hora = time.strftime("%H:%M:%S")
    print(f"[{hora}] {msg}", flush=True)


def _apagar(path, client=""):
    # Tenta algumas vezes: o Windows pode segurar o arquivo por um instante
    # (antivirus escaneando, gravacao ainda nao liberada, etc.)
    for tentativa in range(5):
        try:
            Path(path).unlink()
            log(f"[{client}] Removido original: {Path(path).name}")
            return
        except Exception as e:
            if tentativa == 4:
                log(f"[{client}] Nao foi possivel remover {Path(path).name}: {e}")
            else:
                time.sleep(1)


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
    result.save(output_path)
    result.close()


class PropostaHandler(FileSystemEventHandler):
    def __init__(self, capa_pdf):
        self.capa_pdf = capa_pdf
        self._pending_single   = {}  # pdf_norm   -> (timestamp, caminho)
        self._pending_completo = {}  # folder_norm -> (timestamp, pasta, trigger)

    def _queue(self, path):
        p = Path(path)
        if p.suffix.lower() != ".pdf":
            return
        if _is_proposta_gerada(str(p)):
            return  # ignora PDFs ja gerados pelo programa

        stem_upper = p.stem.upper()

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
        if not event.is_directory:
            self._queue(event.dest_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._queue(event.src_path)

    def tick(self):
        import traceback
        now = time.time()

        # PDFs individuais: envolve com Capa + Pagina Final (6s de espera)
        prontos = [k for k, (t, _) in list(self._pending_single.items()) if now - t >= 6]
        for key in prontos:
            _, src_path = self._pending_single.pop(key)
            try:
                self._wrap_individual(src_path)
            except Exception as e:
                log(f"ERRO ao envolver {src_path}: {e}")
                log(traceback.format_exc())

        # COMPLETO: junta tudo (8s de espera)
        prontos = [k for k, (t, _, __) in list(self._pending_completo.items()) if now - t >= WAIT_SECONDS]
        for key in prontos:
            _, folder, trigger_path = self._pending_completo.pop(key)
            try:
                self._process_completo(folder, trigger_path)
            except Exception as e:
                log(f"ERRO COMPLETO em {folder}: {e}")
                log(traceback.format_exc())

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

        # Permite propostas wrap individuais (PVC/ALM) como fontes; exclui propostas finais
        for key in pdfs:
            pdfs[key] = [p for p in pdfs[key] if not _is_proposta_final(p)]

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
        client  = suggest_client_name(folder)
        today   = date.today().strftime("%d-%m")

        log(f"[{client}] COMPLETO detectado — PVC={has_pvc} ALM={has_alm} — montando proposta final...")

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


def main():
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

    print()
    print("=" * 55)
    print(f"  Monitorando: {pasta_raiz}")
    print(f"  Capa: {Path(capa_pdf).name}")
    print()
    print("  Salve qualquer PDF com COMPLETO no nome para")
    print("  disparar a montagem automatica da proposta.")
    print()
    print("  Pressione Ctrl+C para parar.")
    print("=" * 55)
    print()

    handler  = PropostaHandler(capa_pdf)
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
