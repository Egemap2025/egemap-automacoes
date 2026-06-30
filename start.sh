#!/bin/bash
# Inicializa o Agente de Orçamento W-Vetro - Egemap

set -e

echo ""
echo "==============================="
echo " Egemap Automações — W-Vetro"
echo "==============================="
echo ""

# Verifica se o .env existe
if [ ! -f ".env" ]; then
  echo "❌ Arquivo .env não encontrado!"
  echo "   Execute: cp .env.example .env"
  echo "   Depois preencha as credenciais."
  exit 1
fi

# Verifica variáveis obrigatórias
source .env

if [ "$TELEGRAM_BOT_TOKEN" = "PREENCHER" ] || [ -z "$TELEGRAM_BOT_TOKEN" ]; then
  echo "❌ Configure TELEGRAM_BOT_TOKEN no arquivo .env"
  exit 1
fi

if [ "$ANTHROPIC_API_KEY" = "PREENCHER" ] || [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "❌ Configure ANTHROPIC_API_KEY no arquivo .env"
  exit 1
fi

# Instala dependências se necessário
if [ ! -d "node_modules" ]; then
  echo "📦 Instalando dependências..."
  npm install
fi

# Compila TypeScript
echo "🔨 Compilando..."
npm run build

echo ""
echo "✅ Agente iniciado! Envie /start no seu bot do Telegram."
echo "   (Ctrl+C para parar)"
echo ""

node dist/index.js
