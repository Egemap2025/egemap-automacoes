@echo off
chcp 65001 >nul 2>&1
title Egemap - Atualizando agente

echo.
echo  =============================================
echo    Egemap - Atualizando estrutura de pastas
echo  =============================================
echo.
echo  Nova estrutura: 2026 / Cidade / Cliente / PDF
echo.

set DESTINO=%USERPROFILE%\EgemapDrive

if not exist "%DESTINO%\rclone.exe" (
    echo  [ERRO] Agente nao encontrado. Execute EGEMAP_INSTALAR.bat primeiro.
    pause & exit /b 1
)

echo  [1/3] Parando agente antigo...
taskkill /F /FI "WINDOWTITLE eq Egemap*" >nul 2>&1
powershell -Command "Get-Process powershell | Where-Object {$_.MainWindowTitle -like '*Egemap*'} | Stop-Process -Force" >nul 2>&1
timeout /t 2 /nobreak >nul
echo        OK.

echo  [2/3] Instalando novo agente...
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
echo PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0iCkxvZyAi
echo TW9uaXRvcmFuZG86ICRwYXN0YSIKTG9nICJFc3RydXR1cmE6ICAgT3JjYW1lbnRvcyAvIDIwMjYg
echo LyBDaWRhZGUgLyBDbGllbnRlIC8gUERGIgpMb2cgIiIKCiRvayA9IEVudmlhZG9zCgp3aGlsZSAo
echo JHRydWUpIHsKICAgIEdldC1DaGlsZEl0ZW0gLVBhdGggJHBhc3RhIC1GaWx0ZXIgIioucGRmIiAt
echo UmVjdXJzZSAtRXJyb3JBY3Rpb24gU2lsZW50bHlDb250aW51ZSB8IEZvckVhY2gtT2JqZWN0IHsK
echo ICAgICAgICAkYXJxID0gJF8uRnVsbE5hbWUKICAgICAgICBpZiAoJG9rLkNvbnRhaW5zS2V5KCRh
echo cnEpKSB7IHJldHVybiB9CgogICAgICAgICMgRXN0cnV0dXJhIGVzcGVyYWRhOgogICAgICAgICMg
echo IHtwYXN0YX0gLyB7QW5vfSAvIHtDaWRhZGV9IC8ge0NsaWVudGV9IC8gYXJxdWl2by5wZGYKICAg
echo ICAgICAjICBwYXJ0ZXM6ICAgIFswXSAgICAgIFsxXSAgICAgICAgWzJdICAgICAgICAgWzM9bm9tZV0K
echo ICAgICAgICAkcmVsICAgPSAkYXJxLlN1YnN0cmluZygkcGFzdGEuTGVuZ3RoKS5UcmltU3RhcnQo
echo IlwiLCAiLyIpCiAgICAgICAgJHAgICAgID0gJHJlbCAtc3BsaXQgIltcXC9dIgoKICAgICAgICBp
echo ZiAoJHAuQ291bnQgLWx0IDQpIHsKICAgICAgICAgICAgIyBBcnF1aXZvIGZvcmEgZGEgZXN0cnV0
echo dXJhIGNvcnJldGEg4oCUIGlnbm9yYSBzZW0gbG9nYXIKICAgICAgICAgICAgJG9rWyRhcnFdID0g
echo Imlnbm9yYWRvIgogICAgICAgICAgICBTYWx2YXIgJG9rCiAgICAgICAgICAgIHJldHVybgogICAg
echo ICAgIH0KCiAgICAgICAgJGFubyAgICAgPSAkcFswXQogICAgICAgICRjaWRhZGUgID0gJHBbMV0K
echo ICAgICAgICAkY2xpZW50ZSA9ICRwWzJdCiAgICAgICAgJG5vbWUgICAgPSAkcFstMV0KCiAgICAg
echo ICAgIyBBZ3VhcmRhIG8gYXJxdWl2byB0ZXJtaW5hciBkZSBzZXIgZ3JhdmFkbwogICAgICAgIFN0
echo YXJ0LVNsZWVwIDMKICAgICAgICBpZiAoLW5vdCAoVGVzdC1QYXRoICRhcnEpKSB7IHJldHVybiB9
echo CgogICAgICAgIExvZyAiQXJxdWl2byBub3ZvOiAkbm9tZSIKICAgICAgICBMb2cgIiAgQW5vOiAg
echo ICAgJGFubyIKICAgICAgICBMb2cgIiAgQ2lkYWRlOiAgJGNpZGFkZSIKICAgICAgICBMb2cgIiAg
echo Q2xpZW50ZTogJGNsaWVudGUiCgogICAgICAgICRkZXN0aW5vID0gIiRhbm8vJGNpZGFkZS8kY2xp
echo ZW50ZSIKCiAgICAgICAgJHIgPSAmICRyY2xvbmUgY29weSAkYXJxICJlZ2VtYXA6JGRlc3Rpbm8i
echo IC0tY29uZmlnICRjb25mIDI+JjEKICAgICAgICBpZiAoJExBU1RFWElUQ09ERSAtZXEgMCkgewog
echo ICAgICAgICAgICBMb2cgIiAgW09LXSBFbnZpYWRvIHBhcmEgbyBEcml2ZSIKICAgICAgICAgICAg
echo JG9rWyRhcnFdID0gIm9rIgogICAgICAgICAgICBTYWx2YXIgJG9rCiAgICAgICAgfSBlbHNlIHsK
echo ICAgICAgICAgICAgTG9nICIgIFtFUlJPXSBGYWxoYSAtIHZhaSB0ZW50YXIgZGUgbm92byBlbSAx
echo MHMiCiAgICAgICAgICAgIExvZyAiICBEZXRhbGhlOiAkciIKICAgICAgICB9CiAgICAgICAgTG9n
echo ICIiCiAgICB9CiAgICBTdGFydC1TbGVlcCAxMAp9Cg==
) > "%B64FILE%"
certutil -decode "%B64FILE%" "%DESTINO%\watcher.ps1" >nul 2>&1
del "%B64FILE%" >nul 2>&1
echo        OK.

echo  [3/3] Reiniciando agente...
start "" /B powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "%DESTINO%\watcher.ps1"
echo        OK. Agente rodando com a nova estrutura.

echo.
echo  =============================================
echo    PRONTO! Agente atualizado e rodando.
echo.
echo    Estrutura correta das pastas:
echo    ORCAMENTOS\2026\{Cidade}\{Cliente}\arq.pdf
echo.
echo    Exemplo:
echo    ORCAMENTOS\2026\CURITIBA\JOAO SILVA\proposta.pdf
echo.
echo    Log em: %DESTINO%\watcher.log
echo  =============================================
echo.
pause
