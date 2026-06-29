#!/usr/bin/env python3
"""
Watcher de orçamentos — roda em segundo plano e monitora a pasta local.

Quando um PDF novo aparecer em:
  {pasta_orcamentos} / {Cidade} / {Nome do Cliente} / arquivo.pdf

Sobe automaticamente para o Google Drive em:
  Pedidos e Contratos / {ano} / {Cidade} / {Nome do Cliente} / arquivo.pdf
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("Instalando watchdog...")
    os.system(f"{sys.executable} -m pip install watchdog")
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

from drive_agent import autenticar, buscar_ou_criar_pasta, fazer_upload, ROOT_FOLDER_ID

CONFIG_FILE = "config.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    handlers=[
        logging.FileHandler("watcher.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def carregar_config():
    """Carrega ou cria o arquivo de configuração."""
    if not os.path.exists(CONFIG_FILE):
        pasta_padrao = str(Path.home() / "Documents" / "Orçamentos")
        config = {
            "pasta_orcamentos": pasta_padrao,
            "extensoes": [".pdf"],
            "ano": str(datetime.now().year),
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        log.info(f"Configuração criada em '{CONFIG_FILE}'.")
        log.info(f"Pasta monitorada: {pasta_padrao}")
        log.info("Edite o arquivo se quiser mudar o caminho.")

    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def arquivo_estavel(caminho, tentativas=10, intervalo=1):
    """
    Aguarda o arquivo terminar de ser gravado antes de fazer upload.
    Compara o tamanho do arquivo em intervalos até estabilizar.
    """
    tamanho_anterior = -1
    for _ in range(tentativas):
        try:
            tamanho = os.path.getsize(caminho)
            if tamanho > 0 and tamanho == tamanho_anterior:
                return True
            tamanho_anterior = tamanho
        except OSError:
            pass
        time.sleep(intervalo)
    return False


def extrair_cidade_e_cliente(caminho, pasta_raiz):
    """
    Extrai cidade e cliente com base na posição das pastas.

    Estrutura esperada:
      {pasta_raiz} / {Cidade} / {Cliente} / arquivo.pdf
                      parte[0]   parte[1]
    """
    try:
        partes = Path(caminho).relative_to(pasta_raiz).parts
        if len(partes) >= 3:
            return partes[-3], partes[-2]   # cidade, cliente
        if len(partes) == 2:
            return None, partes[-2]          # só cliente, sem cidade
    except ValueError:
        pass
    return None, None


class OrcamentoHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.pasta_raiz = Path(config["pasta_orcamentos"])
        self.extensoes = [e.lower() for e in config.get("extensoes", [".pdf"])]
        self.ano = config.get("ano", str(datetime.now().year))
        self._service = None
        self._em_processo = set()

    def _service_drive(self):
        if self._service is None:
            self._service = autenticar()
        return self._service

    def on_created(self, event):
        if event.is_directory:
            return
        caminho = event.src_path
        if Path(caminho).suffix.lower() not in self.extensoes:
            return
        if caminho in self._em_processo:
            return
        self._em_processo.add(caminho)
        try:
            self._processar(caminho)
        finally:
            self._em_processo.discard(caminho)

    def _processar(self, caminho):
        nome_arquivo = Path(caminho).name
        log.info(f"Novo arquivo detectado: {nome_arquivo}")

        if not arquivo_estavel(caminho):
            log.warning(f"  Arquivo demorou para estabilizar, pulando: {nome_arquivo}")
            return

        cidade, cliente = extrair_cidade_e_cliente(caminho, self.pasta_raiz)

        if not cidade or not cliente:
            log.warning(
                f"  Não foi possível identificar cidade/cliente para: {caminho}\n"
                f"  Estrutura esperada: Orçamentos / Cidade / Cliente / arquivo.pdf"
            )
            return

        log.info(f"  Cidade:  {cidade}")
        log.info(f"  Cliente: {cliente}")

        try:
            service = self._service_drive()

            ano_id, criado = buscar_ou_criar_pasta(service, self.ano, ROOT_FOLDER_ID)
            if criado:
                log.info(f"  [CRIADO] Pasta {self.ano} no Drive")

            cidade_id, criado = buscar_ou_criar_pasta(service, cidade, ano_id)
            if criado:
                log.info(f"  [CRIADO] Pasta {cidade} no Drive")

            cliente_id, criado = buscar_ou_criar_pasta(service, cliente, cidade_id)
            if criado:
                log.info(f"  [CRIADO] Pasta {cliente} no Drive")
            else:
                log.info(f"  [OK]     Pasta {cliente} já existe no Drive")

            resultado = fazer_upload(service, caminho, cliente_id)
            if resultado:
                log.info(f"  [ENVIADO] {resultado['name']}")
                log.info(f"  {resultado.get('webViewLink', '')}")
            log.info("")

        except Exception as e:
            log.error(f"  Erro no upload: {e}")
            self._service = None  # Força reconexão na próxima tentativa


def main():
    config = carregar_config()
    pasta = Path(config["pasta_orcamentos"])

    if not pasta.exists():
        log.error(f"Pasta não encontrada: {pasta}")
        log.error(f"Corrija o caminho no arquivo '{CONFIG_FILE}' e reinicie.")
        input("Pressione Enter para fechar...")
        sys.exit(1)

    log.info("=" * 52)
    log.info("  Agente de Orçamentos — Drive")
    log.info("=" * 52)
    log.info(f"Monitorando: {pasta}")
    log.info(f"Ano atual:   {config['ano']}")
    log.info("Aguardando novos arquivos...")
    log.info("")

    handler = OrcamentoHandler(config)
    observer = Observer()
    observer.schedule(handler, str(pasta), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(5)
            # Atualiza o ano automaticamente na virada
            ano_atual = str(datetime.now().year)
            if handler.ano != ano_atual:
                handler.ano = ano_atual
                log.info(f"Ano atualizado para {ano_atual}")
    except KeyboardInterrupt:
        observer.stop()
        log.info("Agente encerrado.")

    observer.join()


if __name__ == "__main__":
    main()
