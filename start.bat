@echo off
title MCSR Discord Rich Presence Tracker
echo.
echo  ============================================
echo   MCSR Discord Rich Presence Tracker
echo  ============================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download Python from https://python.org/downloads
    echo Make sure to check "Add Python to PATH" during install!
    pause
    exit /b 1
)

:: Install dependencies if not already installed
echo Checking dependencies...
pip show pypresence >nul 2>&1
if errorlevel 1 (
    echo Installing pypresence...
    pip install pypresence
)
pip show watchdog >nul 2>&1
if errorlevel 1 (
    echo Installing watchdog...
    pip install watchdog
)

echo.
echo Starting tracker... (Press Ctrl+C to stop)
echo.
python main.py
pause
