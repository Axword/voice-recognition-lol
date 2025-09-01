#!/usr/bin/env python3
"""
Alternative setup script using PyInstaller
Often works better on Windows than cx_Freeze
"""

import os
import subprocess
import sys

def install_pyinstaller():
    """Install PyInstaller if not available"""
    try:
        import PyInstaller
        print("✅ PyInstaller already installed")
        return True
    except ImportError:
        print("📦 Installing PyInstaller...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("✅ PyInstaller installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install PyInstaller")
            return False

def build_gui():
    """Build GUI executable"""
    print("🔨 Building GUI executable...")
    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name=LoL_Voice_Controller",
        "--add-data=lol_data_manager.py;.",
        "--add-data=lol_voice_controller_v2.py;.",
        "--add-data=lol_game_client_api.py;.",
        "--add-data=requirements.txt;.",
        "lol_voice_gui.py"
    ]
    
    try:
        subprocess.check_call(cmd)
        print("✅ GUI executable built successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to build GUI: {e}")
        return False

def build_console():
    """Build console executable"""
    print("🔨 Building console executable...")
    cmd = [
        "pyinstaller",
        "--onefile",
        "--console",
        "--name=LoL_Voice_Console",
        "--add-data=lol_data_manager.py;.",
        "--add-data=lol_game_client_api.py;.",
        "--add-data=requirements.txt;.",
        "lol_voice_controller_v2.py"
    ]
    
    try:
        subprocess.check_call(cmd)
        print("✅ Console executable built successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to build console: {e}")
        return False

def main():
    print("🎯 === LoL Voice Controller - PyInstaller Build ===")
    print()
    
    if not install_pyinstaller():
        print("❌ Cannot proceed without PyInstaller")
        return
    
    print()
    print("🧹 Cleaning previous builds...")
    if os.path.exists("dist"):
        import shutil
        shutil.rmtree("dist")
    if os.path.exists("build"):
        import shutil
        shutil.rmtree("build")
    
    print()
    success_gui = build_gui()
    print()
    success_console = build_console()
    
    print()
    if success_gui and success_console:
        print("🎉 All executables built successfully!")
        print("📁 Check the 'dist' folder for your .exe files")
    elif success_gui or success_console:
        print("⚠️  Partial build success - check 'dist' folder")
    else:
        print("❌ Build failed completely")
    
    print()
    input("Press Enter to continue...")

if __name__ == "__main__":
    main()
