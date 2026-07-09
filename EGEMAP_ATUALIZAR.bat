@echo off
chcp 65001 >nul 2>&1
title Egemap - Atualizando agente

echo.
echo  =============================================
echo    Egemap - Atualizando agente
echo  =============================================
echo.
echo  Novo comportamento:
echo    - Estrutura: 2026 / Cidade / Cliente / PDF
echo    - Somente PDFs com "Proposta Comercial" no nome
echo    - Arquivos ja existentes NAO serao enviados
echo    - Apenas novos a partir de agora
echo.

set DESTINO=%USERPROFILE%\EgemapDrive

if not exist "%DESTINO%\rclone.exe" (
    echo  [ERRO] Agente nao encontrado. Execute EGEMAP_INSTALAR.bat primeiro.
    pause & exit /b 1
)

echo  [1/4] Parando agente antigo...
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { $_.CommandLine -like '*watcher.ps1*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
timeout /t 2 /nobreak >nul
echo        OK.

echo  [2/4] Instalando novo agente...
set B64FILE=%TEMP%\watcher_b64.txt
(
echo cGFyYW0oW3N0cmluZ10kQ29uZmlnID0gIiRQU1NjcmlwdFJvb3RcY29uZmlnLmpzb24iKQoKJGNm
echo ZyAgICA9IEdldC1Db250ZW50ICRDb25maWcgLVJhdyB8IENvbnZlcnRGcm9tLUpzb24KJHBhc3Rh
echo ICA9ICRjZmcucGFzdGFfb3JjYW1lbnRvcy5UcmltRW5kKCIvXCIpCiRyY2xvbmUgPSAiJFBTU2Ny
echo aXB0Um9vdFxyY2xvbmUuZXhlIgokY29uZiAgID0gIiRQU1NjcmlwdFJvb3RccmNsb25lLmNvbmYi
echo CiRsb2cgICAgPSAiJFBTU2NyaXB0Um9vdFx3YXRjaGVyLmxvZyIKJHZpc3RvcyA9ICIkUFNTY3Jp
echo cHRSb290XGVudmlhZG9zLmpzb24iCgpmdW5jdGlvbiBMb2coJG0pIHsKICAgICRsID0gIiQoR2V0
echo LURhdGUgLWYgJ3l5eXktTU0tZGQgSEg6bW0nKSAgJG0iCiAgICBBZGQtQ29udGVudCAkbG9nICRs
echo IC1FbmNvZGluZyBVVEY4CiAgICBXcml0ZS1Ib3N0ICRsCn0KCmZ1bmN0aW9uIEVudmlhZG9zIHsK
echo ICAgIGlmIChUZXN0LVBhdGggJHZpc3RvcykgewogICAgICAgIHRyeSB7IHJldHVybiAoR2V0LUNv
echo bnRlbnQgJHZpc3RvcyAtUmF3IHwgQ29udmVydEZyb20tSnNvbiAtQXNIYXNodGFibGUpIH0gY2F0
echo Y2gge30KICAgIH0KICAgIHJldHVybiBAe30KfQoKZnVuY3Rpb24gU2FsdmFyKCRoKSB7ICRoIHwg
echo Q29udmVydFRvLUpzb24gfCBTZXQtQ29udGVudCAkdmlzdG9zIC1FbmNvZGluZyBVVEY4IH0KCmlm
echo ICgtbm90IChUZXN0LVBhdGggJHBhc3RhKSkgIHsgTG9nICJFUlJPOiBwYXN0YSBuYW8gZW5jb250
echo cmFkYTogJHBhc3RhIjsgUmVhZC1Ib3N0ICJFbnRlciBwYXJhIGZlY2hhciI7IGV4aXQgMSB9Cmlm
echo ICgtbm90IChUZXN0LVBhdGggJHJjbG9uZSkpIHsgTG9nICJFUlJPOiByY2xvbmUuZXhlIGF1c2Vu
echo dGUuIFJvZGUgRUdFTUFQX0lOU1RBTEFSLmJhdCI7IFJlYWQtSG9zdCAiRW50ZXIgcGFyYSBmZWNo
echo YXIiOyBleGl0IDEgfQoKTG9nICI9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09
echo PT09PT09PT09PT09PT09PT09IgpMb2cgIiAgQWdlbnRlIEVnZW1hcCAtIERyaXZlIgpMb2cgIj09
echo PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0iCkxv
echo ZyAiTW9uaXRvcmFuZG86ICRwYXN0YSIKTG9nICJFc3RydXR1cmE6ICAgT3JjYW1lbnRvcyAvIDIw
echo MjYgLyBDaWRhZGUgLyBDbGllbnRlIC8gUERGIgpMb2cgIiIKCiRvayA9IEVudmlhZG9zCgojIE5h
echo IHByaW1laXJhIGV4ZWN1Y2FvIChvdSBhcG9zIGF0dWFsaXphY2FvKTogbWFyY2EgYXJxdWl2b3Mg
echo ZXhpc3RlbnRlcyBjb21vIGphIHZpc3RvcyBzZW0gZW52aWFyCmlmICgkb2suQ291bnQgLWVxIDAp
echo IHsKICAgIExvZyAiSW5pY2lhbGl6YW5kbzogcmVnaXN0cmFuZG8gYXJxdWl2b3MgZXhpc3RlbnRl
echo cyAobmFvIHNlcmFvIGVudmlhZG9zKS4uLiIKICAgIEdldC1DaGlsZEl0ZW0gLVBhdGggJHBhc3Rh
echo IC1GaWx0ZXIgIioucGRmIiAtUmVjdXJzZSAtRXJyb3JBY3Rpb24gU2lsZW50bHlDb250aW51ZSB8
echo IEZvckVhY2gtT2JqZWN0IHsKICAgICAgICAkb2tbJF8uRnVsbE5hbWVdID0gImlnbm9yYWRvIgog
echo ICAgfQogICAgU2FsdmFyICRvawogICAgTG9nICJQcm9udG8uIE1vbml0b3JhbmRvIGFwZW5hcyBh
echo cnF1aXZvcyBub3ZvcyBhIHBhcnRpciBkZSBhZ29yYS4iCiAgICBMb2cgIiIKfQoKd2hpbGUgKCR0
echo cnVlKSB7CiAgICBHZXQtQ2hpbGRJdGVtIC1QYXRoICRwYXN0YSAtRmlsdGVyICIqLnBkZiIgLVJl
echo Y3Vyc2UgLUVycm9yQWN0aW9uIFNpbGVudGx5Q29udGludWUgfCBGb3JFYWNoLU9iamVjdCB7CiAg
echo ICAgICAgJGFycSA9ICRfLkZ1bGxOYW1lCiAgICAgICAgaWYgKCRvay5Db250YWluc0tleSgkYXJx
echo KSkgeyByZXR1cm4gfQoKICAgICAgICAjIEVzdHJ1dHVyYSBlc3BlcmFkYToKICAgICAgICAjICB7
echo cGFzdGF9IC8ge0Fub30gLyB7Q2lkYWRlfSAvIHtDbGllbnRlfSAvIGFycXVpdm8ucGRmCiAgICAg
echo ICAgIyAgcGFydGVzOiAgICBbMF0gICAgICBbMV0gICAgICAgIFsyXSAgICAgICAgIFszPW5vbWVd
echo CiAgICAgICAgJHJlbCAgID0gJGFycS5TdWJzdHJpbmcoJHBhc3RhLkxlbmd0aCkuVHJpbVN0YXJ0
echo KCJcIiwgIi8iKQogICAgICAgICRwICAgICA9ICRyZWwgLXNwbGl0ICJbXFwvXSIKCiAgICAgICAg
echo aWYgKCRwLkNvdW50IC1sdCA0KSB7CiAgICAgICAgICAgICMgQXJxdWl2byBmb3JhIGRhIGVzdHJ1
echo dHVyYSBjb3JyZXRhIOKAlCBpZ25vcmEgc2VtIGxvZ2FyCiAgICAgICAgICAgICRva1skYXJxXSA9
echo ICJpZ25vcmFkbyIKICAgICAgICAgICAgU2FsdmFyICRvawogICAgICAgICAgICByZXR1cm4KICAg
echo ICAgICB9CgogICAgICAgICRhbm8gICAgID0gJHBbMF0KICAgICAgICAkY2lkYWRlICA9ICRwWzFd
echo CiAgICAgICAgJGNsaWVudGUgPSAkcFsyXQogICAgICAgICRub21lICAgID0gJHBbLTFdCgogICAg
echo ICAgICMgU29tZW50ZSBhcnF1aXZvcyBjb20gIlByb3Bvc3RhIENvbWVyY2lhbCIgbm8gbm9tZQog
echo ICAgICAgIGlmICgkbm9tZSAtbm90bGlrZSAiKlByb3Bvc3RhIENvbWVyY2lhbCoiKSB7CiAgICAg
echo ICAgICAgICRva1skYXJxXSA9ICJpZ25vcmFkbyIKICAgICAgICAgICAgU2FsdmFyICRvawogICAg
echo ICAgICAgICByZXR1cm4KICAgICAgICB9CgogICAgICAgICMgQWd1YXJkYSBvIGFycXVpdm8gdGVy
echo bWluYXIgZGUgc2VyIGdyYXZhZG8KICAgICAgICBTdGFydC1TbGVlcCAzCiAgICAgICAgaWYgKC1u
echo b3QgKFRlc3QtUGF0aCAkYXJxKSkgeyByZXR1cm4gfQoKICAgICAgICBMb2cgIkFycXVpdm8gbm92
echo bzogJG5vbWUiCiAgICAgICAgTG9nICIgIEFubzogICAgICRhbm8iCiAgICAgICAgTG9nICIgIENp
echo ZGFkZTogICRjaWRhZGUiCiAgICAgICAgTG9nICIgIENsaWVudGU6ICRjbGllbnRlIgoKICAgICAg
echo ICAkZGVzdGlubyA9ICIkYW5vLyRjaWRhZGUvJGNsaWVudGUiCgogICAgICAgICRyID0gJiAkcmNs
echo b25lIGNvcHkgJGFycSAiZWdlbWFwOiRkZXN0aW5vIiAtLWNvbmZpZyAkY29uZiAyPiYxCiAgICAg
echo ICAgaWYgKCRMQVNURVhJVENPREUgLWVxIDApIHsKICAgICAgICAgICAgTG9nICIgIFtPS10gRW52
echo aWFkbyBwYXJhIG8gRHJpdmUiCiAgICAgICAgICAgICRva1skYXJxXSA9ICJvayIKICAgICAgICAg
echo ICAgU2FsdmFyICRvawogICAgICAgIH0gZWxzZSB7CiAgICAgICAgICAgIExvZyAiICBbRVJST10g
echo RmFsaGEgLSB2YWkgdGVudGFyIGRlIG5vdm8gZW0gMTBzIgogICAgICAgICAgICBMb2cgIiAgRGV0
echo YWxoZTogJHIiCiAgICAgICAgfQogICAgICAgIExvZyAiIgogICAgfQogICAgU3RhcnQtU2xlZXAg
echo MTAKfQo=
) > "%B64FILE%"
certutil -decode "%B64FILE%" "%DESTINO%\watcher.ps1" >nul 2>&1
del "%B64FILE%" >nul 2>&1
echo        OK.

echo  [3/4] Resetando historico (arquivos existentes nao serao reenviados)...
if exist "%DESTINO%\enviados.json" del "%DESTINO%\enviados.json"
echo        OK.

echo  [4/4] Iniciando agente atualizado...
start "" /B powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "%DESTINO%\watcher.ps1"
echo        OK.

echo.
echo  =============================================
echo    PRONTO! Agente atualizado e rodando.
echo.
echo    Apenas PDFs com "Proposta Comercial" no
echo    nome serao enviados ao Drive.
echo.
echo    Estrutura: 2026\Cidade\Cliente\arquivo.pdf
echo    Log: %DESTINO%\watcher.log
echo  =============================================
echo.
pause
