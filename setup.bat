@echo off
rem YJHWell one-time setup: create the venv and install dependencies.
rem Needs internet ONCE; after this the app runs fully offline via run.bat.
cd /d "%~dp0"
echo [YJHWell] Creating virtual environment (.venv)...
py -3.12 -m venv .venv 2>nul || python -m venv .venv
if not exist ".venv\Scripts\python.exe" (
  echo [YJHWell] ERROR: could not create .venv. Install Python 3.12 first.
  pause
  exit /b 1
)
echo [YJHWell] Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
echo.
echo [YJHWell] Setup complete. Double-click run.bat to launch the UI.
pause
