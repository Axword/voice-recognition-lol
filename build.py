"""
Build script for creating production executables
Supports CI/CD pipeline
"""

import os
import sys
import shutil
import subprocess
import argparse
import json
from pathlib import Path
import PyInstaller.__main__
from build_config import *
import zipfile


class Builder:
    def __init__(self, app_only=False, installer_only=False):
        self.root_dir = ROOT_DIR
        self.build_dir = BUILD_DIR
        self.dist_dir = DIST_DIR
        self.installer_dir = INSTALLER_DIR
        self.app_dir = APP_DIR
        self.app_only = app_only
        self.installer_only = installer_only
        
        version_file = self.root_dir / "version.json"
        if version_file.exists():
            with open(version_file) as f:
                version_data = json.load(f)
                self.version = version_data['version']
        else:
            self.version = VERSION

    def clean(self):
        """Clean previous builds."""
        print("🧹 Cleaning previous builds...")
        
        for directory in [self.build_dir, self.dist_dir]:
            if directory.exists():
                shutil.rmtree(directory)
                print(f"   Removed: {directory}")
        
        # Clean PyInstaller cache
        for spec_file in self.root_dir.glob("*.spec"):
            spec_file.unlink()
            print(f"   Removed: {spec_file}")
    
    def prepare_directories(self):
        """Create necessary directories."""
        print("📁 Creating directories...")
        
        for directory in [self.build_dir, self.dist_dir, self.installer_dir, self.app_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"   Created: {directory}")
    
    def create_version_file(self):
        """Create version file for Windows."""
        print("📝 Creating version file...")
        
        version_file = self.root_dir / "version.txt"
        
        version_content = f"""
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({VERSION.replace('.', ', ')}, 0),
    prodvers=({VERSION.replace('.', ', ')}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'{COMPANY}'),
        StringStruct(u'FileDescription', u'{DESCRIPTION}'),
        StringStruct(u'FileVersion', u'{VERSION}'),
        StringStruct(u'InternalName', u'{PRODUCT}'),
        StringStruct(u'LegalCopyright', u'{COPYRIGHT}'),
        StringStruct(u'OriginalFilename', u'LoLVoiceController.exe'),
        StringStruct(u'ProductName', u'{PRODUCT}'),
        StringStruct(u'ProductVersion', u'{VERSION}')])
      ]), 
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
        version_file.write_text(version_content)
        return str(version_file)
    
    def build_main_app(self):
        """Build the main application executable."""
        print("\n🔨 Building main application...")
        
        # Create spec file content
        spec_content = f'''
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['{self.root_dir}'],
    binaries=[],
    datas={INCLUDE_FILES},
    hiddenimports={HIDDEN_IMPORTS},
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes={EXCLUDES},
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LoLVoiceController',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='{self.create_version_file()}',
    icon='assets/icon.ico' if (Path('assets/icon.ico').exists()) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LoLVoiceController',
)
'''
        
        spec_file = self.root_dir / "main.spec"
        spec_file.write_text(spec_content)
        
        # Build with PyInstaller
        PyInstaller.__main__.run([
            str(spec_file),
            '--distpath', str(self.app_dir),
            '--workpath', str(self.build_dir / 'app'),
            '--clean',
            '--noconfirm'
        ])
        
        print("   ✅ Main application built successfully")
    
    def build_installer(self):
        """Build the installer executable."""
        print("\n🔨 Building installer...")
        
        # Create installer script
        installer_script = self.root_dir / "installer_main.py"
        installer_content = '''
#!/usr/bin/env python3
"""
LoL Voice Controller - Installer
"""

import sys
import os
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import zipfile
import requests


class InstallerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("LoL Voice Controller - Installer")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        
        # Default installation path
        self.install_path = Path.home() / "LoLVoiceController"
        
        self.setup_ui()
        self.center_window()
    
    def center_window(self):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (300)
        y = (self.root.winfo_screenheight() // 2) - (250)
        self.root.geometry(f"600x500+{x}+{y}")
    
    def setup_ui(self):
        # Header
        header_frame = tk.Frame(self.root, bg="#2b2f36", height=100)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)
        
        title = tk.Label(
            header_frame,
            text="LoL Voice Controller",
            font=("Segoe UI", 24, "bold"),
            bg="#2b2f36",
            fg="#00ff88"
        )
        title.pack(pady=20)
        
        subtitle = tk.Label(
            header_frame,
            text="Installation Wizard",
            font=("Segoe UI", 12),
            bg="#2b2f36",
            fg="white"
        )
        subtitle.pack()
        
        # Main content
        main_frame = tk.Frame(self.root, bg="white", padx=40, pady=30)
        main_frame.pack(fill="both", expand=True)
        
        # Welcome text
        welcome_text = """Welcome to the LoL Voice Controller installer.
        
This wizard will guide you through the installation process.
The application will be installed with all necessary components.

Click 'Next' to continue."""
        
        self.info_label = tk.Label(
            main_frame,
            text=welcome_text,
            font=("Segoe UI", 10),
            bg="white",
            justify="left"
        )
        self.info_label.pack(anchor="w", pady=(0, 20))
        
        # Path selection
        path_frame = tk.LabelFrame(
            main_frame,
            text="Installation Directory",
            font=("Segoe UI", 10, "bold"),
            bg="white"
        )
        path_frame.pack(fill="x", pady=(0, 20))
        
        path_inner = tk.Frame(path_frame, bg="white", padx=10, pady=10)
        path_inner.pack(fill="x")
        
        self.path_var = tk.StringVar(value=str(self.install_path))
        path_entry = tk.Entry(
            path_inner,
            textvariable=self.path_var,
            font=("Segoe UI", 10),
            width=50
        )
        path_entry.pack(side="left", padx=(0, 10))
        
        browse_btn = tk.Button(
            path_inner,
            text="Browse...",
            command=self.browse_path,
            font=("Segoe UI", 9)
        )
        browse_btn.pack(side="left")
        
        # Options
        options_frame = tk.LabelFrame(
            main_frame,
            text="Installation Options",
            font=("Segoe UI", 10, "bold"),
            bg="white"
        )
        options_frame.pack(fill="x", pady=(0, 20))
        
        options_inner = tk.Frame(options_frame, bg="white", padx=10, pady=10)
        options_inner.pack(fill="x")
        
        self.create_desktop = tk.BooleanVar(value=True)
        desktop_check = tk.Checkbutton(
            options_inner,
            text="Create desktop shortcut",
            variable=self.create_desktop,
            bg="white",
            font=("Segoe UI", 10)
        )
        desktop_check.pack(anchor="w")
        
        self.create_start_menu = tk.BooleanVar(value=True)
        start_check = tk.Checkbutton(
            options_inner,
            text="Create Start Menu shortcut",
            variable=self.create_start_menu,
            bg="white",
            font=("Segoe UI", 10)
        )
        start_check.pack(anchor="w")
        
        # Progress bar
        self.progress = ttk.Progressbar(
            main_frame,
            length=500,
            mode="determinate"
        )
        self.progress.pack(pady=(0, 10))
        
        self.progress_label = tk.Label(
            main_frame,
            text="Ready to install",
            font=("Segoe UI", 9),
            bg="white",
            fg="gray"
        )
        self.progress_label.pack()
        
        # Buttons
        button_frame = tk.Frame(self.root, bg="#f0f0f0", height=60)
        button_frame.pack(fill="x", side="bottom")
        button_frame.pack_propagate(False)
        
        self.install_btn = tk.Button(
            button_frame,
            text="Install",
            command=self.install,
            bg="#00ff88",
            fg="black",
            font=("Segoe UI", 10, "bold"),
            padx=30
        )
        self.install_btn.pack(side="right", padx=20, pady=15)
        
        cancel_btn = tk.Button(
            button_frame,
            text="Cancel",
            command=self.root.quit,
            font=("Segoe UI", 10),
            padx=30
        )
        cancel_btn.pack(side="right", pady=15)
    
    def browse_path(self):
        path = filedialog.askdirectory(initialdir=self.path_var.get())
        if path:
            self.path_var.set(path)
            self.install_path = Path(path)
    
    def install(self):
        self.install_btn.config(state="disabled")
        self.progress["value"] = 0
        
        try:
            # Create directories
            self.progress_label.config(text="Creating directories...")
            self.install_path.mkdir(parents=True, exist_ok=True)
            self.progress["value"] = 20
            self.root.update()
            
            # Extract application files
            self.progress_label.config(text="Extracting files...")
            self.extract_files()
            self.progress["value"] = 60
            self.root.update()
            
            # Download models
            self.progress_label.config(text="Downloading models...")
            self.download_models()
            self.progress["value"] = 80
            self.root.update()
            
            # Create shortcuts
            if self.create_desktop.get() or self.create_start_menu.get():
                self.progress_label.config(text="Creating shortcuts...")
                self.create_shortcuts()
            self.progress["value"] = 100
            self.root.update()
            
            self.progress_label.config(text="Installation complete!")
            messagebox.showinfo(
                "Success",
                "LoL Voice Controller has been installed successfully!\\n\\n"
                f"Installation path: {self.install_path}"
            )
            self.root.quit()
            
        except Exception as e:
            messagebox.showerror("Error", f"Installation failed:\\n{e}")
            self.install_btn.config(state="normal")
    
    def extract_files(self):
        # In production, extract embedded files
        # For now, copy from current directory
        import sys
        if getattr(sys, 'frozen', False):
            # Running as compiled exe
            source = Path(sys._MEIPASS) / "app_data.zip"
            with zipfile.ZipFile(source, 'r') as zip_ref:
                zip_ref.extractall(self.install_path)
        else:
            # Development mode - copy files
            source = Path(__file__).parent
            for item in source.glob("*"):
                if item.name not in ["build", "dist", "__pycache__"]:
                    dest = self.install_path / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dest)
    
    def download_models(self):
        models_dir = self.install_path / "models"
        models_dir.mkdir(exist_ok=True)
        
        model_file = models_dir / "ggml-tiny.bin"
        if not model_file.exists():
            import urllib.request
            url = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin"
            urllib.request.urlretrieve(url, str(model_file))
    
    def create_shortcuts(self):
        if sys.platform == "win32":
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            
            exe_path = self.install_path / "LoLVoiceController.exe"
            
            if self.create_desktop.get():
                desktop = Path(shell.SpecialFolders("Desktop"))
                shortcut = shell.CreateShortCut(str(desktop / "LoL Voice Controller.lnk"))
                shortcut.Targetpath = str(exe_path)
                shortcut.WorkingDirectory = str(self.install_path)
                shortcut.IconLocation = str(exe_path)
                shortcut.save()
            
            if self.create_start_menu.get():
                start_menu = Path(shell.SpecialFolders("StartMenu")) / "Programs"
                shortcut = shell.CreateShortCut(str(start_menu / "LoL Voice Controller.lnk"))
                shortcut.Targetpath = str(exe_path)
                shortcut.WorkingDirectory = str(self.install_path)
                shortcut.IconLocation = str(exe_path)
                shortcut.save()
    
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = InstallerGUI()
    app.run()
'''
        installer_script.write_text(installer_content)
        
        # Build installer with PyInstaller
        PyInstaller.__main__.run([
            str(installer_script),
            '--name', 'LoLVoiceController_Setup',
            '--onefile',
            '--windowed',
            '--distpath', str(self.installer_dir),
            '--workpath', str(self.build_dir / 'installer'),
            '--clean',
            '--noconfirm',
            '--add-data', f'{self.app_dir};app_data',
            '--icon', 'assets/installer_icon.ico' if Path('assets/installer_icon.ico').exists() else None,
        ])
        
        print("   ✅ Installer built successfully")
    
    def create_portable_zip(self):
        """Create portable ZIP version."""
        print("\n📦 Creating portable version...")
        
        zip_path = self.dist_dir / f"LoLVoiceController_{VERSION}_portable.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in self.app_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(self.app_dir)
                    zipf.write(file_path, arcname)
        
        print(f"   ✅ Portable version created: {zip_path}")
    
    def build_all(self):
        """Build everything or specific components."""
        print("\n" + "="*60)
        print("   LoL Voice Controller - Build System")
        print("="*60)
        print(f"Version: {self.version}")
        print("="*60 + "\n")
        
        if not self.installer_only:
            self.clean()
            self.prepare_directories()
            self.build_main_app()
        
        if not self.app_only:
            self.build_installer()
            self.create_portable_zip()
        
        print("\n" + "="*60)
        print("✅ Build completed successfully!")
        print("="*60)
        print("\nOutput files:")
        print(f"  • Installer: {self.installer_dir / 'LoLVoiceController_Setup.exe'}")
        print(f"  • Portable:  {self.dist_dir / f'LoLVoiceController_{VERSION}_portable.zip'}")
        print(f"  • App:       {self.app_dir / 'LoLVoiceController'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Build LoL Voice Controller')
    parser.add_argument('--app-only', action='store_true', help='Build only the main application')
    parser.add_argument('--installer-only', action='store_true', help='Build only the installer')
    
    args = parser.parse_args()
    
    builder = Builder(app_only=args.app_only, installer_only=args.installer_only)
    builder.build_all()