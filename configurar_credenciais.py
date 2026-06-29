#!/usr/bin/env python3
"""
Configuração inicial do acesso ao Google Drive.
Execute este script UMA VEZ. Depois o drive_agent.py funciona sozinho.
"""

import os
import sys
import pickle

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError:
    os.system(f"{sys.executable} -m pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    from google_auth_oauthlib.flow import InstalledAppFlow
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
        print("\nComo obter:")
        print("  1. Acesse: https://console.cloud.google.com/")
        print("  2. Crie um projeto (ex: 'Egemap Automações')")
        print("  3. Menu lateral > APIs e Serviços > Biblioteca")
        print("     Pesquise 'Google Drive API' e clique em Ativar")
        print("  4. APIs e Serviços > Credenciais > Criar credencial")
        print("     Escolha: ID do cliente OAuth 2.0")
        print("     Tipo de aplicativo: App para computador")
        print("  5. Baixe o arquivo JSON e salve como 'credentials.json'")
        print("     nesta mesma pasta")
        print("\nDepois execute este script novamente.")
        sys.exit(1)

    print("\nUma janela do navegador vai abrir para você fazer login.")
    print("Entre com a sua conta do Google normalmente.\n")

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "wb") as f:
        pickle.dump(creds, f)

    print("\nTestando conexão com o Drive...")
    service = build("drive", "v3", credentials=creds)
    pasta = service.files().get(fileId=ROOT_FOLDER_ID, fields="name").execute()

    print(f"\n[OK] Conectado! Pasta encontrada: {pasta['name']}")
    print("\nPronto! Agora use o drive_agent.py normalmente:")
    print('  python drive_agent.py --cidade "Sombrio" --cliente "João Silva"')


if __name__ == "__main__":
    configurar()
