@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0.runtime\python\python.exe" (echo Run INSTALL.bat first. & exit /b 1)
"%~dp0.runtime\python\python.exe" "%~dp0installer\verify_install.py"
set "result=%errorlevel%"
if not "%~1"=="--unattended" pause
exit /b %result%
