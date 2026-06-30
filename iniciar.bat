@echo off
chcp 65001 >nul
title Egemap Automações - Bot W-Vetro Ativo

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║    EGEMAP AUTOMAÇÕES - Bot W-Vetro       ║
echo  ╚══════════════════════════════════════════╝
echo.
echo  Bot: @OrcamentoEgemapBot
echo.
echo  Para usar:
echo  1. Abra o Telegram
echo  2. Procure por @OrcamentoEgemapBot
echo  3. Envie /start
echo  4. Mande o PDF da planta
echo.
echo  [Nao feche esta janela enquanto quiser usar o bot]
echo  [Pressione Ctrl+C para parar]
echo  ════════════════════════════════════════════
echo.

node dist\index.js

echo.
echo  Bot encerrado.
pause
