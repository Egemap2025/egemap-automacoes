@echo off
setlocal enableextensions enabledelayedexpansion
title EGEMAP - Robo de Orcamentos
chcp 65001 >nul

REM =====================================================================
REM  EGEMAP - Lancador UNICO do Robo de Alteracao de Orcamentos (W-Vetro)
REM  Baixe este arquivo UMA vez. Depois, so de 2 cliques nele:
REM  ele sozinho baixa a versao mais nova do robo e roda. Sem ZIP.
REM =====================================================================

set "PASTA=%USERPROFILE%\EGEMAP_robo"
set "ARQ=%PASTA%\alterar_orcamento.py"
set "URL=https://raw.githubusercontent.com/Egemap2025/egemap-automacoes/claude/orcamento-2346-alteracao-fmwarh-7top10/alterar_orcamento.py"

if not exist "%PASTA%" mkdir "%PASTA%"

echo.
echo ==================================================
echo    EGEMAP - Robo de Alteracao de Orcamentos
echo ==================================================
echo.

REM 1) Encontra o Python (python ou py)
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY ( where py >nul 2>nul && set "PY=py" )
if not defined PY (
  echo [ERRO] Python nao encontrado neste computador.
  echo.
  echo  Instale o Python em: https://www.python.org/downloads/
  echo  IMPORTANTE: marque a opcao "Add Python to PATH" na instalacao.
  echo  Depois, rode este arquivo de novo.
  echo.
  pause
  exit /b 1
)

REM 2) Baixa a versao mais nova do robo (valida antes de substituir)
echo Buscando a versao mais nova do robo...
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; try { $ProgressPreference='SilentlyContinue'; $tmp = Join-Path $env:TEMP 'egemap_robo_novo.py'; Invoke-WebRequest -UseBasicParsing -Headers @{'Cache-Control'='no-cache';'Pragma'='no-cache'} -Uri '%URL%' -OutFile $tmp; if ((Get-Item $tmp).Length -gt 500) { Copy-Item $tmp '%ARQ%' -Force; Write-Host '   versao mais nova baixada. OK' } else { Write-Host '   download invalido - usando a copia que ja tenho.' } } catch { Write-Host '   sem internet? usando a copia que ja tenho.' }"

if not exist "%ARQ%" (
  echo.
  echo [ERRO] Nao consegui baixar o robo e nao existe copia salva ainda.
  echo Verifique a internet e tente de novo.
  echo.
  pause
  exit /b 1
)

REM 3) Garante o Playwright instalado (so na 1a vez)
%PY% -c "import playwright" 1>nul 2>nul
if errorlevel 1 (
  echo Instalando componentes ^(so na primeira vez, pode demorar um pouco^)...
  %PY% -m pip install --quiet --upgrade pip
  %PY% -m pip install --quiet playwright
)

REM 4) Roda o robo
echo.
%PY% "%ARQ%"

echo.
echo (Robo encerrado. Pode fechar esta janela.)
pause
