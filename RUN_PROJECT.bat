@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0.runtime\python\python.exe" (echo Run INSTALL.bat first. & exit /b 1)
"%~dp0.runtime\python\python.exe" -m faceinverse.project %*
exit /b %errorlevel%
