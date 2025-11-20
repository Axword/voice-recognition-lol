@echo off
title LoL Voice Controller - Installer
echo ========================================
echo    LoL Voice Controller - Installer
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

echo Starting setup...
python setup.py

if %errorlevel% neq 0 (
    echo.
    echo Setup failed!
    pause
    exit /b 1
)

echo.
echo Installation complete!
echo You can now run the application using:
echo   - launch.bat (default mode)
echo   - launch_gui.bat (GUI mode)
echo   - launch_cli.bat (CLI mode)
echo.
pause