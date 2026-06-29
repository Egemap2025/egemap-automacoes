#!/usr/bin/env python3
"""
EGEMAP - Monitor de Pasta de Orçamentos
Monitora a pasta principal e monta propostas automaticamente
quando arquivos PVC ou ALM são salvos.
"""

import sys
import time
import logging
import json
import os
from pathlib import Path
from datetime import date, datetime

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("ERRO: biblioteca 'watchdog' nao instalada.")
    print("Execute: pip install watchdog")
    input("Pressione Enter para sair...")
    sys.exit(1)

try:
    import fitz
except ImportError:
    print("ERRO: biblioteca 'pymupdf' nao instalada.")
    print("Execute: pip install pymupdf")
    input("Pressione Enter para sair...")
    sys.exit(1)

# Import funções do montador principal
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))
from montar_orcamento import (
    merge_pvc, merge_alm, find_pdfs_in_folder,
    extract_total_pvc, extract_total_alm,
    safe_output_path, load_config, save_config,
    suggest_client_name,
)

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
log = logging.getLogger("egemap")


# ── Monitor ──────────────────────────────────────────────────────────────────

WAIT_SECONDS = 4  # aguarda N segundos após o último arquivo antes de processar


class PropostaHandler(FileSystemEventHandler):
    def __init__(self, capa_pdf):
        self.capa_pdf = capa_pdf
        # folder_path -> timestamp do último evento
        self._pending: dict[str, float] = {}

    def _is_target(self, path: Path) -> bool:
        if path.suffix.lower() != ".pdf":
            return False
        name = path.name.upper()
        return "PVC" in name or "ALM" in name

    def _queue(self, path: Path):
        folder = str(path.parent)
        self._pending[folder] = time.time()

    def on_created(self, event):
        if not event.is_directory:
            self._queue(Path(event.src_path))

    def on_modified(self, event):
        if not event.is_directory:
            p = Path(event.src_path)
            if self._is_target(p):
                self._queue(p)

    def on_moved(self, event):
        if not event.is_directory:
            self._queue(Path(event.dest_path))

    def tick(self):
        """Chamado periodicamente — processa pastas que aguardaram tempo suficiente."""
        now = time.time()
        ready = [f for f, t in list(self._pending.items()) if now - t >= WAIT_SECONDS]
        for folder in ready:
            del self._pending[folder]
            try:
                self._process_folder(folder)
            except Exception as e:
                log.error(f"Erro ao processar {folder}: {e}")

    def _process_folder(self, folder: str):
        pdfs = find_pdfs_in_folder(folder)

        has_pvc = bool(pdfs["pvc"])
        has_alm = bool(pdfs["alm"])

        if not has_pvc and not has_alm:
            return

        today = date.today().strftime("%d-%m-%Y")
        client = suggest_client_name(
            folder,
            pdfs["pvc"][0] if pdfs["pvc"] else (pdfs["alm"][0] if pdfs["alm"] else ""),
        )
        out_name = f"Proposta Comercial {client} - {today}"
        output_path = safe_output_path(folder, out_name)

        if has_pvc and has_alm:
            pvc_path = pdfs["pvc"][0]
            alm_path = pdfs["alm"][0]

            pvc_total = extract_total_pvc(pvc_path)
            alm_total = extract_total_alm(alm_path)

            if not pvc_total or not alm_total:
                log.warning(
                    f"[{client}] Nao foi possivel extrair totais automaticamente. "
                    f"PVC={pvc_total or 'N/A'}  ALM={alm_total or 'N/A'}. "
                    f"Use o programa manual para informar os valores."
                )
                return

            log.info(
                f"[{client}] PVC+ALM detectados → montando proposta completa... "
                f"(PVC R${pvc_total}  +  MAD R${alm_total})"
            )
            merge_pvc(self.capa_pdf, pvc_path, alm_path, pvc_total, alm_total, output_path)
            log.info(f"[{client}] ✔ Salvo: {Path(output_path).name}")

        elif has_alm and not has_pvc:
            alm_path = pdfs["alm"][0]
            log.info(f"[{client}] Somente ALM detectado → montando proposta de alumínio...")
            merge_alm(self.capa_pdf, alm_path, output_path)
            log.info(f"[{client}] ✔ Salvo: {Path(output_path).name}")

        elif has_pvc and not has_alm:
            # PVC sozinho — aguarda o ALM
            log.info(
                f"[{client}] Arquivo PVC encontrado. Aguardando ALM (portas internas)... "
                f"Salve o arquivo ALM na mesma pasta para montar automaticamente."
            )


# ── Setup inicial ─────────────────────────────────────────────────────────────

def _pick_file_dialog(title, filetypes=None):
    """Abre janela gráfica para selecionar arquivo."""
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(title=title, filetypes=filetypes or [("Todos", "*.*")])
    root.destroy()
    return path


def _pick_folder_dialog(title):
    """Abre janela gráfica para selecionar pasta."""
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askdirectory(title=title)
    root.destroy()
    return path


def configurar():
    """Configura capa PDF e pasta de orçamentos (abre janelas de seleção)."""
    cfg = load_config()

    print("=" * 60)
    print("  EGEMAP - Monitor de Propostas")
    print("=" * 60)

    # ── Capa PDF ────────────────────────────────────────────────────────────
    capa = cfg.get("capa_pdf", "")
    if capa and Path(capa).exists():
        print(f"\nCapa PDF: {capa}")
        resp = input("Pressione Enter para manter ou 'T' para trocar: ").strip().upper()
        if resp == "T":
            capa = ""

    if not capa or not Path(capa).exists():
        print("\nUma janela vai abrir — selecione o arquivo PDF de Capa (Capa_Orcamento_1.pdf)...")
        input("Pressione Enter para abrir a janela de seleção...")
        capa = _pick_file_dialog(
            title="Selecionar PDF de Capa/Contra Capa",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")],
        )
        if not capa:
            print("Nenhum arquivo selecionado. Encerrando.")
            input("Pressione Enter para sair...")
            sys.exit(1)

    cfg["capa_pdf"] = capa
    save_config(cfg)
    print(f"Capa PDF: {capa}")

    # ── Pasta de orçamentos ─────────────────────────────────────────────────
    pasta = cfg.get("pasta_orcamentos", "")
    if pasta and Path(pasta).exists():
        print(f"\nPasta monitorada: {pasta}")
        resp = input("Pressione Enter para manter ou 'T' para trocar: ").strip().upper()
        if resp == "T":
            pasta = ""

    if not pasta or not Path(pasta).exists():
        print("\nUma janela vai abrir — selecione a pasta principal de Orçamentos...")
        input("Pressione Enter para abrir a janela de seleção...")
        pasta = _pick_folder_dialog(title="Selecionar Pasta Principal de Orçamentos")
        if not pasta:
            print("Nenhuma pasta selecionada. Encerrando.")
            input("Pressione Enter para sair...")
            sys.exit(1)

    cfg["pasta_orcamentos"] = pasta
    save_config(cfg)
    print(f"Pasta: {pasta}")

    return capa, pasta


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    capa, pasta = configurar()

    handler = PropostaHandler(capa_pdf=capa)
    observer = Observer()
    observer.schedule(handler, pasta, recursive=True)
    observer.start()

    print()
    print("=" * 60)
    print(f"  Monitorando: {pasta}")
    print(f"  Capa PDF: {Path(capa).name}")
    print()
    print("  Regras:")
    print("   • Arquivo *PVC*.pdf + *ALM*.pdf → Proposta completa (com Resumo)")
    print("   • Arquivo *ALM*.pdf (sem PVC)   → Proposta de alumínio")
    print("   • Arquivo *PVC*.pdf (sem ALM)   → Aguarda o ALM")
    print()
    print("  Pressione Ctrl+C para encerrar.")
    print("=" * 60)
    print()

    try:
        while True:
            handler.tick()
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Encerrando monitor...")
        observer.stop()

    observer.join()
    print("\nMonitor encerrado.")


if __name__ == "__main__":
    main()
