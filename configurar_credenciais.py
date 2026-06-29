#!/usr/bin/env python3
"""
Script de configuração das credenciais do Google Drive.

Execute este script UMA VEZ para autorizar o acesso ao Drive.
Após isso, o drive_agent.py funcionará automaticamente.
"""

import os
import sys
import pickle

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except ImportError:
    print("Instalando dependências...")
    os.system(f"{sys.executable} -m pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.pickle"
ROOT_FOLDER_ID = "1qtOmTr3KXqSFBwPJyidVcMvEvg7w86L3"


def configurar():
    print("=" * 50)
    print("  Configuração do Agente de Orçamentos")
    print("=" * 50)

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"\nArquivo '{CREDENTIALS_FILE}' não encontrado!")
        print("\nPara obtê-lo:")
        print("  1. Acesse: https://console.cloud.google.com/")
        print("  2. Crie um projeto (ex: 'Egemap Automações')")
        print("  3. Ative a API: APIs > Google Drive API > Ativar")
        print("  4. Credenciais > Criar credencial > ID do cliente OAuth 2.0")
        print("  5. Tipo: 'App para computador'")
        print("  6. Baixe o JSON e salve como 'credentials.json' nesta pasta")
        print("\nDepois execute este script novamente.")
        sys.exit(1)

    print("\nIniciando autorização...")
    print("Uma janela do navegador será aberta para você autorizar o acesso.")
    print("Faça login com a conta: egemapesquadrias@gmail.com\n")

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "wb") as f:
        pickle.dump(creds, f)

    print("\nAutorização concluída! Testando conexão com o Drive...")

    service = build("drive", "v3", credentials=creds)
    pasta = service.files().get(fileId=ROOT_FOLDER_ID, fields="name, webViewLink").execute()

    print(f"\n[OK] Conectado ao Drive!")
    print(f"     Pasta raiz: {pasta['name']}")
    print(f"     Link: {pasta.get('webViewLink', '')}")
    print("\nTudo pronto! Agora você pode usar o drive_agent.py.")
    print("\nExemplo:")
    print('  python drive_agent.py --cidade "Sombrio" --cliente "João Silva"')


if __name__ == "__main__":
    configurar()
