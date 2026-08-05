@echo off
cd /d "%~dp0"
title W-vetro - Configurar Login Automatico
chcp 65001 >nul 2>&1

echo.
echo  ============================================
echo   W-vetro - Configurar Login Automatico
echo  ============================================
echo.
echo  Seus dados serao salvos localmente neste
echo  computador e o sistema vai logar sozinho.
echo.

set /p USUARIO="  Usuario (ex: egemap2024): "
echo.

set /p SENHA="  Senha: "
echo.

set /p LICENCA="  Licenca (ex: 6607): "
echo.

rem Cria o arquivo .env com as credenciais
(
  echo WVETRO_USUARIO=%USUARIO%
  echo WVETRO_SENHA=%SENHA%
  echo WVETRO_LICENCA=%LICENCA%
) > "%~dp0.env"

echo.
echo  ============================================
echo   Pronto! Login automatico configurado.
echo   Pode fechar esta janela e abrir INICIAR.bat
echo  ============================================
echo.
pause
