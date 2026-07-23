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


LABELS_SUBTIPO = {
    "alm":     "Esquadrias de Alumínio",
    "mad":     "Esquadrias de Madeira",
    "alm_mad": "Esquadrias de Madeira e Alumínio",
}


_FONT_CACHE: dict = {}

def _extract_font_from_capa(capa_pdf_path, want_black: bool):
    """Extrai Arial-Black ou ArialMT do PDF da capa e salva em temp."""
    import tempfile
    cache_key = (str(capa_pdf_path), want_black)
    if cache_key in _FONT_CACHE:
        return _FONT_CACHE[cache_key]
    result = None
    try:
        doc = fitz.open(capa_pdf_path)
        page = doc[1]
        for finfo in page.get_fonts():
            # get_fonts() retorna 6 ou 7 campos dependendo da versao do PyMuPDF
            xref, ext, _t, basename, _name, _enc = finfo[:6]
            lower = basename.lower()
            is_black  = "black" in lower
            is_bold   = "bold" in lower
            is_italic = "italic" in lower
            if want_black:
                matches = is_black
            else:
                matches = "arial" in lower and not is_black and not is_bold and not is_italic
            if matches:
                data = doc.extract_font(xref)
                if data and data[3]:
                    fname = "ariblk" if want_black else "arialmt"
                    tmp = Path(tempfile.gettempdir()) / f"egemap_{fname}.{ext or 'ttf'}"
                    tmp.write_bytes(data[3])
                    result = str(tmp)
                    break
    except Exception:
        pass
    _FONT_CACHE[cache_key] = result
    return result


def _get_resumo_fonts(capa_pdf_path=None):
    """Retorna (fn_bold, fn_regular) — busca no sistema e extrai da capa como fallback."""
    fn_bold = fn_reg = None

    if os.name == "nt":
        win_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        # Arial Black (ariblk) ou Arial Bold (arialbd) como fallback
        for f in ("ariblk.ttf", "arialbd.ttf"):
            p = win_dir / f
            if p.exists():
                fn_bold = str(p)
                break
        p = win_dir / "arial.ttf"
        if p.exists():
            fn_reg = str(p)
    else:
        for base in (
            Path("/usr/share/fonts/truetype/liberation"),
            Path("/usr/share/fonts/liberation"),
        ):
            b = base / "LiberationSans-Bold.ttf"
            r = base / "LiberationSans-Regular.ttf"
            if b.exists() and r.exists():
                fn_bold, fn_reg = str(b), str(r)
                break

    # Se ainda nao achou, extrai do proprio PDF da capa
    if capa_pdf_path:
        if fn_bold is None:
            fn_bold = _extract_font_from_capa(capa_pdf_path, want_black=True)
        if fn_reg is None:
            fn_reg = _extract_font_from_capa(capa_pdf_path, want_black=False)

    return fn_bold, fn_reg


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


def update_resumo_page(capa_pdf_path, pvc_total_str, alm_total_str, alm_subtipo="alm_mad"):
    pvc   = parse_brl(pvc_total_str)
    alm   = parse_brl(alm_total_str)
    total = pvc + alm
    novo_label = LABELS_SUBTIPO.get(alm_subtipo, "Esquadrias de Madeira e Alumínio")
    capa_doc   = fitz.open(capa_pdf_path)
    fn_bold, fn_reg = _get_resumo_fonts(capa_pdf_path)
    resumo_doc = fitz.open()
    resumo_doc.insert_pdf(capa_doc, from_page=1, to_page=1)
    page = resumo_doc[0]

    # Coleta spans com origem (baseline) para posicionamento exato
    # Estrutura: { "pvc_val": (origin, font, size, color), "alm_label": ..., "alm_val": ..., "total_val": ... }
    spans_por_linha = []  # lista de (y_baseline, origin, text, font, size, color)
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                t = span["text"].strip()
                if not t:
                    continue
                spans_por_linha.append({
                    "text":   t,
                    "origin": span["origin"],   # (x, y) baseline exato
                    "bbox":   span["bbox"],     # (x0, y0, x1, y1)
                    "font":   span["font"],
                    "size":   span["size"],
                    "color":  span["color"],
                })

    # Identifica os 3 valores R$ por ordem vertical (baseline y)
    money_spans = sorted(
        [s for s in spans_por_linha if s["text"].startswith("R$")],
        key=lambda s: s["origin"][1]
    )

    # Identifica label ALM (linha que tem "Esquadrias de" mas nao "PVC")
    alm_label_span = next(
        (s for s in spans_por_linha if "Esquadrias de" in s["text"] and "PVC" not in s["text"]),
        None
    )

    # Identifica label PVC (linha que tem "Esquadrias de" e "PVC")
    pvc_label_span = next(
        (s for s in spans_por_linha if "Esquadrias de" in s["text"] and "PVC" in s["text"]),
        None
    )

    to_redact = []
    to_insert = []  # (x, y_baseline, text, fontfile, fontsize, color)

    # Valor PVC (1º por y)
    if len(money_spans) >= 1:
        s = money_spans[0]
        for r in page.search_for(s["text"]):
            to_redact.append(r)
        if pvc_label_span:
            # Posiciona a partir da borda direita real do label "Esquadrias de PVC:"
            # (a posicao original do placeholder ficava colada/sobreposta ao label)
            ox = pvc_label_span["bbox"][2] + 4
            oy = pvc_label_span["origin"][1]
        else:
            ox, oy = s["origin"]
        to_insert.append((ox, oy, f"R${format_brl(pvc)}", fn_bold, s["size"], (0, 0, 0)))

    # Label ALM + valor ALM (2º por y)
    if alm_label_span:
        for r in page.search_for(alm_label_span["text"]):
            to_redact.append(r)
        lx, ly = alm_label_span["origin"]
        # Mede largura do novo label para posicionar o valor ao lado
        font_reg_obj = fitz.Font(fontfile=fn_reg)
        lw = font_reg_obj.text_length(novo_label + ":", fontsize=alm_label_span["size"])
        to_insert.append((lx, ly, novo_label + ":", fn_reg, alm_label_span["size"], (0, 0, 0)))
        if len(money_spans) >= 2:
            s2 = money_spans[1]
            for r in page.search_for(s2["text"]):
                to_redact.append(r)
            to_insert.append((lx + lw + 4, ly, f"R${format_brl(alm)}", fn_bold, s2["size"], (0, 0, 0)))

    # Valor Total (3º por y)
    if len(money_spans) >= 3:
        s = money_spans[2]
        for r in page.search_for(s["text"]):
            to_redact.append(r)
        ox, oy = s["origin"]
        col = _color_tuple(s["color"])
        to_insert.append((ox, oy, f"R${format_brl(total)}", fn_bold, s["size"], col))

    for rect in to_redact:
        page.add_redact_annot(rect, fill=(1, 1, 1))
    page.apply_redactions()
    for x, y, text, ff, fs, col in to_insert:
        if ff:
            # fontname precisa ser explicito: sem ele o PyMuPDF ignora o
            # fontfile e cai no Helvetica padrao (fontname="helv" e o default).
            alias = re.sub(r"[^A-Za-z0-9]+", "_", Path(ff).stem)
            page.insert_text((x, y), text, fontfile=ff, fontname=alias, fontsize=fs, color=col)
        else:
            page.insert_text((x, y), text, fontname="helv", fontsize=fs, color=col)

    return resumo_doc



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
    n = len(doc)
    start = 1 if n > 1 else 0
    end = n - 2 if n > 2 else n - 1
    return start, end


def _alm_range(alm_doc, alm_pdf_path):
    """Paginas de conteudo W-Vetro: todas se original, sem capa/contra-capa se ja e wrap."""
    if _is_proposta_gerada(alm_pdf_path):
        return _content_range(alm_doc)
    return 0, len(alm_doc) - 1


def merge_pvc(capa_pdf_path, pvc_pdf_path, alm_pdf_path, pvc_total, alm_total, output_path, alm_subtipo="alm_mad"):
    capa_doc = fitz.open(capa_pdf_path)
    pvc_doc  = fitz.open(pvc_pdf_path)
    alm_doc  = fitz.open(alm_pdf_path)
    resumo_doc = update_resumo_page(capa_pdf_path, pvc_total, alm_total, alm_subtipo)

    result = fitz.open()
    result.insert_pdf(capa_doc, from_page=0, to_page=0)

    if _is_proposta_gerada(pvc_pdf_path):
        # Wrap nosso: pula nossa Capa (pg 0) e nossa Contra Capa (ultima pg)
        pvc_start = 1
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

    result.insert_pdf(resumo_doc)
    result.insert_pdf(capa_doc, from_page=2, to_page=2)
    result.save(output_path)
    result.close()


def merge_alm(capa_pdf_path, alm_pdf_path, output_path):
    capa_doc = fitz.open(capa_pdf_path)
    alm_doc  = fitz.open(alm_pdf_path)

    result = fitz.open()
    result.insert_pdf(capa_doc, from_page=0, to_page=0)

    alm_start, alm_end = _alm_range(alm_doc, alm_pdf_path)
    if not _is_proposta_gerada(alm_pdf_path):
        limpar_campos_vazios_alm(alm_doc, alm_start)
    if alm_start <= alm_end:
        result.insert_pdf(alm_doc, from_page=alm_start, to_page=alm_end)

    result.insert_pdf(capa_doc, from_page=2, to_page=2)
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
    """Proposta final completa (sem sufixo PVC/ALM) — nao usar como fonte no COMPLETO."""
    stem = Path(path).stem
    if not stem.startswith("Proposta Comercial"):
        return False
    upper = stem.upper()
    # Wraps individuais (sufixo PVC, ALM, MAD ou MAD ALM) PODEM ser usados como fonte
    if upper.endswith(" PVC") or upper.endswith(" ALM") or upper.endswith(" MAD"):
        return False
    return True


def merge_individual(capa_pdf_path, src_pdf_path, output_path):
    """Envolve um unico PDF (PVC ou ALM) com Capa + conteudo + Contra Capa."""
    capa_doc = fitz.open(capa_pdf_path)
    src_doc  = fitz.open(src_pdf_path)
    result   = fitz.open()

    result.insert_pdf(capa_doc, from_page=0, to_page=0)

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

    result.insert_pdf(capa_doc, from_page=2, to_page=2)
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

        # PDFs individuais: envolve com Capa + Contra Capa (6s de espera)
        prontos = [k for k, (t, _) in list(self._pending_single.items()) if now - t >= 6]
        for key in prontos:
            _, src_path = self._pending_single.pop(key)
            try:
                self._wrap_individual(src_path)
            except Exception as e:
                log(f"ERRO ao envolver {src_path}: {e}")
                log(traceback.format_exc())

        # COMPLETO: junta tudo com Resumo (8s de espera)
        prontos = [k for k, (t, _, __) in list(self._pending_completo.items()) if now - t >= WAIT_SECONDS]
        for key in prontos:
            _, folder, trigger_path = self._pending_completo.pop(key)
            try:
                self._process_completo(folder, trigger_path)
            except Exception as e:
                log(f"ERRO COMPLETO em {folder}: {e}")
                log(traceback.format_exc())

    def _wrap_individual(self, src_path):
        """Envolve PVC ou ALM com Capa + Contra Capa."""
        tipo = detect_pdf_type(src_path)
        if tipo not in ("pvc", "alm"):
            return

        folder = str(Path(src_path).parent)
        client = suggest_client_name(folder)
        today  = date.today().strftime("%d-%m")
        if tipo == "pvc":
            sufixo = "PVC"
        else:
            # Preserva MAD/ALM do nome original no arquivo renomeado, senao a
            # informacao de madeira+aluminio se perde e o COMPLETO usa so "ALM"
            subtipo = detect_alm_subtipo(src_path)
            sufixo = {"mad": "MAD", "alm": "ALM", "alm_mad": "MAD ALM"}[subtipo]
        out_name = f"Proposta Comercial {client} {today} {sufixo}"
        output_path = output_path_do_dia(folder, out_name, client)

        log(f"[{client}] {sufixo} detectado — adicionando Capa e Contra Capa...")
        merge_individual(self.capa_pdf, src_path, output_path)
        if not _saida_valida(output_path, 3):
            log(f"[{client}] ATENCAO: arquivo envolvido saiu com poucas paginas — mantendo o original por seguranca.")
            return
        log(f"[{client}] SALVO: {Path(output_path).name}")
        _apagar(src_path, client)

    def _process_completo(self, folder, trigger_path):
        """Junta PVC + ALM com Resumo somando os totais."""
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

            out_name = f"Proposta Comercial {client} {today}"
            output_path = output_path_do_dia(folder, out_name, client)
            log(f"[{client}] PVC R${pvc_total} + ALM R${alm_total} — montando com Resumo...")
            alm_subtipo = detect_alm_subtipo(alm_path)
            merge_pvc(self.capa_pdf, pvc_path, alm_path, pvc_total, alm_total, output_path, alm_subtipo)
            if not _saida_valida(output_path, 4):
                log(f"[{client}] ATENCAO: proposta final saiu com poucas paginas — mantendo os arquivos originais por seguranca.")
                return
            log(f"[{client}] SALVO: {Path(output_path).name}")
            _apagar(pvc_path, client)
            _apagar(alm_path, client)
            if trigger_is_signal:
                _apagar(trigger_path, client)

        elif has_alm:
            alm_path = pdfs["alm"][0]
            out_name = f"Proposta Comercial {client} {today}"
            output_path = output_path_do_dia(folder, out_name, client)
            log(f"[{client}] Aluminio — montando Capa + Conteudo + Contra Capa...")
            merge_alm(self.capa_pdf, alm_path, output_path)
            if not _saida_valida(output_path, 3):
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
            return (f"O PDF de Capa precisa ter 3 paginas (Capa / Resumo / Contra Capa).\n"
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
