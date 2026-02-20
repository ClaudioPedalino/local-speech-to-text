@echo off
cd /d "%~dp0"
setlocal EnableDelayedExpansion

:: Find a suitable Python (3.10, 3.11, or 3.12)
set "PYCMD="
where py >nul 2>&1 && (
  py -3.12 -c "exit(0)" 2>nul && set "PYCMD=py -3.12"
  if not defined PYCMD py -3.11 -c "exit(0)" 2>nul && set "PYCMD=py -3.11"
  if not defined PYCMD py -3.10 -c "exit(0)" 2>nul && set "PYCMD=py -3.10"
)
if not defined PYCMD where python >nul 2>&1 && (
  python -c "import sys; exit(0 if (sys.version_info.major==3 and 10<=sys.version_info.minor<=12) else 1)" 2>nul && set "PYCMD=python"
)
if not defined PYCMD (
  echo Python 3.10, 3.11, or 3.12 is required.
  echo Install from https://www.python.org/downloads/ and check "Add python.exe to PATH".
  echo Then run this script again.
  pause
  exit /b 1
)

echo Using: %PYCMD%
if not exist "venv\Scripts\python.exe" (
  echo Creating virtual environment and installing dependencies...
  %PYCMD% -m venv venv
  if errorlevel 1 (
    echo Failed to create venv.
    pause
    exit /b 1
  )
  call venv\Scripts\activate.bat
  pip install -r requirements.txt
  if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
  )
  echo.
)

:: Run the app
venv\Scripts\python.exe voice_dictation.py
if errorlevel 1 pause
