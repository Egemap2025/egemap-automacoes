#!/usr/bin/env python3
"""
Agente de automação para orçamentos no Google Drive.

Cria automaticamente a estrutura de pastas:
  Pedidos e Contratos / {ANO} / {CIDADE} / {CLIENTE} / [arquivos]

Uso:
  python drive_agent.py --cidade "Sombrio" --cliente "João Silva"
  python drive_agent.py --cidade "Criciúma" --cliente "Maria Souza" --arquivos orcamento.pdf planilha.xlsx
"""

import os
import sys
import pickle
import argparse
import mimetypes
from datetime import datetime
from pathlib import Path

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
except ImportError:
    print("Dependências não instaladas. Execute:")
    print("  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/drive"]
ROOT_FOLDER_ID = "1qtOmTr3KXqSFBwPJyidVcMvEvg7w86L3"  # Pedidos e Contratos
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.pickle"


def autenticar():
    """Autentica com o Google Drive. Na 1ª vez abre o navegador para login."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"Arquivo '{CREDENTIALS_FILE}' não encontrado.")
                print("Execute: python configurar_credenciais.py")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            print("Abrindo navegador para autorização no Google Drive...")
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    return build("drive", "v3", credentials=creds)


def buscar_ou_criar_pasta(service, nome, parent_id):
    """Busca uma pasta pelo nome dentro do parent. Cria se não existir."""
    nome_escaped = nome.replace("'", "\\'")
    query = (
        f"name = '{nome_escaped}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents "
        f"and trashed = false"
    )
    resultado = service.files().list(q=query, fields="files(id, name)").execute()
    existentes = resultado.get("files", [])

    if existentes:
        return existentes[0]["id"], False  # (id, foi_criado)

    metadata = {
        "name": nome,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    pasta = service.files().create(body=metadata, fields="id").execute()
    return pasta["id"], True


def fazer_upload(service, caminho_arquivo, parent_id):
    """Faz upload de um arquivo para uma pasta no Drive."""
    caminho = Path(caminho_arquivo)
    if not caminho.exists():
        print(f"  AVISO: arquivo não encontrado: {caminho_arquivo}")
        return None

    mime_type, _ = mimetypes.guess_type(str(caminho))
    mime_type = mime_type or "application/octet-stream"

    metadata = {"name": caminho.name, "parents": [parent_id]}
    media = MediaFileUpload(str(caminho), mimetype=mime_type, resumable=True)

    return (
        service.files()
        .create(body=metadata, media_body=media, fields="id, name, webViewLink")
        .execute()
    )


def criar_orcamento(cidade, cliente, arquivos=None, ano=None, abrir_no_browser=False):
    """
    Cria a estrutura de pastas e faz upload dos arquivos de orçamento.

    Estrutura: Pedidos e Contratos / {ano} / {cidade} / {cliente}
    """
    service = autenticar()
    ano = ano or str(datetime.now().year)

    print(f"\nAgente de Orçamentos - Google Drive")
    print(f"{'─' * 40}")
    print(f"Cidade:  {cidade}")
    print(f"Cliente: {cliente}")
    print(f"Ano:     {ano}")
    print(f"{'─' * 40}")

    ano_id, criado = buscar_ou_criar_pasta(service, ano, ROOT_FOLDER_ID)
    print(f"{'[NOVO] ' if criado else '[OK]   '} {ano}")

    cidade_id, criado = buscar_ou_criar_pasta(service, cidade, ano_id)
    print(f"{'[NOVO] ' if criado else '[OK]   '} {cidade}")

    cliente_id, criado = buscar_ou_criar_pasta(service, cliente, cidade_id)
    print(f"{'[NOVO] ' if criado else '[OK]   '} {cliente}")

    if arquivos:
        print(f"\nEnviando {len(arquivos)} arquivo(s)...")
        for arquivo in arquivos:
            resultado = fazer_upload(service, arquivo, cliente_id)
            if resultado:
                print(f"  [OK] {resultado['name']}")

    info = service.files().get(fileId=cliente_id, fields="webViewLink").execute()
    link = info.get("webViewLink", "")

    print(f"\nConcluído! Link da pasta:")
    print(f"  {link}")

    if abrir_no_browser and link:
        import webbrowser
        webbrowser.open(link)

    return {"cliente_id": cliente_id, "cidade_id": cidade_id, "link": link}


def listar_cidades(ano=None):
    """Lista todas as cidades cadastradas no ano informado."""
    service = autenticar()
    ano = ano or str(datetime.now().year)

    ano_id, _ = buscar_ou_criar_pasta(service, ano, ROOT_FOLDER_ID)
    query = (
        f"mimeType = 'application/vnd.google-apps.folder' "
        f"and '{ano_id}' in parents "
        f"and trashed = false"
    )
    resultado = service.files().list(q=query, fields="files(id, name)", orderBy="name").execute()
    cidades = resultado.get("files", [])

    print(f"\nCidades em {ano}:")
    for cidade in cidades:
        print(f"  - {cidade['name']}")

    return [c["name"] for c in cidades]


def main():
    parser = argparse.ArgumentParser(
        description="Agente de orçamentos – cria pastas e faz upload no Google Drive",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Criar pasta para novo cliente
  python drive_agent.py --cidade "Sombrio" --cliente "João Silva"

  # Criar pasta e enviar o orçamento
  python drive_agent.py --cidade "Criciúma" --cliente "Maria Souza" --arquivos orcamento.pdf

  # Enviar vários arquivos e abrir a pasta no navegador
  python drive_agent.py --cidade "Içara" --cliente "Empresa ABC" \\
      --arquivos orcamento.pdf planilha.xlsx --abrir

  # Listar cidades já cadastradas em 2026
  python drive_agent.py --listar-cidades

  # Usar ano específico
  python drive_agent.py --cidade "Araranguá" --cliente "Carlos Lima" --ano 2025
        """,
    )

    parser.add_argument("--cidade", help="Nome da cidade do cliente")
    parser.add_argument("--cliente", help="Nome do cliente")
    parser.add_argument("--arquivos", nargs="*", metavar="ARQUIVO", help="Arquivo(s) para upload")
    parser.add_argument("--ano", help="Ano da pasta (padrão: ano atual)")
    parser.add_argument("--abrir", action="store_true", help="Abrir a pasta no navegador após criar")
    parser.add_argument("--listar-cidades", action="store_true", help="Listar cidades do ano atual")

    args = parser.parse_args()

    if args.listar_cidades:
        listar_cidades(args.ano)
        return

    if not args.cidade or not args.cliente:
        parser.print_help()
        print("\nERRO: --cidade e --cliente são obrigatórios.")
        sys.exit(1)

    criar_orcamento(
        cidade=args.cidade,
        cliente=args.cliente,
        arquivos=args.arquivos or [],
        ano=args.ano,
        abrir_no_browser=args.abrir,
    )


if __name__ == "__main__":
    main()
