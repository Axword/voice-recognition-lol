@echo off
title Building LoL Voice Controller

echo ========================================
echo    Building LoL Voice Controller
echo ========================================
echo.

REM Activate virtual environment if exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Install build requirements
echo Installing build requirements...
pip install -r requirements-dev.txt

REM Run build script
echo.
echo Starting build process...
python build.py

if %errorlevel% neq 0 (
    echo.
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo Build complete!
echo.
echo Output files:
echo   - dist\installer\LoLVoiceController_Setup.exe (Installer)
echo   - dist\LoLVoiceController_*_portable.zip (Portable version)
echo.
pause