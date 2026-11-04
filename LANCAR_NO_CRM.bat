@echo off
:: Manda UMA proposta pro CRM na hora, mostrando cada passo.
:: Arraste o PDF da proposta pronta para cima deste arquivo.
cd /d "%~dp0"

IF EXIST "EGEMAP-Monitor.exe" (
    EGEMAP-Monitor.exe --lancar %1
) ELSE (
    python "%~dp0monitorar.py" --lancar %1
)
