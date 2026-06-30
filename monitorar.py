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


def safe_output_path(folder, name):
    base = Path(folder) / f"{name}.pdf"
    if not base.exists():
        return str(base)
    i = 1
    while True:
        candidate = Path(folder) / f"{name} ({i}).pdf"
        if not candidate.exists():
            return str(candidate)
        i += 1


def suggest_client_name(folder_path):
    return Path(folder_path).name or "Cliente"


def update_resumo_page(capa_pdf_path, pvc_total_str, alm_total_str):
    pvc = parse_brl(pvc_total_str)
    alm = parse_brl(alm_total_str)
    total = pvc + alm

    capa_doc = fitz.open(capa_pdf_path)
    resumo_doc = fitz.open()
    resumo_doc.insert_pdf(capa_doc, from_page=1, to_page=1)
    page = resumo_doc[0]

    full_text = page.get_text()
    money_matches = re.findall(r"R\$([\d.,]+)", full_text)

    found = []
    for val in money_matches:
        search_str = f"R${val}"
        rects = page.search_for(search_str)
        if rects:
            found.append((rects[0].y0, rects[0], val))

    found.sort(key=lambda x: x[0])
    new_values = [format_brl(pvc), format_brl(alm), format_brl(total)]

    for _, rect, _ in found:
        page.add_redact_annot(rect, fill=(1, 1, 1))
    page.apply_redactions()

    for (_, rect, _), new_val in zip(found, new_values):
        page.insert_text((rect.x0, rect.y1 - 1), f"R${new_val}",
                         fontname="helv", fontsize=20, color=(0, 0, 0))
    return resumo_doc


def _has_system_capa(doc):
    if len(doc) == 0:
        return False
    return "PROPOSTA" in doc[0].get_text().upper()


def _content_range(doc):
    n = len(doc)
    start = 1 if n > 1 else 0
    end = n - 2 if n > 2 else n - 1
    return start, end


def merge_pvc(capa_pdf_path, pvc_pdf_path, alm_pdf_path, pvc_total, alm_total, output_path):
    capa_doc = fitz.open(capa_pdf_path)
    pvc_doc  = fitz.open(pvc_pdf_path)
    alm_doc  = fitz.open(alm_pdf_path)
    resumo_doc = update_resumo_page(capa_pdf_path, pvc_total, alm_total)

    result = fitz.open()
    result.insert_pdf(capa_doc, from_page=0, to_page=0)

    pvc_start = 1 if _has_system_capa(pvc_doc) else 0
    if pvc_start < len(pvc_doc):
        result.insert_pdf(pvc_doc, from_page=pvc_start)

    alm_start, alm_end = _content_range(alm_doc)
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

    alm_start, alm_end = _content_range(alm_doc)
    if alm_start <= alm_end:
        result.insert_pdf(alm_doc, from_page=alm_start, to_page=alm_end)

    result.insert_pdf(capa_doc, from_page=2, to_page=2)
    result.save(output_path)
    result.close()

# ── Watchdog handler ──────────────────────────────────────────────────────────

WAIT_SECONDS = 4

def log(msg):
    hora = time.strftime("%H:%M:%S")
    print(f"[{hora}] {msg}", flush=True)


class PropostaHandler(FileSystemEventHandler):
    def __init__(self, capa_pdf):
        self.capa_pdf = capa_pdf
        self._pending = {}

    def _is_trigger(self, path):
        return "COMPLETO" in Path(path).stem.upper()

    def _queue(self, path):
        p = Path(path)
        if p.suffix.lower() == ".pdf" and self._is_trigger(str(p)):
            self._pending[str(p.parent)] = (time.time(), str(p))

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
        now = time.time()
        ready = [f for f, (t, _) in list(self._pending.items()) if now - t >= WAIT_SECONDS]
        for folder in ready:
            _, trigger_path = self._pending.pop(folder)
            try:
                self._process_folder(folder, trigger_path)
            except Exception as e:
                log(f"ERRO em {folder}: {e}")

    def _process_folder(self, folder, trigger_path):
        pdfs = find_pdfs_in_folder(folder)
        trigger = str(trigger_path)
        for key in pdfs:
            pdfs[key] = [p for p in pdfs[key] if p != trigger]

        has_pvc = bool(pdfs["pvc"])
        has_alm = bool(pdfs["alm"])

        client = suggest_client_name(folder)
        today  = date.today().strftime("%d-%m-%Y")
        out_name = f"Proposta Comercial {client} - {today}"
        output_path = safe_output_path(folder, out_name)

        log(f"[{client}] COMPLETO detectado — verificando PDFs...")

        if has_pvc and has_alm:
            pvc_path  = pdfs["pvc"][0]
            alm_path  = pdfs["alm"][0]
            pvc_total = extract_total_pvc(pvc_path)
            alm_total = extract_total_alm(alm_path)

            if not pvc_total or not alm_total:
                log(f"[{client}] Nao foi possivel extrair totais. PVC={pvc_total or 'N/A'}  ALM={alm_total or 'N/A'}")
                return

            log(f"[{client}] PVC R${pvc_total} + ALM R${alm_total} — montando com Resumo...")
            merge_pvc(self.capa_pdf, pvc_path, alm_path, pvc_total, alm_total, output_path)
            log(f"[{client}] SALVO: {Path(output_path).name}")

        elif has_alm and not has_pvc:
            alm_path = pdfs["alm"][0]
            log(f"[{client}] Aluminio — montando Capa + Conteudo + Contra Capa...")
            merge_alm(self.capa_pdf, alm_path, output_path)
            log(f"[{client}] SALVO: {Path(output_path).name}")

        elif has_pvc and not has_alm:
            log(f"[{client}] So PVC encontrado — falta o ALM (portas internas).")

        else:
            log(f"[{client}] Nenhum PDF de orcamento encontrado na pasta.")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    os.system("cls" if os.name == "nt" else "clear")
    print("=" * 55)
    print("   EGEMAP - Monitor de Propostas Comerciais")
    print("=" * 55)
    print()

    saved_capa, saved_pasta = load_config()

    # Capa PDF
    if saved_capa and Path(saved_capa).exists():
        print(f"Capa PDF salvo: {saved_capa}")
        resp = input("Usar este? (ENTER = sim, ou cole novo caminho): ").strip()
        capa_pdf = resp if resp else saved_capa
    else:
        capa_pdf = input("Cole o caminho do PDF de Capa (ex: C:\\EGEMAP\\Capa.pdf): ").strip()

    capa_pdf = capa_pdf.strip('"').strip("'")
    if not Path(capa_pdf).exists():
        print(f"\nERRO: Arquivo nao encontrado: {capa_pdf}")
        input("\nPressione ENTER para fechar.")
        sys.exit(1)

    # Pasta raiz
    if saved_pasta and Path(saved_pasta).exists():
        print(f"\nPasta salva: {saved_pasta}")
        resp = input("Usar esta? (ENTER = sim, ou cole nova pasta): ").strip()
        pasta_raiz = resp if resp else saved_pasta
    else:
        pasta_raiz = input("\nCole o caminho da pasta de orcamentos: ").strip()

    pasta_raiz = pasta_raiz.strip('"').strip("'")
    if not Path(pasta_raiz).is_dir():
        print(f"\nERRO: Pasta nao encontrada: {pasta_raiz}")
        input("\nPressione ENTER para fechar.")
        sys.exit(1)

    save_config(capa_pdf, pasta_raiz)

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
