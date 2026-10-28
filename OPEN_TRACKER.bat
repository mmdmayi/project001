@echo off
cd /d "%~dp0"
".runtime\python\python.exe" installer\launch_tracker.py
if errorlevel 1 pause
