#!/usr/bin/env python3
"""
LoL Voice Controller - Setup Script
Installs all dependencies in a virtual environment without admin rights
"""

import os
import sys
import subprocess
import platform
from pathlib import Path


class Setup:
    def __init__(self):
        self.system = platform.system()
        self.is_windows = self.system == "Windows"
        self.base_dir = Path(__file__).parent
        self.venv_path = self.base_dir / "venv"
        self.python_exe = self._get_python_exe()
        self.pip_exe = self._get_pip_exe()
        
    def _get_python_exe(self):
        """Get the path to Python executable in venv."""
        if self.is_windows:
            return str(self.venv_path / "Scripts" / "python.exe")
        return str(self.venv_path / "bin" / "python")
    
    def _get_pip_exe(self):
        """Get the path to pip executable in venv."""
        if self.is_windows:
            return str(self.venv_path / "Scripts" / "pip.exe")
        return str(self.venv_path / "bin" / "pip")
    
    def print_header(self):
        """Print setup header."""
        print("="*60)
        print("   LoL Voice Controller - Setup")
        print("="*60)
        print(f"System: {self.system}")
        print(f"Python: {sys.version}")
        print(f"Directory: {self.base_dir}")
        print("="*60 + "\n")
    
    def check_python_version(self):
        """Check if Python version is compatible."""
        print("✓ Checking Python version...")
        if sys.version_info < (3, 8):
            print("❌ Error: Python 3.8 or higher is required!")
            print(f"   Current version: {sys.version}")
            return False
        print(f"  Python {sys.version.split()[0]} - OK")
        return True
    
    def create_venv(self):
        """Create virtual environment."""
        if self.venv_path.exists():
            print("✓ Virtual environment already exists")
            return True
        
        print("✓ Creating virtual environment...")
        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(self.venv_path)],
                check=True,
                capture_output=True
            )
            print("  Virtual environment created successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create virtual environment: {e}")
            return False
    
    def upgrade_pip(self):
        """Upgrade pip in virtual environment."""
        print("✓ Upgrading pip...")
        try:
            subprocess.run(
                [self.python_exe, "-m", "pip", "install", "--upgrade", "pip"],
                check=True,
                capture_output=True
            )
            print("  Pip upgraded successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to upgrade pip: {e}")
            return False
    
    def install_requirements(self):
        """Install requirements from requirements.txt."""
        req_file = self.base_dir / "requirements.txt"
        
        if not req_file.exists():
            print("❌ requirements.txt not found!")
            return False
        
        print("✓ Installing dependencies...")
        print("  This may take a few minutes...\n")
        
        try:
            # Install main requirements
            result = subprocess.run(
                [self.pip_exe, "install", "-r", str(req_file)],
                capture_output=False,  # Show output for progress
                text=True
            )
            
            if result.returncode != 0:
                print("\n⚠️  Some packages might have failed to install")
                print("  Trying to install essential packages...")
                
                # Try installing essential packages one by one
                essential = [
                    "numpy",
                    "sounddevice", 
                    "webrtcvad",
                    "colorama",
                    "requests"
                ]
                
                for package in essential:
                    print(f"  Installing {package}...")
                    subprocess.run(
                        [self.pip_exe, "install", package],
                        capture_output=True
                    )
            
            print("\n✓ Dependencies installed")
            return True
            
        except Exception as e:
            print(f"❌ Installation error: {e}")
            return False
    
    def install_whisper(self):
        """Try to install Whisper implementation."""
        print("\n✓ Installing Whisper speech recognition...")
        
        whisper_options = [
            ("pywhispercpp", "Recommended - Fast CPU implementation"),
            ("faster-whisper", "Alternative - Optimized implementation"),
            ("openai-whisper", "Fallback - Official OpenAI implementation")
        ]
        
        for package, description in whisper_options:
            print(f"  Trying {package} ({description})...")
            try:
                result = subprocess.run(
                    [self.pip_exe, "install", package],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minutes timeout
                )
                
                if result.returncode == 0:
                    print(f"  ✓ {package} installed successfully!")
                    return True
                    
            except subprocess.TimeoutExpired:
                print(f"  ⚠️  {package} installation timed out, trying next option...")
            except Exception:
                pass
        
        print("  ⚠️  Warning: No Whisper implementation could be installed")
        print("     You may need to install one manually later")
        return False
    
    def download_models(self):
        """Download required Whisper models."""
        print("\n✓ Checking Whisper models...")
        
        models_dir = self.base_dir / "models"
        models_dir.mkdir(exist_ok=True)
        
        model_file = models_dir / "ggml-tiny.bin"
        
        if model_file.exists():
            print("  Model already downloaded")
            return True
        
        print("  Downloading Whisper tiny model...")
        model_url = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin"
        
        try:
            import urllib.request
            urllib.request.urlretrieve(model_url, str(model_file))
            print("  ✓ Model downloaded successfully")
            return True
        except Exception as e:
            print(f"  ⚠️  Failed to download model: {e}")
            print("     You can download it manually from:")
            print(f"     {model_url}")
            return False
    
    def create_launcher(self):
        """Create launcher scripts."""
        print("\n✓ Creating launcher scripts...")
        
        # Windows batch file
        if self.is_windows:
            bat_content = f"""@echo off
title LoL Voice Controller
echo Starting LoL Voice Controller...
"{self.python_exe}" main.py %*
pause
"""
            launcher_path = self.base_dir / "launch.bat"
            launcher_path.write_text(bat_content)
            print(f"  Created: launch.bat")
            
            # Also create GUI launcher
            gui_bat = f"""@echo off
title LoL Voice Controller - GUI
"{self.python_exe}" main.py --gui
"""
            gui_launcher = self.base_dir / "launch_gui.bat"
            gui_launcher.write_text(gui_bat)
            print(f"  Created: launch_gui.bat")
            
            # CLI launcher
            cli_bat = f"""@echo off
title LoL Voice Controller - CLI
"{self.python_exe}" main.py --cli
pause
"""
            cli_launcher = self.base_dir / "launch_cli.bat"
            cli_launcher.write_text(cli_bat)
            print(f"  Created: launch_cli.bat")
            
        else:
            # Unix/Linux shell script
            sh_content = f"""#!/bin/bash
echo "Starting LoL Voice Controller..."
{self.python_exe} main.py "$@"
"""
            launcher_path = self.base_dir / "launch.sh"
            launcher_path.write_text(sh_content)
            launcher_path.chmod(0o755)
            print(f"  Created: launch.sh")
            
            # GUI launcher
            gui_sh = f"""#!/bin/bash
{self.python_exe} main.py --gui
"""
            gui_launcher = self.base_dir / "launch_gui.sh"
            gui_launcher.write_text(gui_sh)
            gui_launcher.chmod(0o755)
            print(f"  Created: launch_gui.sh")
            
            # CLI launcher
            cli_sh = f"""#!/bin/bash
{self.python_exe} main.py --cli
"""
            cli_launcher = self.base_dir / "launch_cli.sh"
            cli_launcher.write_text(cli_sh)
            cli_launcher.chmod(0o755)
            print(f"  Created: launch_cli.sh")
        
        return True
    
    def create_directories(self):
        """Create required directories."""
        print("\n✓ Creating directories...")
        
        dirs = [
            "config",
            "models",
            "logs",
            "data/champions",
            "controller",
            "controls", 
            "game",
            "gui",
            "utils"
        ]
        
        for dir_name in dirs:
            dir_path = self.base_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            
        print("  All directories created")
        return True
    
    def run(self):
        """Run the complete setup process."""
        self.print_header()
        
        steps = [
            ("Checking Python version", self.check_python_version),
            ("Creating virtual environment", self.create_venv),
            ("Upgrading pip", self.upgrade_pip),
            ("Installing dependencies", self.install_requirements),
            ("Installing Whisper", self.install_whisper),
            ("Downloading models", self.download_models),
            ("Creating directories", self.create_directories),
            ("Creating launchers", self.create_launcher)
        ]
        
        for step_name, step_func in steps:
            if not step_func():
                print(f"\n⚠️  Setup incomplete: {step_name} failed")
                print("   You may need to complete this step manually")
                input("\nPress Enter to continue...")
        
        print("\n" + "="*60)
        print("✅ Setup completed!")
        print("="*60)
        print("\nTo start the application:")
        
        if self.is_windows:
            print("  • Double-click 'launch.bat' for default mode")
            print("  • Double-click 'launch_gui.bat' for GUI")
            print("  • Double-click 'launch_cli.bat' for CLI")
        else:
            print("  • Run './launch.sh' for default mode")
            print("  • Run './launch_gui.sh' for GUI")
            print("  • Run './launch_cli.sh' for CLI")
        
        print("\n" + "="*60)
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    try:
        setup = Setup()
        setup.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)