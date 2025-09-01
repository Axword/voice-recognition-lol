@echo off
echo ========================================
echo LoL Voice Controller - Optimized Build
echo ========================================
echo.

echo Installing PyInstaller...
python -m pip install pyinstaller

echo.
echo Cleaning previous builds...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo.
echo Building optimized GUI executable...
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name=LoL_Voice_Controller ^
    --add-data="lol_data_manager.py;." ^
    --add-data="lol_voice_controller_v2.py;." ^
    --add-data="lol_game_client_api.py;." ^
    --add-data="requirements.txt;." ^
    --add-data="cache;cache" ^
    --exclude-module=matplotlib ^
    --exclude-module=numpy ^
    --exclude-module=pandas ^
    --exclude-module=scipy ^
    --exclude-module=tkinter.test ^
    --exclude-module=unittest ^
    --exclude-module=test ^
    --exclude-module=tests ^
    --exclude-module=__pycache__ ^
    --exclude-module=*.pyc ^
    --strip ^
    --optimize=2 ^
    lol_voice_gui.py

echo.
if exist dist (
    echo ✅ Build complete! 
    echo 📁 Check the dist/ directory for LoL_Voice_Controller.exe
    echo 📊 File size:
    dir dist /-c
) else (
    echo ❌ Build failed! Check error messages above.
)
echo.
pause
