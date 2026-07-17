@echo off
REG DELETE "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "EGEMAP-Monitor" /f >nul 2>&1

echo.
echo Monitor removido do inicio automatico do Windows.
echo.
pause
