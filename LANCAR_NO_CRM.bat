@echo off
:: Manda UM arquivo pro CRM na hora, mostrando cada passo.
:: Serve pra orcamento E pra pedido -- ele ve sozinho qual e.
:: Arraste o PDF pronto para cima deste arquivo.
cd /d "%~dp0"

IF EXIST "EGEMAP-Monitor.exe" (
    EGEMAP-Monitor.exe --lancar %1
) ELSE (
    python "%~dp0monitorar.py" --lancar %1
)
