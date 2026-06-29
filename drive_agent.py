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
import argparse
from datetime import datetime
from pathlib import Path

# Instale com: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    import pickle
except ImportError:
    print("Dependências não instaladas. Execute:")
    print("  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    sys.exit(1)

# Escopo de acesso ao Drive
SCOPES = ["https://www.googleapis.com/auth/drive"]

# ID da pasta raiz "Pedidos e Contratos" no Google Drive
ROOT_FOLDER_ID = "1qtOmTr3KXqSFBwPJyidVcMvEvg7w86L3"

# Arquivos de autenticação (gerados pelo script de configuração)
CREDENTIALS_FILE = "credentials.json"   # baixado do Google Cloud Console
TOKEN_FILE = "token.pickle"             # gerado automaticamente na 1ª execução

# Cada colaborador pode ter seu próprio token usando --conta
# Ex: token_jackson.pickle, token_orcamentos.pickle
def _token_file(conta=None):
    if conta:
        return f"token_{conta}.pickle"
    return TOKEN_FILE


def autenticar(conta=None):
    """
    Autentica com o Google Drive e retorna o serviço.

    Se usar --conta, salva um token separado por colaborador,
    permitindo que cada um use sua própria conta do Google.
    """
    creds = None
    token_path = _token_file(conta)

    if os.path.exists(token_path):
        with open(token_path, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"Arquivo '{CREDENTIALS_FILE}' não encontrado.")
                print("Siga as instruções no README para configurar as credenciais.")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            print("Abrindo navegador para autorização...")
            if conta:
                print(f"Faça login com a conta: {conta}")
            creds = flow.run_local_server(port=0)

        with open(token_path, "wb") as f:
            pickle.dump(creds, f)

    return build("drive", "v3", credentials=creds)


def buscar_ou_criar_pasta(service, nome, parent_id):
    """
    Busca uma pasta pelo nome dentro de um parent.
    Se não existir, cria e retorna o ID.
    """
    nome_escaped = nome.replace("'", "\\'")
    query = (
        f"name = '{nome_escaped}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents "
        f"and trashed = false"
    )
    resultado = service.files().list(q=query, fields="files(id, name)").execute()
    arquivos = resultado.get("files", [])

    if arquivos:
        return arquivos[0]["id"], False  # (id, foi_criado)

    metadata = {
        "name": nome,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    pasta = service.files().create(body=metadata, fields="id").execute()
    return pasta["id"], True  # (id, foi_criado)


def fazer_upload(service, caminho_arquivo, parent_id):
    """Faz upload de um arquivo para uma pasta no Drive."""
    caminho = Path(caminho_arquivo)
    if not caminho.exists():
        print(f"  AVISO: arquivo não encontrado: {caminho_arquivo}")
        return None

    # Detectar tipo MIME pelo arquivo
    import mimetypes
    mime_type, _ = mimetypes.guess_type(str(caminho))
    mime_type = mime_type or "application/octet-stream"

    metadata = {"name": caminho.name, "parents": [parent_id]}
    media = MediaFileUpload(str(caminho), mimetype=mime_type, resumable=True)

    arquivo = (
        service.files()
        .create(body=metadata, media_body=media, fields="id, name, webViewLink")
        .execute()
    )
    return arquivo


def criar_orcamento(cidade, cliente, arquivos=None, ano=None, abrir_no_browser=False, conta=None):
    """
    Cria a estrutura de pastas para o orçamento e faz upload dos arquivos.

    Args:
        cidade:           Nome da cidade do cliente
        cliente:          Nome do cliente
        arquivos:         Lista de caminhos para upload (opcional)
        ano:              Ano da pasta (padrão: ano atual)
        abrir_no_browser: Abre a pasta do cliente no navegador após criar
        conta:            Identificador do colaborador (ex: "jackson", "orcamentos")
    """
    service = autenticar(conta=conta)
    ano = ano or str(datetime.now().year)

    print(f"\nAgente de Orçamentos - Google Drive")
    print(f"{'─' * 40}")
    print(f"Cidade:  {cidade}")
    print(f"Cliente: {cliente}")
    print(f"Ano:     {ano}")
    print(f"{'─' * 40}")

    # Pasta do Ano
    ano_id, criado = buscar_ou_criar_pasta(service, ano, ROOT_FOLDER_ID)
    print(f"{'[NOVO]' if criado else '[OK]  '} Ano: {ano}")

    # Pasta da Cidade
    cidade_id, criado = buscar_ou_criar_pasta(service, cidade, ano_id)
    print(f"{'[NOVO]' if criado else '[OK]  '} Cidade: {cidade}")

    # Pasta do Cliente
    cliente_id, criado = buscar_ou_criar_pasta(service, cliente, cidade_id)
    print(f"{'[NOVO]' if criado else '[OK]  '} Cliente: {cliente}")

    # Upload de arquivos
    if arquivos:
        print(f"\nEnviando {len(arquivos)} arquivo(s)...")
        for arquivo in arquivos:
            resultado = fazer_upload(service, arquivo, cliente_id)
            if resultado:
                print(f"  [OK] {resultado['name']}")

    # Link da pasta do cliente
    info = service.files().get(fileId=cliente_id, fields="webViewLink, name").execute()
    link = info.get("webViewLink", "")

    print(f"\nConcluído!")
    print(f"Link da pasta: {link}")

    if abrir_no_browser and link:
        import webbrowser
        webbrowser.open(link)

    return {"cliente_id": cliente_id, "cidade_id": cidade_id, "link": link}


def listar_cidades(ano=None, conta=None):
    """Lista todas as cidades cadastradas no ano informado."""
    service = autenticar(conta=conta)
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
  # Criar pasta para cliente (sem upload de arquivos)
  python drive_agent.py --cidade "Sombrio" --cliente "João Silva"

  # Criar pasta e enviar orçamento
  python drive_agent.py --cidade "Criciúma" --cliente "Maria Souza" --arquivos orcamento.pdf

  # Enviar vários arquivos e abrir a pasta no navegador
  python drive_agent.py --cidade "Içara" --cliente "Empresa ABC" \\
      --arquivos orcamento.pdf planilha.xlsx --abrir

  # Listar cidades cadastradas em 2026
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
    parser.add_argument(
        "--conta",
        metavar="NOME",
        help="Identificador do colaborador para usar conta própria (ex: jackson, orcamentos)",
    )

    args = parser.parse_args()

    if args.listar_cidades:
        listar_cidades(args.ano, conta=args.conta)
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
        conta=args.conta,
    )


if __name__ == "__main__":
    main()
