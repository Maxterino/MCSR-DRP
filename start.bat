@echo off
title MCSR Discord Rich Presence Tracker
echo.
echo  ============================================
echo   MCSR Discord Rich Presence Tracker
echo  ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download Python from https://python.org/downloads
    echo Make sure to check "Add Python to PATH" during install!
    pause
    exit /b 1
)

:: Install dependencies silently
echo Checking dependencies...
pip show pypresence >nul 2>&1
if errorlevel 1 ( pip install pypresence -q )
pip show watchdog >nul 2>&1
if errorlevel 1 ( pip install watchdog -q )

:: First time setup — if no config.ini exists, run wizard
if not exist "%~dp0config.ini" (
    echo.
    echo First run detected! Starting setup wizard...
    echo.
    python "%~dp0main.py" --setup
    echo.
    echo Setup done. Starting tracker...
    echo.
)

echo Starting tracker... (Press Ctrl+C to stop)
echo.
python "%~dp0main.py"
pause
