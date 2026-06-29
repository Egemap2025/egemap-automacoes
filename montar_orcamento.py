#!/usr/bin/env python3
"""
Montador de Propostas EGEMAP
Junta automaticamente: Capa + Sintegra (PVC) + W-Vetro (ALM) + Resumo + Contra Capa
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import fitz  # PyMuPDF
import re
import os
import json
from pathlib import Path
from datetime import date

CONFIG_FILE = Path.home() / ".egemap_montador.json"


# ── Config ──────────────────────────────────────────────────────────────────

def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


# ── PDF detection ────────────────────────────────────────────────────────────

def find_pdfs_in_folder(folder):
    """Returns dict with keys 'pvc', 'alm', 'other' — lists of PDF paths."""
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


# ── Total extraction ─────────────────────────────────────────────────────────

def extract_total_pvc(pdf_path):
    """Extracts total from Sintegra (PVC) PDF — looks for 'TOTAL GERAL (R$)'."""
    try:
        doc = fitz.open(pdf_path)
        text = "".join(p.get_text() for p in doc)
        match = re.search(r"TOTAL GERAL \(R\$\)\s*([\d.,]+)", text)
        if match:
            return match.group(1)
    except Exception:
        pass
    return ""


def extract_total_alm(pdf_path):
    """Extracts total from W-Vetro (ALM) PDF — looks for last 'TOTAL:' value."""
    try:
        doc = fitz.open(pdf_path)
        text = "".join(p.get_text() for p in doc)
        matches = re.findall(r"TOTAL:\s*([\d.,]+)", text)
        if matches:
            return matches[-1]
    except Exception:
        pass
    return ""


def parse_brl(value_str):
    """'1.234,56' → 1234.56"""
    cleaned = value_str.strip().replace("R$", "").replace(" ", "")
    return float(cleaned.replace(".", "").replace(",", "."))


def format_brl(value):
    """1234.56 → '1.234,56'"""
    s = f"{value:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# ── Resumo page generation ───────────────────────────────────────────────────

# Known positions in the capa PDF resumo page (page index 1)
# These were extracted from the template analysis.
_RESUMO_VALUES = [
    # (search_text_prefix, value_key)
    # We'll search for the actual text and replace
]


def update_resumo_page(capa_pdf_path, pvc_total_str, alm_total_str):
    """
    Copies the resumo page from the capa PDF and replaces monetary values.
    Returns a fitz.Document with a single page (the updated resumo).
    """
    pvc = parse_brl(pvc_total_str)
    alm = parse_brl(alm_total_str)
    total = pvc + alm

    capa_doc = fitz.open(capa_pdf_path)
    resumo_doc = fitz.open()
    resumo_doc.insert_pdf(capa_doc, from_page=1, to_page=1)
    page = resumo_doc[0]

    # Find all R$value occurrences (exact text search gives tight bounding boxes)
    full_text = page.get_text()
    money_matches = re.findall(r"R\$([\d.,]+)", full_text)

    # Sort found values by y-position using search_for
    found = []
    for val in money_matches:
        search_str = f"R${val}"
        rects = page.search_for(search_str)
        if rects:
            found.append((rects[0].y0, rects[0], val, search_str))

    found.sort(key=lambda x: x[0])  # top to bottom

    # Expected order: PVC (top), Madeira (middle), Total (bottom)
    new_values = [format_brl(pvc), format_brl(alm), format_brl(total)]

    # Step 1: redact old values (using tight rects from search_for)
    for _, rect, _, _ in found:
        page.add_redact_annot(rect, fill=(1, 1, 1))
    page.apply_redactions()

    # Step 2: write new values at the same positions
    for (_, rect, _, _), new_val in zip(found, new_values):
        page.insert_text(
            (rect.x0, rect.y1 - 1),
            f"R${new_val}",
            fontname="helv",
            fontsize=20,
            color=(0, 0, 0),
        )

    return resumo_doc


# ── PDF merge ────────────────────────────────────────────────────────────────

def _has_system_capa(doc, page_idx=0):
    """Returns True if the page looks like a system-generated cover (has 'PROPOSTA' text)."""
    if len(doc) <= page_idx:
        return False
    txt = doc[page_idx].get_text().strip()
    return "PROPOSTA" in txt.upper()


def _has_system_contracapa(doc):
    """Returns True if last page looks like a system-generated back cover."""
    if len(doc) == 0:
        return False
    txt = doc[-1].get_text().strip()
    # W-Vetro contracapa has EGEMAP warranty text; empty = image-only EGEMAP contracapa
    return "EGEMAP" in txt.upper() or txt == ""


def _content_range(doc, skip_first=True, skip_last=True):
    """Returns (from_page, to_page) for content pages, skipping covers."""
    n = len(doc)
    start = 1 if (skip_first and n > 1) else 0
    end = n - 2 if (skip_last and n > 2) else n - 1
    return start, end


def merge_pvc(capa_pdf_path, pvc_pdf_path, alm_pdf_path, pvc_total, alm_total, output_path):
    """PVC: Capa + Sintegra + W-Vetro (content only) + Resumo + Contra Capa"""
    capa_doc = fitz.open(capa_pdf_path)
    pvc_doc = fitz.open(pvc_pdf_path)
    alm_doc = fitz.open(alm_pdf_path)
    resumo_doc = update_resumo_page(capa_pdf_path, pvc_total, alm_total)

    result = fitz.open()

    # 1. EGEMAP Capa
    result.insert_pdf(capa_doc, from_page=0, to_page=0)

    # 2. Sintegra PVC content — auto-detect if it has its own cover
    pvc_start = 1 if _has_system_capa(pvc_doc) else 0
    if pvc_start < len(pvc_doc):
        result.insert_pdf(pvc_doc, from_page=pvc_start)

    # 3. W-Vetro ALM content — skip system capa and contracapa
    alm_start, alm_end = _content_range(alm_doc, skip_first=True, skip_last=True)
    if alm_start <= alm_end:
        result.insert_pdf(alm_doc, from_page=alm_start, to_page=alm_end)

    # 4. Resumo (with updated totals)
    result.insert_pdf(resumo_doc)

    # 5. EGEMAP Contra Capa
    result.insert_pdf(capa_doc, from_page=2, to_page=2)

    result.save(output_path)
    result.close()


def merge_alm(capa_pdf_path, alm_pdf_path, output_path):
    """Alumínio: Capa + W-Vetro (content only) + Contra Capa"""
    capa_doc = fitz.open(capa_pdf_path)
    alm_doc = fitz.open(alm_pdf_path)

    result = fitz.open()

    # 1. EGEMAP Capa
    result.insert_pdf(capa_doc, from_page=0, to_page=0)

    # 2. W-Vetro content — skip system capa and contracapa
    alm_start, alm_end = _content_range(alm_doc, skip_first=True, skip_last=True)
    if alm_start <= alm_end:
        result.insert_pdf(alm_doc, from_page=alm_start, to_page=alm_end)

    # 3. EGEMAP Contra Capa
    result.insert_pdf(capa_doc, from_page=2, to_page=2)

    result.save(output_path)
    result.close()


def safe_output_path(folder, name):
    """Returns a path that doesn't overwrite existing files."""
    base = Path(folder) / f"{name}.pdf"
    if not base.exists():
        return str(base)
    i = 1
    while True:
        candidate = Path(folder) / f"{name} ({i}).pdf"
        if not candidate.exists():
            return str(candidate)
        i += 1


def suggest_client_name(folder_path, pdf_path):
    """Try to extract client name from folder name or PDF filename."""
    folder_name = Path(folder_path).name
    if folder_name and folder_name not in (".", ".."):
        return folder_name
    # Fallback: extract from PDF name removing suffix
    stem = Path(pdf_path).stem
    stem = re.sub(r"\s*(PVC|ALM|pvc|alm)\s*$", "", stem, flags=re.IGNORECASE).strip()
    return stem


# ── GUI ──────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EGEMAP — Montador de Propostas")
        self.resizable(False, False)
        self.configure(bg="#f0f0f0")

        self.cfg = load_config()
        self._build_ui()
        self._apply_config()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}

        # ── Capa PDF ────────────────────────────────────────────────────────
        frm_capa = tk.LabelFrame(self, text="Arquivo de Capa/Contra Capa", bg="#f0f0f0", font=("Arial", 9, "bold"))
        frm_capa.grid(row=0, column=0, columnspan=3, sticky="ew", **pad)

        self.var_capa = tk.StringVar()
        tk.Entry(frm_capa, textvariable=self.var_capa, width=60).grid(row=0, column=0, padx=5, pady=4)
        tk.Button(frm_capa, text="Procurar...", command=self._pick_capa).grid(row=0, column=1, padx=5)

        # ── Pasta do cliente ────────────────────────────────────────────────
        frm_pasta = tk.LabelFrame(self, text="Pasta do Cliente", bg="#f0f0f0", font=("Arial", 9, "bold"))
        frm_pasta.grid(row=1, column=0, columnspan=3, sticky="ew", **pad)

        self.var_pasta = tk.StringVar()
        tk.Entry(frm_pasta, textvariable=self.var_pasta, width=60).grid(row=0, column=0, padx=5, pady=4)
        tk.Button(frm_pasta, text="Selecionar...", command=self._pick_pasta).grid(row=0, column=1, padx=5)

        # ── Tipo ────────────────────────────────────────────────────────────
        frm_tipo = tk.LabelFrame(self, text="Tipo de Orçamento", bg="#f0f0f0", font=("Arial", 9, "bold"))
        frm_tipo.grid(row=2, column=0, columnspan=3, sticky="ew", **pad)

        self.var_tipo = tk.StringVar(value="pvc")
        tk.Radiobutton(frm_tipo, text="PVC + Portas Internas (Sintegra + W-Vetro)", variable=self.var_tipo,
                       value="pvc", bg="#f0f0f0", command=self._on_tipo_change).grid(row=0, column=0, sticky="w", padx=10, pady=2)
        tk.Radiobutton(frm_tipo, text="Só Alumínio (W-Vetro)", variable=self.var_tipo,
                       value="alm", bg="#f0f0f0", command=self._on_tipo_change).grid(row=1, column=0, sticky="w", padx=10, pady=2)

        # ── Arquivos detectados ─────────────────────────────────────────────
        frm_arq = tk.LabelFrame(self, text="Arquivos na Pasta", bg="#f0f0f0", font=("Arial", 9, "bold"))
        frm_arq.grid(row=3, column=0, columnspan=3, sticky="ew", **pad)

        # PVC file
        self.lbl_pvc_file = tk.Label(frm_arq, text="Sintegra (PVC):", bg="#f0f0f0", width=18, anchor="w")
        self.lbl_pvc_file.grid(row=0, column=0, padx=5, pady=3)
        self.var_pvc_file = tk.StringVar(value="—")
        self.cmb_pvc = ttk.Combobox(frm_arq, textvariable=self.var_pvc_file, width=50, state="readonly")
        self.cmb_pvc.grid(row=0, column=1, padx=5)

        # ALM file
        self.lbl_alm_file = tk.Label(frm_arq, text="W-Vetro (ALM):", bg="#f0f0f0", width=18, anchor="w")
        self.lbl_alm_file.grid(row=1, column=0, padx=5, pady=3)
        self.var_alm_file = tk.StringVar(value="—")
        self.cmb_alm = ttk.Combobox(frm_arq, textvariable=self.var_alm_file, width=50, state="readonly")
        self.cmb_alm.grid(row=1, column=1, padx=5)

        # ── Totais ──────────────────────────────────────────────────────────
        frm_tot = tk.LabelFrame(self, text="Totais (extraídos automaticamente — edite se necessário)", bg="#f0f0f0", font=("Arial", 9, "bold"))
        frm_tot.grid(row=4, column=0, columnspan=3, sticky="ew", **pad)

        self.lbl_tot_pvc = tk.Label(frm_tot, text="Total PVC (R$):", bg="#f0f0f0", width=18, anchor="w")
        self.lbl_tot_pvc.grid(row=0, column=0, padx=5, pady=3)
        self.var_tot_pvc = tk.StringVar()
        self.ent_tot_pvc = tk.Entry(frm_tot, textvariable=self.var_tot_pvc, width=20)
        self.ent_tot_pvc.grid(row=0, column=1, padx=5)

        tk.Label(frm_tot, text="Total Madeira (R$):", bg="#f0f0f0", width=20, anchor="w").grid(row=1, column=0, padx=5, pady=3)
        self.var_tot_alm = tk.StringVar()
        self.ent_tot_alm = tk.Entry(frm_tot, textvariable=self.var_tot_alm, width=20)
        self.ent_tot_alm.grid(row=1, column=1, padx=5)

        # ── Nome do arquivo de saída ─────────────────────────────────────────
        frm_out = tk.LabelFrame(self, text="Nome do Arquivo Final", bg="#f0f0f0", font=("Arial", 9, "bold"))
        frm_out.grid(row=5, column=0, columnspan=3, sticky="ew", **pad)

        self.var_out_name = tk.StringVar()
        tk.Entry(frm_out, textvariable=self.var_out_name, width=60).grid(row=0, column=0, padx=5, pady=4)
        tk.Label(frm_out, text=".pdf", bg="#f0f0f0").grid(row=0, column=1)

        # ── Botão ────────────────────────────────────────────────────────────
        self.btn_montar = tk.Button(self, text="✦  MONTAR PROPOSTA  ✦",
                                    command=self._montar,
                                    bg="#c0392b", fg="white",
                                    font=("Arial", 11, "bold"),
                                    relief="flat", padx=20, pady=8,
                                    cursor="hand2")
        self.btn_montar.grid(row=6, column=0, columnspan=3, pady=15)

        self.lbl_status = tk.Label(self, text="", bg="#f0f0f0", fg="#27ae60", font=("Arial", 9))
        self.lbl_status.grid(row=7, column=0, columnspan=3, pady=(0, 10))

        self.columnconfigure(0, weight=1)
        self._on_tipo_change()

    def _apply_config(self):
        if "capa_pdf" in self.cfg:
            self.var_capa.set(self.cfg["capa_pdf"])

    def _pick_capa(self):
        path = filedialog.askopenfilename(title="Selecionar PDF de Capa",
                                          filetypes=[("PDF", "*.pdf")])
        if path:
            self.var_capa.set(path)
            self.cfg["capa_pdf"] = path
            save_config(self.cfg)

    def _pick_pasta(self):
        folder = filedialog.askdirectory(title="Selecionar Pasta do Cliente")
        if not folder:
            return
        self.var_pasta.set(folder)
        self._scan_folder(folder)

    def _scan_folder(self, folder):
        pdfs = find_pdfs_in_folder(folder)

        # Populate comboboxes
        pvc_names = [Path(p).name for p in pdfs["pvc"]]
        alm_names = [Path(p).name for p in pdfs["alm"]]

        self.cmb_pvc["values"] = pvc_names or ["—"]
        self.cmb_alm["values"] = alm_names or ["—"]
        self.var_pvc_file.set(pvc_names[0] if pvc_names else "—")
        self.var_alm_file.set(alm_names[0] if alm_names else "—")

        self._folder_pdfs = pdfs
        self._folder_path = folder

        # Extract totals
        if pdfs["pvc"]:
            tot = extract_total_pvc(pdfs["pvc"][0])
            self.var_tot_pvc.set(tot)

        if pdfs["alm"]:
            tot = extract_total_alm(pdfs["alm"][0])
            self.var_tot_alm.set(tot)

        # Suggest output name
        today = date.today().strftime("%d-%m-%Y")
        client = suggest_client_name(folder, pdfs["pvc"][0] if pdfs["pvc"] else (pdfs["alm"][0] if pdfs["alm"] else ""))
        self.var_out_name.set(f"Proposta Comercial {client} - {today}")

        self.lbl_status.config(text=f"Pasta carregada: {len(pdfs['pvc'])} PVC, {len(pdfs['alm'])} ALM encontrado(s).", fg="#2980b9")

    def _on_tipo_change(self):
        tipo = self.var_tipo.get()
        if tipo == "pvc":
            self.lbl_pvc_file.config(fg="black")
            self.cmb_pvc.config(state="readonly")
            self.lbl_tot_pvc.config(fg="black")
            self.ent_tot_pvc.config(state="normal")
            self.lbl_tot_alm = getattr(self, "_lbl_tot_alm_ref", None)
            self.ent_tot_alm.config(state="normal")
        else:
            self.lbl_pvc_file.config(fg="#999999")
            self.cmb_pvc.config(state="disabled")
            self.lbl_tot_pvc.config(fg="#999999")
            self.ent_tot_pvc.config(state="disabled")
            self.ent_tot_alm.config(state="normal")

    def _get_full_path(self, filename, key):
        if filename == "—" or not filename:
            return None
        folder = getattr(self, "_folder_path", None)
        if not folder:
            return None
        return str(Path(folder) / filename)

    def _montar(self):
        capa = self.var_capa.get().strip()
        pasta = getattr(self, "_folder_path", "")
        tipo = self.var_tipo.get()
        out_name = self.var_out_name.get().strip()

        if not capa or not Path(capa).exists():
            messagebox.showerror("Erro", "Selecione o arquivo PDF de Capa.")
            return
        if not pasta:
            messagebox.showerror("Erro", "Selecione a pasta do cliente.")
            return
        if not out_name:
            messagebox.showerror("Erro", "Informe o nome do arquivo de saída.")
            return

        output_path = safe_output_path(pasta, out_name)

        try:
            if tipo == "pvc":
                pvc_name = self.var_pvc_file.get()
                alm_name = self.var_alm_file.get()
                pvc_path = self._get_full_path(pvc_name, "pvc")
                alm_path = self._get_full_path(alm_name, "alm")

                if not pvc_path or not Path(pvc_path).exists():
                    messagebox.showerror("Erro", "Arquivo PVC não encontrado.")
                    return
                if not alm_path or not Path(alm_path).exists():
                    messagebox.showerror("Erro", "Arquivo ALM não encontrado.")
                    return

                pvc_total = self.var_tot_pvc.get().strip()
                alm_total = self.var_tot_alm.get().strip()

                if not pvc_total or not alm_total:
                    messagebox.showerror("Erro", "Informe os totais de PVC e Madeira.")
                    return

                merge_pvc(capa, pvc_path, alm_path, pvc_total, alm_total, output_path)

            else:  # alm only
                alm_name = self.var_alm_file.get()
                alm_path = self._get_full_path(alm_name, "alm")

                if not alm_path or not Path(alm_path).exists():
                    messagebox.showerror("Erro", "Arquivo ALM não encontrado.")
                    return

                merge_alm(capa, alm_path, output_path)

        except Exception as e:
            messagebox.showerror("Erro ao montar", str(e))
            return

        out_filename = Path(output_path).name
        self.lbl_status.config(text=f"✔ Salvo: {out_filename}", fg="#27ae60")
        messagebox.showinfo("Concluído!", f"Proposta gerada com sucesso!\n\n{output_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
