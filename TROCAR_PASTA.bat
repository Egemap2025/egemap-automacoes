@echo off
:: Troca a pasta de orcamentos que o monitor vigia.
:: Ele vigia a pasta escolhida E TUDO que estiver dentro dela.
:: Nao mexe na Capa nem na pasta de pedidos.
cd /d "%~dp0"

IF EXIST "EGEMAP-Monitor.exe" (
    EGEMAP-Monitor.exe --pasta
) ELSE (
    python "%~dp0monitorar.py" --pasta
)
pause
