# Egemap Automações — Orçamentos no Drive

Sobe automaticamente os PDFs de orçamento para o Google Drive assim que entram na pasta do computador.

---

## Como funciona

O agente fica rodando em segundo plano no Windows.

Quando você salva um PDF na pasta:
```
Orçamentos / Sombrio / João Silva / orcamento.pdf
```

Ele cria automaticamente no Drive e faz o upload:
```
Pedidos e Contratos / 2026 / Sombrio / João Silva / orcamento.pdf
```

Se a pasta da cidade ou do cliente já existir no Drive, só joga o arquivo dentro — não duplica nada.

---

## Configuração (só uma vez)

### 1. Instalar o Python

Baixe em [python.org/downloads](https://www.python.org/downloads/) e marque a opção **"Add Python to PATH"** durante a instalação.

### 2. Baixar as credenciais do Google

- Acesse [console.cloud.google.com](https://console.cloud.google.com/)
- Crie um projeto → Ative a **Google Drive API**
- Credenciais → Criar credencial → **ID do cliente OAuth 2.0** → App para computador
- Baixe o JSON e salve como `credentials.json` nesta pasta

### 3. Configurar a pasta de orçamentos

Abra o arquivo `config.json` e coloque o caminho correto da sua pasta:

```json
{
  "pasta_orcamentos": "C:/Users/SeuNome/Documents/Orçamentos",
  "extensoes": [".pdf"],
  "ano": "2026"
}
```

### 4. Instalar e iniciar o agente

Clique duas vezes em:
```
instalar_inicio_automatico.bat
```

Na primeira execução vai abrir o navegador pedindo login no Google — faça login normalmente com sua conta. Depois fica salvo e nunca mais pede.

**Pronto.** O agente vai iniciar sozinho toda vez que o Windows ligar.

---

## Estrutura de pastas esperada

O agente identifica cidade e cliente pela posição das pastas:

```
📁 Orçamentos          ← pasta configurada no config.json
 └── 📁 Sombrio         ← cidade
      └── 📁 João Silva  ← cliente
           └── 📄 orcamento.pdf   ← detectado → sobe pro Drive
```

---

## Arquivos

| Arquivo | O que é |
|---|---|
| `watcher.py` | O agente que monitora a pasta |
| `drive_agent.py` | Funções de criação de pasta e upload |
| `configurar_credenciais.py` | Autoriza o acesso ao Drive (opcional, o watcher faz isso automaticamente) |
| `config.json` | Caminho da pasta e configurações |
| `instalar_inicio_automatico.bat` | Instala o agente no início do Windows |
| `iniciar_agente.bat` | Inicia o agente manualmente |
| `parar_agente.bat` | Para o agente |
| `watcher.log` | Registro de tudo que o agente fez |
| `credentials.json` | Baixado do Google — **não compartilhar** |
| `token.pickle` | Gerado automaticamente — **não compartilhar** |

---

## Log de atividade

Tudo que o agente faz fica registrado em `watcher.log`:

```
2026-06-29 14:32:01  Novo arquivo detectado: orcamento.pdf
2026-06-29 14:32:02    Cidade:  Sombrio
2026-06-29 14:32:02    Cliente: João Silva
2026-06-29 14:32:03    [OK]     Pasta João Silva já existe no Drive
2026-06-29 14:32:05    [ENVIADO] orcamento.pdf
2026-06-29 14:32:05    https://drive.google.com/...
```
