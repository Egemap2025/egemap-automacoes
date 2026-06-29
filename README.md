# Egemap Automações

Automações para gerenciamento de orçamentos da Egemap Esquadrias.

---

## Agente do Google Drive (`drive_agent.py`)

Cria automaticamente a estrutura de pastas no Drive e faz upload dos arquivos de orçamento.

**Estrutura criada automaticamente:**
```
Pedidos e Contratos
└── 2026
    └── {Cidade}
        └── {Nome do Cliente}
            └── [arquivos de orçamento]
```

### Configuração (apenas uma vez)

**1. Instalar dependências**
```bash
pip install -r requirements.txt
```

**2. Configurar credenciais do Google**
```bash
python configurar_credenciais.py
```
> Este script abre o navegador para você autorizar o acesso ao Drive da conta `egemapesquadrias@gmail.com`.
> Após autorizar, o arquivo `token.pickle` é salvo e você não precisa fazer isso de novo.

---

### Como usar

**Criar pasta para um novo cliente:**
```bash
python drive_agent.py --cidade "Sombrio" --cliente "João Silva"
```

**Criar pasta e enviar o orçamento:**
```bash
python drive_agent.py --cidade "Criciúma" --cliente "Maria Souza" --arquivos orcamento.pdf
```

**Enviar vários arquivos e abrir a pasta no navegador:**
```bash
python drive_agent.py --cidade "Içara" --cliente "Empresa ABC" --arquivos orcamento.pdf planilha.xlsx --abrir
```

**Listar cidades já cadastradas:**
```bash
python drive_agent.py --listar-cidades
```

**Usar ano específico:**
```bash
python drive_agent.py --cidade "Araranguá" --cliente "Carlos Lima" --ano 2025 --arquivos orcamento.pdf
```

---

### Múltiplas contas (vários colaboradores)

Como a empresa usa várias contas Google com acesso à mesma pasta, cada colaborador pode autorizar com a própria conta usando `--conta`:

```bash
# Jackson autoriza com a conta dele (salva token_jackson.pickle)
python drive_agent.py --conta jackson --cidade "Criciúma" --cliente "João"

# Conta de orçamentos (salva token_orcamentos.pickle)
python drive_agent.py --conta orcamentos --cidade "Sombrio" --cliente "Maria"
```

Na primeira vez com uma `--conta` nova, abre o navegador pedindo login. Depois fica salvo automaticamente.

---

### O que o agente faz

1. **Busca a pasta do ano** (ex: `2026`) dentro de "Pedidos e Contratos" — cria se não existir
2. **Busca a pasta da cidade** dentro do ano — cria se não existir
3. **Busca a pasta do cliente** dentro da cidade — cria se não existir
4. **Faz upload dos arquivos** para a pasta do cliente
5. **Exibe o link** da pasta no Drive

> Se a pasta já existir (cliente repetido), o agente apenas adiciona os novos arquivos sem duplicar pastas.

---

### Arquivos importantes

| Arquivo | Descrição |
|---|---|
| `drive_agent.py` | Agente principal |
| `configurar_credenciais.py` | Configura o acesso ao Drive (rodar uma vez) |
| `credentials.json` | Baixado do Google Cloud Console (não commitar!) |
| `token.pickle` | Gerado automaticamente (não commitar!) |
| `requirements.txt` | Dependências Python |

> **Atenção:** Nunca compartilhe os arquivos `credentials.json` e `token.pickle`.
