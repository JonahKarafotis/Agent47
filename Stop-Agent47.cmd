@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Create .venv first. See ReadMe.md for Windows setup.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m agent47.launcher stop
if errorlevel 1 (
  pause
  exit /b 1
)
