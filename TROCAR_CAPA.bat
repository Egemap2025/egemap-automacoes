@echo off
:: Troca o PDF de Capa usado nas propostas.
:: Serve quando a Capa mudou de lugar, de nome, ou quando o layout foi refeito.
:: Nao mexe na pasta de orcamentos nem na pasta de pedidos.
cd /d "%~dp0"

IF EXIST "EGEMAP-Monitor.exe" (
    EGEMAP-Monitor.exe --capa
) ELSE (
    python "%~dp0monitorar.py" --capa
)
pause
