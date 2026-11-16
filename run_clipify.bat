@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run install_dependencies.bat, then double-click this launcher again.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" clipify.py
if errorlevel 1 (
  echo Clipify stopped. See Logs\clipify.log and the error above.
  pause
)
