@echo off
:: Faxina nas pastas de orcamento do Google Drive: junta as pastas repetidas
:: (ex.: "Passo De Torres" com "Passo de Torres") e tira as copias.
:: Mostra tudo o que vai fazer ANTES e so mexe se voce confirmar digitando 1.
cd /d "%~dp0"

IF EXIST "EGEMAP-Monitor.exe" (
    EGEMAP-Monitor.exe --limpar-drive
) ELSE (
    python "%~dp0limpar_drive.py"
)
pause
