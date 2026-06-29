#!/usr/bin/env python3
"""
EGEMAP - Monitor de Propostas
Interface gráfica com monitoramento automático de pasta.
"""

import sys
import time
import threading
import json
import re
from pathlib import Path
from datetime import date
import tkinter as tk
from tkinter import filedialog, scrolledtext
import tkinter.font as tkfont

# ── Dependências externas ─────────────────────────────────────────────────────

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    import subprocess, sys as _sys
    subprocess.check_call([_sys.executable, "-m", "pip", "install", "watchdog"])
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

try:
    import fitz
except ImportError:
    import subprocess, sys as _sys
    subprocess.check_call([_sys.executable, "-m", "pip", "install", "pymupdf"])
    import fitz

# ── Config ────────────────────────────────────────────────────────────────────

CONFIG_FILE = Path.home() / ".egemap_montador.json"

def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

# ── Lógica de PDF ─────────────────────────────────────────────────────────────

def find_pdfs_in_folder(folder):
    result = {"pvc": [], "alm": [], "other": []}
    for p in Path(folder).glob("*.pdf"):
        name_upper = p.name.upper()
        if "PVC" in name_upper:
            result["pvc"].append(str(p))
        elif "ALM" in name_upper:
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

def suggest_client_name(folder_path, pdf_path=""):
    folder_name = Path(folder_path).name
    if folder_name:
        return folder_name
    if pdf_path:
        stem = Path(pdf_path).stem
        stem = re.sub(r"\s*(PVC|ALM|pvc|alm)\s*$", "", stem, flags=re.IGNORECASE).strip()
        return stem
    return "Cliente"

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

class PropostaHandler(FileSystemEventHandler):
    def __init__(self, capa_pdf, log_fn):
        self.capa_pdf = capa_pdf
        self.log = log_fn
        self._pending = {}

    def _queue(self, path):
        p = Path(path)
        if p.suffix.lower() == ".pdf":
            name = p.name.upper()
            if "PVC" in name or "ALM" in name:
                self._pending[str(p.parent)] = time.time()

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
        ready = [f for f, t in list(self._pending.items()) if now - t >= WAIT_SECONDS]
        for folder in ready:
            del self._pending[folder]
            try:
                self._process_folder(folder)
            except Exception as e:
                self.log(f"ERRO em {folder}: {e}")

    def _process_folder(self, folder):
        pdfs = find_pdfs_in_folder(folder)
        has_pvc = bool(pdfs["pvc"])
        has_alm = bool(pdfs["alm"])

        if not has_pvc and not has_alm:
            return

        today  = date.today().strftime("%d-%m-%Y")
        client = suggest_client_name(folder, pdfs["pvc"][0] if pdfs["pvc"] else pdfs["alm"][0])
        out_name = f"Proposta Comercial {client} - {today}"
        output_path = safe_output_path(folder, out_name)

        if has_pvc and has_alm:
            pvc_path  = pdfs["pvc"][0]
            alm_path  = pdfs["alm"][0]
            pvc_total = extract_total_pvc(pvc_path)
            alm_total = extract_total_alm(alm_path)

            if not pvc_total or not alm_total:
                self.log(f"[{client}] Não foi possível extrair os totais automaticamente. "
                         f"PVC={pvc_total or 'N/A'}  ALM={alm_total or 'N/A'}")
                return

            self.log(f"[{client}] PVC + ALM detectados → montando proposta completa...")
            merge_pvc(self.capa_pdf, pvc_path, alm_path, pvc_total, alm_total, output_path)
            self.log(f"[{client}] ✔ Salvo: {Path(output_path).name}")

        elif has_alm and not has_pvc:
            alm_path = pdfs["alm"][0]
            self.log(f"[{client}] ALM detectado → montando proposta de alumínio...")
            merge_alm(self.capa_pdf, alm_path, output_path)
            self.log(f"[{client}] ✔ Salvo: {Path(output_path).name}")

        elif has_pvc and not has_alm:
            self.log(f"[{client}] Arquivo PVC encontrado — aguardando ALM para montar.")

# ── Interface gráfica ─────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EGEMAP — Monitor de Propostas")
        self.resizable(False, False)
        self.configure(bg="#1e1e2e")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.cfg = load_config()
        self._observer = None
        self._handler  = None
        self._running  = False
        self._tick_after = None

        self._build_ui()
        self._load_saved()

    def _build_ui(self):
        BG   = "#1e1e2e"
        CARD = "#2a2a3e"
        RED  = "#c0392b"
        GRN  = "#27ae60"
        TXT  = "#e0e0e0"
        SUB  = "#888"

        # ── Título ───────────────────────────────────────────────────────────
        tk.Label(self, text="EGEMAP", bg=BG, fg=RED,
                 font=("Arial", 20, "bold")).pack(pady=(18, 0))
        tk.Label(self, text="Monitor de Propostas Comerciais", bg=BG, fg=SUB,
                 font=("Arial", 9)).pack(pady=(0, 12))

        # ── Capa PDF ─────────────────────────────────────────────────────────
        frm1 = tk.Frame(self, bg=CARD, bd=0)
        frm1.pack(fill="x", padx=20, pady=4)
        tk.Label(frm1, text="PDF de Capa  (Capa_Orcamento_1.pdf)", bg=CARD, fg=SUB,
                 font=("Arial", 8)).pack(anchor="w", padx=10, pady=(8, 2))
        row1 = tk.Frame(frm1, bg=CARD)
        row1.pack(fill="x", padx=10, pady=(0, 8))
        self.var_capa = tk.StringVar()
        tk.Entry(row1, textvariable=self.var_capa, width=46, bg="#12121e", fg=TXT,
                 insertbackground=TXT, relief="flat", font=("Arial", 9)).pack(side="left")
        tk.Button(row1, text="Procurar", command=self._pick_capa,
                  bg=RED, fg="white", relief="flat", font=("Arial", 8),
                  padx=8, cursor="hand2").pack(side="left", padx=(6, 0))

        # ── Pasta ─────────────────────────────────────────────────────────────
        frm2 = tk.Frame(self, bg=CARD, bd=0)
        frm2.pack(fill="x", padx=20, pady=4)
        tk.Label(frm2, text="Pasta principal de Orçamentos", bg=CARD, fg=SUB,
                 font=("Arial", 8)).pack(anchor="w", padx=10, pady=(8, 2))
        row2 = tk.Frame(frm2, bg=CARD)
        row2.pack(fill="x", padx=10, pady=(0, 8))
        self.var_pasta = tk.StringVar()
        tk.Entry(row2, textvariable=self.var_pasta, width=46, bg="#12121e", fg=TXT,
                 insertbackground=TXT, relief="flat", font=("Arial", 9)).pack(side="left")
        tk.Button(row2, text="Procurar", command=self._pick_pasta,
                  bg=RED, fg="white", relief="flat", font=("Arial", 8),
                  padx=8, cursor="hand2").pack(side="left", padx=(6, 0))

        # ── Botão iniciar/parar ───────────────────────────────────────────────
        self.btn = tk.Button(self, text="▶  INICIAR MONITORAMENTO",
                             command=self._toggle,
                             bg=GRN, fg="white", relief="flat",
                             font=("Arial", 11, "bold"),
                             padx=20, pady=10, cursor="hand2")
        self.btn.pack(pady=14)

        # ── Status ────────────────────────────────────────────────────────────
        self.lbl_status = tk.Label(self, text="● Parado", bg=BG, fg=SUB,
                                   font=("Arial", 9))
        self.lbl_status.pack()

        # ── Log ───────────────────────────────────────────────────────────────
        tk.Label(self, text="Registro de atividade", bg=BG, fg=SUB,
                 font=("Arial", 8)).pack(anchor="w", padx=22, pady=(10, 2))
        self.log_box = scrolledtext.ScrolledText(
            self, width=62, height=14, bg="#12121e", fg=TXT,
            font=("Consolas", 8), relief="flat", state="disabled",
            insertbackground=TXT)
        self.log_box.pack(padx=20, pady=(0, 16))

    def _load_saved(self):
        self.var_capa.set(self.cfg.get("capa_pdf", ""))
        self.var_pasta.set(self.cfg.get("pasta_orcamentos", ""))

    def _pick_capa(self):
        path = filedialog.askopenfilename(
            title="Selecionar PDF de Capa",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")])
        if path:
            self.var_capa.set(path)

    def _pick_pasta(self):
        path = filedialog.askdirectory(title="Selecionar Pasta de Orçamentos")
        if path:
            self.var_pasta.set(path)

    def _log(self, msg):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}]  {msg}\n"
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _toggle(self):
        if self._running:
            self._stop()
        else:
            self._start()

    def _start(self):
        capa  = self.var_capa.get().strip()
        pasta = self.var_pasta.get().strip()

        if not capa or not Path(capa).exists():
            self._log("ERRO: Selecione o PDF de Capa válido.")
            return
        if not pasta or not Path(pasta).exists():
            self._log("ERRO: Selecione a Pasta de Orçamentos válida.")
            return

        self.cfg["capa_pdf"] = capa
        self.cfg["pasta_orcamentos"] = pasta
        save_config(self.cfg)

        self._handler  = PropostaHandler(capa_pdf=capa, log_fn=self._log)
        self._observer = Observer()
        self._observer.schedule(self._handler, pasta, recursive=True)
        self._observer.start()
        self._running = True

        self.btn.configure(text="■  PARAR MONITORAMENTO", bg="#c0392b")
        self.lbl_status.configure(text="● Monitorando...", fg="#27ae60")
        self._log(f"Monitorando: {pasta}")
        self._log(f"Capa: {Path(capa).name}")
        self._tick()

    def _stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        if self._tick_after:
            self.after_cancel(self._tick_after)
            self._tick_after = None
        self._running = False
        self.btn.configure(text="▶  INICIAR MONITORAMENTO", bg="#27ae60")
        self.lbl_status.configure(text="● Parado", fg="#888")
        self._log("Monitor parado.")

    def _tick(self):
        if self._running and self._handler:
            self._handler.tick()
        if self._running:
            self._tick_after = self.after(1000, self._tick)

    def _on_close(self):
        self._stop()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
