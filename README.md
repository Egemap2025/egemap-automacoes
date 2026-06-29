# Egemap — Agente de Orçamentos no Drive

Sobe automaticamente os PDFs de orçamento para o Google Drive assim que entram na pasta do computador. Roda em segundo plano, sem precisar abrir nada.

---

## Como funciona

Você salva o PDF na pasta do computador normalmente:
```
Orçamentos / Sombrio / João Silva / orcamento.pdf
```

O agente detecta em segundos e cria automaticamente no Drive:
```
Pedidos e Contratos / 2026 / Sombrio / João Silva / orcamento.pdf
```

Se a pasta do cliente já existir no Drive, só joga o arquivo lá dentro — não duplica nada.

---

## Instalação (só uma vez)

### Passo 1 — Instalar o Python

Baixe em **[python.org/downloads](https://www.python.org/downloads/)**

> Durante a instalação, marque obrigatoriamente: **"Add Python to PATH"**

---

### Passo 2 — Baixar as credenciais do Google

Precisa baixar um arquivo do Google que permite ao agente acessar o seu Drive.

1. Acesse **[console.cloud.google.com](https://console.cloud.google.com/)**
2. Clique em **"Selecionar projeto"** → **"Novo projeto"**
   - Nome: `Egemap` → clique em **Criar**
3. No menu lateral: **APIs e Serviços → Biblioteca**
   - Pesquise `Google Drive API` → clique nela → **Ativar**
4. **APIs e Serviços → Credenciais → Criar credencial**
   - Escolha: **ID do cliente OAuth 2.0**
   - Tipo de aplicativo: **Aplicativo para computador**
   - Nome: `Agente Orçamentos` → **Criar**
5. Clique em **Baixar JSON** → renomeie o arquivo para `credentials.json`
6. Salve o `credentials.json` **dentro da pasta deste projeto**

---

### Passo 3 — Instalar o agente

Clique duas vezes em:
```
instalar_inicio_automatico.bat
```

O que vai acontecer:
- Instala as dependências Python automaticamente
- Pergunta o caminho da sua pasta de orçamentos no computador
- Abre o navegador para fazer login no Google (uma única vez)
- Configura o agente para iniciar junto com o Windows
- Inicia o agente imediatamente

---

### Passo 4 — Testar

Clique duas vezes em:
```
testar_agente.bat
```

Se aparecer **"Tudo funcionando!"** está pronto. Ele cria uma pasta `_TESTE_AGENTE` no Drive só para confirmar — pode apagar depois.

---

## Uso no dia a dia

Não precisa fazer nada. O agente fica rodando invisível em segundo plano.

Basta salvar o PDF na estrutura correta de pastas:

```
📁 Orçamentos              ← sua pasta configurada
 └── 📁 Sombrio            ← cidade
      └── 📁 João Silva    ← nome do cliente
           └── 📄 orcamento.pdf   ← arquivo detectado → vai pro Drive
```

O Drive recebe na hora:
```
Pedidos e Contratos / 2026 / Sombrio / João Silva / orcamento.pdf
```

---

## Acompanhar o que o agente fez

Abra o arquivo `watcher.log` — ele registra tudo:

```
2026-06-29 14:32  Novo arquivo detectado: orcamento.pdf
2026-06-29 14:32    Cidade:  Sombrio
2026-06-29 14:32    Cliente: João Silva
2026-06-29 14:32    [OK]     Pasta João Silva já existe no Drive
2026-06-29 14:32    [ENVIADO] orcamento.pdf
```

---

## Arquivos do projeto

| Arquivo | O que faz |
|---|---|
| `watcher.py` | O agente que monitora a pasta |
| `drive_agent.py` | Funções de Drive (não executar direto) |
| `configurar_credenciais.py` | Configuração inicial |
| `config.json` | Caminho da pasta e configurações |
| `instalar_inicio_automatico.bat` | **Instalação — executar uma vez** |
| `testar_agente.bat` | **Teste — confirmar que funciona** |
| `iniciar_agente.bat` | Iniciar manualmente se precisar |
| `parar_agente.bat` | Parar o agente |
| `watcher.log` | Registro de atividade |
| `credentials.json` | Baixado do Google — **não compartilhar** |
| `token.pickle` | Gerado automaticamente — **não compartilhar** |
