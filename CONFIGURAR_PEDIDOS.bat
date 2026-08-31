@echo off
:: Escolhe a pasta dos PEDIDOS (so precisa fazer uma vez).
:: Todo PDF de pedido salvo nessa pasta vai sozinho para o card do cliente
:: no CRM, na etapa Contrato, junto do que ja esta anexado la.
cd /d "%~dp0"

IF EXIST "EGEMAP-Monitor.exe" (
    EGEMAP-Monitor.exe --pedidos
) ELSE (
    python "%~dp0monitorar.py" --pedidos
)
pause
