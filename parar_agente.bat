@echo off
:: Para o agente de orçamentos se estiver rodando
echo Parando o Agente de Orcamentos...
taskkill /F /IM pythonw.exe /T >nul 2>&1
taskkill /F /IM python.exe /T >nul 2>&1
echo Agente parado.
pause
