@echo off
:: Inicia o Agente de Orçamentos em segundo plano (sem janela visível)
:: Este arquivo fica na pasta de Inicialização do Windows

cd /d "%~dp0"
pythonw watcher.py
