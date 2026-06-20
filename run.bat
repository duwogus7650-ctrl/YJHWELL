@echo off
rem YJHWell launcher (offline). Double-click to start the UI.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo [YJHWell] .venv not found - run setup.bat once first ^(needs internet only that one time^).
  pause
  exit /b 1
)
start "YJHWell" ".venv\Scripts\pythonw.exe" run.py
