@echo off
setlocal
cd /d "%~dp0"
py -3.11 --version
if errorlevel 1 goto fail
if not exist ".venv\Scripts\python.exe" py -3.11 -m venv --system-site-packages .venv
if errorlevel 1 goto fail
".venv\Scripts\python.exe" check_setup.py
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip list > "Logs\pip_before.txt"
".venv\Scripts\python.exe" -m pip show openai-whisper numpy requests opencv-python PySide6 torch > "Logs\packages_before.txt" 2>&1
".venv\Scripts\python.exe" install_missing.py
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip list > "Logs\pip_after.txt"
".venv\Scripts\python.exe" check_setup.py
if errorlevel 1 goto fail
echo Setup checks complete. Read Logs\setup_report.json or open Settings in Clipify.
pause
exit /b 0
:fail
echo Setup stopped. Please share the error above. No drivers or models were changed.
pause
exit /b 1
