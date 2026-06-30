# Egemap Automações

Agente de orçamento automático para W-Vetro via Telegram.

Você envia a planta baixa em PDF pelo Telegram → a IA analisa → preenche o orçamento no W-Vetro → você só confere.

## Fluxo

```
Você (Telegram) → PDF da planta
                       ↓
              IA analisa janelas/portas
                       ↓
           Aplica regras Egemap (Linha 25)
                       ↓
         Gera relatório Excel (quantitativos)
                       ↓
        Preenche orçamento no W-Vetro (Playwright)
                       ↓
     Você recebe resumo + Excel no Telegram ✅
```

## Especificações aplicadas automaticamente

| Ambiente | Esquadria | Vidro | Extra |
|---|---|---|---|
| Dormitórios | Linha 25 Branco | Temperado 8mm | Persiana com motor |
| Banheiros | Maxim-Ar Linha 25 | Mini Boreal 4mm | — |
| Sala / Cozinha / Outros | Linha 25 Branco | Temperado 6mm | — |
| Portas | Linha 25 Branco | Temperado 8mm | — |

## Instalação

### 1. Pré-requisitos

- Node.js 18 ou superior
- npm

### 2. Instalar dependências

```bash
npm install
npm run setup   # instala o Chromium para o Playwright
```

### 3. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` e preencha:

| Variável | Descrição | Onde obter |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Token do bot Telegram | Fale com @BotFather no Telegram |
| `ANTHROPIC_API_KEY` | Chave da API Claude | console.anthropic.com/settings/keys |
| `WVETRO_URL` | URL do W-Vetro | Geralmente https://app.wvetro.com.br |
| `WVETRO_EMAIL` | Seu login no W-Vetro | — |
| `WVETRO_SENHA` | Sua senha no W-Vetro | — |

### 4. Criar o Bot no Telegram

1. Abra o Telegram e procure por **@BotFather**
2. Envie `/newbot`
3. Escolha um nome e um username para o bot
4. Copie o token e cole no `.env` em `TELEGRAM_BOT_TOKEN`

### 5. Iniciar

```bash
# Desenvolvimento (com reload automático)
npm run dev

# Produção
npm run build
npm start
```

## Uso

1. Abra o Telegram e inicie uma conversa com seu bot
2. Envie `/start` para ver as instruções
3. Envie o PDF da planta baixa
4. Aguarde 1-3 minutos
5. Receba o resumo de quantitativos + arquivo Excel + confirmação do W-Vetro

## Depuração do W-Vetro

Se a automação do W-Vetro não funcionar na primeira vez, ative o modo debug:

```env
WVETRO_DEBUG=true
```

Screenshots automáticos de cada etapa são salvos em `outputs/screenshots/`.

## Estrutura do projeto

```
src/
├── index.ts
├── bot/telegram.ts                   # Bot Telegram
├── agents/wvetro-budget/
│   ├── index.ts                      # Orquestrador
│   ├── analyzer.ts                   # IA analisa a planta (Claude)
│   ├── rules.ts                      # Regras de produtos Egemap
│   ├── report.ts                     # Relatório Excel
│   └── automator.ts                  # Automação W-Vetro (Playwright)
└── utils/logger.ts
```