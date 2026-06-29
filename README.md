# Egemap Automações

Automação para criação de pastas de orçamentos no Google Drive.

---

## Como funciona

O agente cria automaticamente a estrutura de pastas no Drive e faz upload dos arquivos:

```
Pedidos e Contratos
└── 2026
    └── {Cidade do Cliente}
        └── {Nome do Cliente}
            └── orcamento.pdf, planilha.xlsx ...
```

Se a pasta da cidade ou do cliente já existir, ele aproveita — não duplica nada.

---

## Configuração (só uma vez)

**1. Instalar dependências**
```bash
pip install -r requirements.txt
```

**2. Baixar o arquivo de credenciais do Google**

- Acesse: [console.cloud.google.com](https://console.cloud.google.com/)
- Crie um projeto → Ative a **Google Drive API**
- Credenciais → Criar credencial → **ID do cliente OAuth 2.0** → App para computador
- Baixe o JSON e salve como `credentials.json` nesta pasta

**3. Autorizar o acesso**
```bash
python configurar_credenciais.py
```
> Abre o navegador para você fazer login. Depois fica salvo automaticamente.

---

## Como usar

**Criar pasta para novo cliente:**
```bash
python drive_agent.py --cidade "Sombrio" --cliente "João Silva"
```

**Criar pasta e enviar o orçamento:**
```bash
python drive_agent.py --cidade "Criciúma" --cliente "Maria Souza" --arquivos orcamento.pdf
```

**Enviar vários arquivos de uma vez:**
```bash
python drive_agent.py --cidade "Içara" --cliente "Carlos Lima" --arquivos orcamento.pdf planilha.xlsx
```

**Criar pasta e já abrir no navegador:**
```bash
python drive_agent.py --cidade "Araranguá" --cliente "Empresa ABC" --arquivos orcamento.pdf --abrir
```

**Ver quais cidades já estão cadastradas:**
```bash
python drive_agent.py --listar-cidades
```

---

## Arquivos

| Arquivo | Descrição |
|---|---|
| `drive_agent.py` | Agente principal |
| `configurar_credenciais.py` | Configuração inicial (rodar uma vez) |
| `credentials.json` | Baixado do Google Cloud Console — **não compartilhar** |
| `token.pickle` | Gerado automaticamente — **não compartilhar** |
| `requirements.txt` | Dependências Python |
