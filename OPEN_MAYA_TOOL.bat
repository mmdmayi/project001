@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0.runtime\python\python.exe" (echo Run INSTALL.bat first. & pause & exit /b 1)
"%~dp0.runtime\python\python.exe" "%~dp0installer\launch_maya.py"
if errorlevel 1 pause
