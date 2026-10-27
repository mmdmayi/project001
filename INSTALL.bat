@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\install.ps1" -Unattended
set "result=%errorlevel%"
if not "%~1"=="--unattended" pause
exit /b %result%
