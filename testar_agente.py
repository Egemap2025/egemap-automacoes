#!/usr/bin/env python3
"""
Teste do agente — cria uma pasta de teste no Drive para confirmar que tudo funciona.
Execute depois de configurar para confirmar que o agente está operacional.
"""

import os
import sys
import json
from pathlib import Path

from drive_agent import autenticar, buscar_ou_criar_pasta, ROOT_FOLDER_ID

CONFIG_FILE = "config.json"


def main():
    print("=" * 52)
    print("  Teste do Agente de Orçamentos")
    print("=" * 52)

    # Verificar config
    if not os.path.exists(CONFIG_FILE):
        print("[ERRO] config.json não encontrado. Execute configurar_credenciais.py primeiro.")
        input("Pressione Enter para fechar...")
        sys.exit(1)

    with open(CONFIG_FILE, encoding="utf-8") as f:
        config = json.load(f)

    pasta_local = Path(config.get("pasta_orcamentos", ""))
    ano = config.get("ano", "2026")

    print(f"\nPasta local:  {pasta_local}")
    print(f"Ano no Drive: {ano}")

    # Verificar pasta local
    print(f"\n[1] Verificando pasta local...")
    if pasta_local.exists():
        print(f"    [OK] Pasta existe: {pasta_local}")
    else:
        print(f"    [AVISO] Pasta não encontrada: {pasta_local}")

    # Testar conexão com Drive
    print(f"\n[2] Testando conexão com o Google Drive...")
    try:
        service = autenticar()
        pasta_root = service.files().get(fileId=ROOT_FOLDER_ID, fields="name").execute()
        print(f"    [OK] Conectado → {pasta_root['name']}")
    except Exception as e:
        print(f"    [ERRO] Falha na conexão: {e}")
        input("Pressione Enter para fechar...")
        sys.exit(1)

    # Criar pasta de teste no Drive
    print(f"\n[3] Criando pasta de teste no Drive...")
    try:
        ano_id, criado = buscar_ou_criar_pasta(service, ano, ROOT_FOLDER_ID)
        print(f"    [OK] Pasta {ano}")

        cidade_id, criado = buscar_ou_criar_pasta(service, "_TESTE_AGENTE", ano_id)
        print(f"    [OK] Pasta _TESTE_AGENTE {'(criada agora)' if criado else '(já existia)'}")

        cliente_id, criado = buscar_ou_criar_pasta(service, "Verificacao", cidade_id)
        info = service.files().get(fileId=cliente_id, fields="webViewLink").execute()
        print(f"    [OK] Pasta Verificacao criada")
        print(f"    Link: {info.get('webViewLink', '')}")

    except Exception as e:
        print(f"    [ERRO] {e}")
        input("Pressione Enter para fechar...")
        sys.exit(1)

    print("\n" + "=" * 52)
    print("  Tudo funcionando!")
    print("=" * 52)
    print("\nO agente está pronto.")
    print("Você pode apagar a pasta '_TESTE_AGENTE' do Drive manualmente.")
    print("\nA partir de agora, qualquer PDF que você salvar em:")
    print(f"  {pasta_local} / {{Cidade}} / {{Cliente}} / arquivo.pdf")
    print("\nserá enviado automaticamente para o Drive.")
    input("\nPressione Enter para fechar...")


if __name__ == "__main__":
    main()
