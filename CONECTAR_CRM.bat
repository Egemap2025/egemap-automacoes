@echo off
:: Conecta o EGEMAP-Monitor ao CRM (so precisa fazer uma vez).
cd /d "%~dp0"

IF EXIST "EGEMAP-Monitor.exe" (
    EGEMAP-Monitor.exe --crm
) ELSE (
    python "%~dp0crm.py" configurar
)
pause
