@echo off
cd /d "%~dp0"
if not exist .venv ( py -3 -m venv .venv || python -m venv .venv )
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
echo Setup done. Double-click run.bat to start DealScout.
pause
