#!/usr/bin/env python3
"""
Configuração inicial — executa UMA VEZ antes de usar o agente.

O que este script faz:
  1. Pergunta qual é a pasta de orçamentos no seu computador
  2. Salva isso no config.json
  3. Abre o navegador para você autorizar o acesso ao Google Drive
  4. Testa a conexão
"""

import os
import sys
import json
import pickle
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request
except ImportError:
    print("Instalando dependências do Google...")
    os.system(f"{sys.executable} -m pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib watchdog")
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.pickle"
CONFIG_FILE = "config.json"
ROOT_FOLDER_ID = "1qtOmTr3KXqSFBwPJyidVcMvEvg7w86L3"  # Pedidos e Contratos


def configurar_pasta():
    """Pergunta e salva o caminho da pasta de orçamentos."""
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, encoding="utf-8") as f:
            config = json.load(f)

    pasta_atual = config.get("pasta_orcamentos", "")
    placeholder = "SeuNome" in pasta_atual or not pasta_atual

    print("\n─── PASSO 1: Pasta de orçamentos ───")
    if pasta_atual and not placeholder:
        print(f"Pasta configurada: {pasta_atual}")
        resposta = input("Quer manter essa pasta? (Enter para sim / N para mudar): ").strip().lower()
        if resposta != "n":
            return pasta_atual

    print("\nDigite o caminho completo da pasta onde ficam os orçamentos no seu computador.")
    print("Exemplo: C:\\Users\\Joao\\Documents\\Orcamentos")
    print()

    while True:
        pasta = input("Caminho da pasta: ").strip().strip('"')
        if not pasta:
            print("Por favor, informe o caminho.")
            continue
        pasta_path = Path(pasta)
        if not pasta_path.exists():
            criar = input(f"A pasta '{pasta}' não existe. Criar agora? (S/N): ").strip().lower()
            if criar == "s":
                pasta_path.mkdir(parents=True, exist_ok=True)
                print(f"Pasta criada: {pasta}")
            else:
                continue
        break

    from datetime import datetime
    config["pasta_orcamentos"] = str(pasta_path).replace("\\", "/")
    config.setdefault("extensoes", [".pdf"])
    config.setdefault("ano", str(datetime.now().year))

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"[OK] Pasta salva: {pasta_path}")
    return str(pasta_path)


def autorizar_drive():
    """Abre o navegador para autorizar o acesso ao Google Drive."""
    print("\n─── PASSO 2: Autorização do Google Drive ───")

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"\nArquivo '{CREDENTIALS_FILE}' não encontrado nesta pasta!")
        print("\nComo baixar:")
        print("  1. Acesse: https://console.cloud.google.com/")
        print("  2. Crie um projeto (pode chamar de 'Egemap')")
        print("  3. Menu esquerdo → APIs e Serviços → Biblioteca")
        print("     Pesquise 'Google Drive API' e clique em Ativar")
        print("  4. APIs e Serviços → Credenciais → Criar credencial")
        print("     Escolha: ID do cliente OAuth 2.0")
        print("     Tipo: Aplicativo para computador")
        print("  5. Baixe o JSON e renomeie para 'credentials.json'")
        print(f"     Salve na mesma pasta deste arquivo:")
        print(f"     {os.path.abspath('.')}")
        print("\nDepois execute este script novamente.")
        input("\nPressione Enter para fechar...")
        sys.exit(1)

    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if creds and creds.valid:
        print("[OK] Já autorizado anteriormente.")
        return creds

    if creds and creds.expired and creds.refresh_token:
        print("Renovando autorização...")
        creds.refresh(Request())
    else:
        print("\nUma janela do navegador vai abrir.")
        print("Faça login com sua conta Google e clique em Permitir.\n")
        input("Pressione Enter quando estiver pronto...")
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "wb") as f:
        pickle.dump(creds, f)

    return creds


def testar_conexao(creds):
    """Verifica que a pasta Pedidos e Contratos está acessível."""
    print("\n─── PASSO 3: Testando conexão ───")
    service = build("drive", "v3", credentials=creds)
    pasta = service.files().get(fileId=ROOT_FOLDER_ID, fields="name").execute()
    print(f"[OK] Conectado ao Drive!")
    print(f"     Pasta encontrada: {pasta['name']}")


def main():
    print("=" * 52)
    print("  Configuração do Agente de Orçamentos")
    print("=" * 52)

    configurar_pasta()
    creds = autorizar_drive()
    testar_conexao(creds)

    print("\n" + "=" * 52)
    print("  Tudo configurado!")
    print("=" * 52)
    print("\nO agente está pronto para uso.")
    print("Agora execute 'instalar_inicio_automatico.bat'")
    print("para que ele inicie junto com o Windows.")
    input("\nPressione Enter para fechar...")


if __name__ == "__main__":
    main()
