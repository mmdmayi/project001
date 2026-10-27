@echo off
cd /d "%~dp0"
".runtime\python\python.exe" installer\verify_maya.py
set "RESULT=%ERRORLEVEL%"
if /I not "%~1"=="--unattended" pause
exit /b %RESULT%
