#!/usr/bin/env python3
"""
League of Legends Voice Controller GUI
Clean, modern interface with full champion detection functionality
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import os
from typing import Dict
import time

from lol_voice_controller_v2 import LoLVoiceControllerV2

class LoLVoiceGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.controller = None
        self.is_running = False
        
        self.config_file = "lol_voice_config.json"
        self.config = self.load_config()
        
        self.setup_window()
        self.create_widgets()
        self.load_initial_state()
        self.start_status_updates()
    
    def setup_window(self):
        self.root.title("LoL Voice Controller v2.0")
        self.root.geometry("700x600")
        self.root.configure(bg='#2b2b2b')
        self.root.resizable(False, False)
        
        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (700 // 2)
        y = (self.root.winfo_screenheight() // 2) - (600 // 2)
        self.root.geometry(f"700x600+{x}+{y}")
    
    def create_widgets(self):
        # Main container
        main_frame = tk.Frame(self.root, bg='#2b2b2b')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Title
        title = tk.Label(main_frame, 
                        text="LoL Voice Controller v2.0",
                        font=('Segoe UI', 24, 'bold'),
                        fg='#00ff88',
                        bg='#2b2b2b')
        title.pack(pady=(0, 25))
        
        # Status section
        self.create_status_section(main_frame)
        
        # Controls section
        self.create_controls_section(main_frame)
        
        # Configuration section
        self.create_config_section(main_frame)
        
        # Champion abilities section
        self.create_champion_section(main_frame)
        
        # Log section
        self.create_log_section(main_frame)
    
    def create_status_section(self, parent):
        status_frame = tk.LabelFrame(parent, 
                                   text="Status",
                                   font=('Segoe UI', 10, 'bold'),
                                   fg='#ffffff',
                                   bg='#2b2b2b',
                                   relief='flat',
                                   bd=0)
        status_frame.pack(fill='x', pady=(0, 15))
        
        # Status grid
        status_grid = tk.Frame(status_frame, bg='#2b2b2b')
        status_grid.pack(fill='x', padx=15, pady=15)
        
        self.status_vars = {
            'listening': tk.StringVar(value="🔴 Stopped"),
            'game': tk.StringVar(value="🔴 No Game"),
            'champion': tk.StringVar(value="❓ Unknown"),
            'commands': tk.StringVar(value="📋 0 commands"),
            'vosk_model': tk.StringVar(value="❓ Checking..."),
            'cache': tk.StringVar(value="🚀 0 cache hits")
        }
        
        # Create status labels in a grid
        labels = [
            ("Voice Control:", self.status_vars['listening']),
            ("Game Status:", self.status_vars['game']),
            ("Champion:", self.status_vars['champion']),
            ("Commands:", self.status_vars['commands']),
            ("Vosk Model:", self.status_vars['vosk_model']),
            ("Cache:", self.status_vars['cache'])
        ]
        
        for i, (label_text, var) in enumerate(labels):
            row = i // 2
            col = i % 2 * 2
            
            tk.Label(status_grid, 
                    text=label_text,
                    font=('Segoe UI', 9),
                    fg='#cccccc',
                    bg='#2b2b2b').grid(row=row, column=col, sticky='w', padx=(0, 10), pady=2)
            
            tk.Label(status_grid,
                    textvariable=var,
                    font=('Segoe UI', 9, 'bold'),
                    fg='#ffffff',
                    bg='#2b2b2b').grid(row=row, column=col+1, sticky='w', padx=(0, 20), pady=2)
    
    def create_controls_section(self, parent):
        controls_frame = tk.LabelFrame(parent,
                                     text="Controls",
                                     font=('Segoe UI', 10, 'bold'),
                                     fg='#ffffff',
                                     bg='#2b2b2b',
                                     relief='flat',
                                     bd=0)
        controls_frame.pack(fill='x', pady=(0, 15))
        
        controls_container = tk.Frame(controls_frame, bg='#2b2b2b')
        controls_container.pack(fill='x', padx=15, pady=15)
        
        # Main control button
        self.main_button = tk.Button(controls_container,
                                   text="🎤 Start Voice Control",
                                   font=('Segoe UI', 12, 'bold'),
                                   fg='#ffffff',
                                   bg='#00ff88',
                                   activebackground='#00cc6a',
                                   activeforeground='#ffffff',
                                   relief='flat',
                                   bd=0,
                                   padx=30,
                                   pady=10,
                                   cursor='hand2',
                                   command=self.toggle_voice_control)
        self.main_button.pack(pady=(0, 10))
        
        # Secondary buttons
        button_frame = tk.Frame(controls_container, bg='#2b2b2b')
        button_frame.pack(fill='x')
        
        test_btn = tk.Button(button_frame,
                           text="🔧 Test Microphone",
                           font=('Segoe UI', 9),
                           fg='#ffffff',
                           bg='#444444',
                           activebackground='#555555',
                           activeforeground='#ffffff',
                           relief='flat',
                           bd=0,
                           padx=20,
                           pady=5,
                           cursor='hand2',
                           command=self.test_microphone)
        test_btn.pack(side='left', padx=(0, 10))
        
        update_btn = tk.Button(button_frame,
                             text="🔄 Update Champion",
                             font=('Segoe UI', 9),
                             fg='#ffffff',
                             bg='#444444',
                             activebackground='#555555',
                             activeforeground='#ffffff',
                             relief='flat',
                             bd=0,
                             padx=20,
                             pady=5,
                             cursor='hand2',
                             command=self.update_champion)
        update_btn.pack(side='left', padx=(0, 10))
        
        vosk_btn = tk.Button(button_frame,
                            text="📥 Download Vosk Model",
                            font=('Segoe UI', 9),
                            fg='#ffffff',
                            bg='#0066cc',
                            activebackground='#0052a3',
                            activeforeground='#ffffff',
                            relief='flat',
                            bd=0,
                            padx=20,
                            pady=5,
                            cursor='hand2',
                            command=self.download_vosk_model)
        vosk_btn.pack(side='left')
    
    def create_config_section(self, parent):
        config_frame = tk.LabelFrame(parent,
                                   text="Configuration",
                                   font=('Segoe UI', 10, 'bold'),
                                   fg='#ffffff',
                                   bg='#2b2b2b',
                                   relief='flat',
                                   bd=0)
        config_frame.pack(fill='x', pady=(0, 15))
        
        config_container = tk.Frame(config_frame, bg='#2b2b2b')
        config_container.pack(fill='x', padx=15, pady=15)
        
        # Language selection
        lang_frame = tk.Frame(config_container, bg='#2b2b2b')
        lang_frame.pack(side='left', padx=(0, 40))
        
        tk.Label(lang_frame,
                text="Language:",
                font=('Segoe UI', 9),
                fg='#cccccc',
                bg='#2b2b2b').pack(anchor='w')
        
        self.language_var = tk.StringVar(value=self.config.get('language', 'pl_PL'))
        supported_languages = ['pl_PL', 'en_US', 'de_DE', 'es_ES', 'fr_FR', 'it_IT', 
                             'pt_BR', 'ru_RU', 'ko_KR', 'zh_CN', 'ja_JP', 'tr_TR']
        
        lang_combo = ttk.Combobox(lang_frame,
                                 textvariable=self.language_var,
                                 values=supported_languages,
                                 state='readonly',
                                 width=12,
                                 font=('Segoe UI', 9))
        lang_combo.pack(pady=(5, 0))
        lang_combo.bind('<<ComboboxSelected>>', self.on_language_change)
        
        # Speech Recognition Engine selection
        engine_frame = tk.Frame(config_container, bg='#2b2b2b')
        engine_frame.pack(side='left', padx=(0, 40))
        
        tk.Label(engine_frame,
                text="Speech Engine:",
                font=('Segoe UI', 9),
                fg='#cccccc',
                bg='#2b2b2b').pack(anchor='w')
        
        # Engine descriptions for speed reference
        engine_descriptions = {
            'vosk': 'Vosk (Offline, Fast)',
            'speech_recognition': 'Google (Ultra Fast)',
            'whisper': 'Whisper (Fast & Accurate)'
        }
        
        # Speed info
        speed_info = {
            'vosk': 'Używa speech_recognition.recognize_vosk()',
            'speech_recognition': 'Używa speech_recognition.recognize_google()',
            'whisper': 'Używa speech_recognition.recognize_whisper()'
        }
        
        self.engine_var = tk.StringVar(value=self.config.get('speech_engine', 'vosk'))
        supported_engines = ['vosk', 'speech_recognition', 'whisper']
        
        engine_combo = ttk.Combobox(engine_frame,
                                   textvariable=self.engine_var,
                                   values=supported_engines,
                                   state='readonly',
                                   width=15,
                                   font=('Segoe UI', 9))
        engine_combo.pack(pady=(5, 0))
        engine_combo.bind('<<ComboboxSelected>>', self.on_engine_change)
        
        # Speed indicator
        self.speed_label = tk.Label(engine_frame,
                                  text="⚡ Ultra Fast",
                                  font=('Segoe UI', 8),
                                  fg='#00ff88',
                                  bg='#2b2b2b')
        self.speed_label.pack(pady=(2, 0))
        
        # Key bindings
        keybind_frame = tk.Frame(config_container, bg='#2b2b2b')
        keybind_frame.pack(side='left', padx=(0, 40))
        
        tk.Label(keybind_frame,
                text="Key Bindings:",
                font=('Segoe UI', 9),
                fg='#cccccc',
                bg='#2b2b2b').pack(anchor='w')
        
        # Flash key
        flash_frame = tk.Frame(keybind_frame, bg='#2b2b2b')
        flash_frame.pack(pady=(5, 2))
        tk.Label(flash_frame,
                text="Flash:",
                font=('Segoe UI', 9),
                fg='#cccccc',
                bg='#2b2b2b').pack(side='left')
        
        self.flash_var = tk.StringVar(value=self.config.get('flash_key', 'f'))
        flash_combo = ttk.Combobox(flash_frame,
                                  textvariable=self.flash_var,
                                  values=['f', 'd'],
                                  state='readonly',
                                  width=5,
                                  font=('Segoe UI', 9))
        flash_combo.pack(side='right', padx=(10, 0))
        flash_combo.bind('<<ComboboxSelected>>', self.on_keybind_change)
        
        # Summoner 2 key
        summ2_frame = tk.Frame(keybind_frame, bg='#2b2b2b')
        summ2_frame.pack(pady=2)
        tk.Label(summ2_frame,
                text="Summoner 2:",
                font=('Segoe UI', 9),
                fg='#cccccc',
                bg='#2b2b2b').pack(side='left')
        
        self.summ2_var = tk.StringVar(value=self.config.get('summoner2_key', 'd'))
        summ2_combo = ttk.Combobox(summ2_frame,
                                  textvariable=self.summ2_var,
                                  values=['d', 'f'],
                                  state='readonly',
                                  width=5,
                                  font=('Segoe UI', 9))
        summ2_combo.pack(side='right', padx=(0, 0))
        summ2_combo.bind('<<ComboboxSelected>>', self.on_keybind_change)
        
        # Auto-update
        update_frame = tk.Frame(config_container, bg='#2b2b2b')
        update_frame.pack(side='right')
        
        tk.Label(update_frame,
                text="Auto-Update:",
                font=('Segoe UI', 9),
                fg='#cccccc',
                bg='#2b2b2b').pack(anchor='w')
        
        self.auto_update_var = tk.BooleanVar(value=self.config.get('auto_update', True))
        auto_update_check = tk.Checkbutton(update_frame,
                                         text="Champion & Game",
                                         font=('Segoe UI', 9),
                                         fg='#ffffff',
                                         bg='#2b2b2b',
                                         selectcolor='#00ff88',
                                         activebackground='#2b2b2b',
                                         activeforeground='#ffffff',
                                         variable=self.auto_update_var,
                                         command=self.on_auto_update_change)
        auto_update_check.pack(pady=(5, 0))
    
    def create_champion_section(self, parent):
        champ_frame = tk.LabelFrame(parent,
                                   text="Champion Abilities",
                                   font=('Segoe UI', 10, 'bold'),
                                   fg='#ffffff',
                                   bg='#2b2b2b',
                                   relief='flat',
                                   bd=0)
        champ_frame.pack(fill='x', pady=(0, 15))
        
        self.abilities_frame = tk.Frame(champ_frame, bg='#2b2b2b')
        self.abilities_frame.pack(fill='x', padx=15, pady=15)
        
        self.no_champ_label = tk.Label(self.abilities_frame,
                                       text="🎮 No champion detected - Start a League of Legends game",
                                       font=('Segoe UI', 9),
                                       fg='#cccccc',
                                       bg='#2b2b2b')
        self.no_champ_label.pack()
    
    def create_log_section(self, parent):
        log_frame = tk.LabelFrame(parent,
                                 text="Console Output",
                                 font=('Segoe UI', 10, 'bold'),
                                 fg='#ffffff',
                                 bg='#2b2b2b',
                                 relief='flat',
                                 bd=0)
        log_frame.pack(fill='both', expand=True)
        
        # Log text area
        self.log_text = tk.Text(log_frame,
                               bg='#1e1e1e',
                               fg='#00ff88',
                               font=('Consolas', 9),
                               wrap='word',
                               relief='flat',
                               bd=0,
                               insertbackground='#00ff88')
        
        # Scrollbar
        scrollbar = tk.Scrollbar(log_frame, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        scrollbar.pack(side='right', fill='y', pady=10)
        
        self.log_message("🎯 LoL Voice Controller v2.0 initialized")
        self.log_message("💡 Select language, configure keybinds, then start voice control")
    
    def load_config(self) -> Dict:
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                return config
        
        default_config = {
            'language': 'pl_PL',
            'flash_key': 'f',
            'summoner2_key': 'd',
            'auto_update': True,
            'speech_engine': 'vosk'
        }
        return default_config
    
    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def load_initial_state(self):
        language = self.config.get('language', 'pl_PL')
        speech_engine = self.config.get('speech_engine', 'vosk')
        self.log_message(f"🌍 Initializing controller with language: {language} and engine: {speech_engine}")
        
        self.controller = LoLVoiceControllerV2(language, speech_engine)
        
        # Verify controller has speech_engine attribute
        if hasattr(self.controller, 'speech_engine'):
            self.log_message(f"✅ Controller speech_engine: {self.controller.speech_engine}")
        else:
            self.log_message("❌ Controller missing speech_engine attribute!")
        
        keybinds = {
            'Flash': self.config.get('flash_key', 'f'),
            'Summoner2': self.config.get('summoner2_key', 'd')
        }
        self.controller.update_keybinds(keybinds)
        
        self.log_message("✅ Voice controller initialized")
    
    def toggle_voice_control(self):
        if not self.controller:
            self.log_message("❌ Controller not initialized")
            return
        
        if not self.is_running:
            self.log_message("🎤 Starting voice control...")
            self.controller.start_listening()
            self.is_running = True
            self.main_button.configure(text="🔴 Stop Voice Control", bg='#ff4444', activebackground='#cc3333')
            self.log_message("✅ Voice control started")
        else:
            self.log_message("🔴 Stopping voice control...")
            self.controller.stop_listening()
            self.is_running = False
            self.main_button.configure(text="🎤 Start Voice Control", bg='#00ff88', activebackground='#00cc6a')
            self.log_message("✅ Voice control stopped")
    
    def test_microphone(self):
        self.log_message("🔧 Testing microphone...")
        if self.controller:
            self.controller.test_microphone()
            self.log_message("✅ Microphone test completed")
        else:
            self.log_message("❌ Controller not initialized")
    
    def update_champion(self):
        self.log_message("🔄 Updating champion data...")
        if self.controller:
            self.controller.update_champion_data()
            self.log_message("✅ Champion data updated")
            self.update_status()
            self.update_champion_display()
        else:
            self.log_message("❌ Controller not initialized")
    
    def update_champion_display(self):
        """Update the champion abilities display"""
        if not self.controller:
            return
        
        # Clear existing abilities
        for widget in self.abilities_frame.winfo_children():
            widget.destroy()
        
        # Get current champion
        champion = self.controller.get_current_champion()
        if not champion:
            self.no_champ_label = tk.Label(self.abilities_frame,
                                         text="🎮 No champion detected - Start a League of Legends game",
                                         font=('Segoe UI', 9),
                                         fg='#cccccc',
                                         bg='#2b2b2b')
            self.no_champ_label.pack()
            return
        
        # Display champion name
        champ_label = tk.Label(self.abilities_frame,
                              text=f"🎮 {champion}",
                              font=('Segoe UI', 12, 'bold'),
                              fg='#00ff88',
                              bg='#2b2b2b')
        champ_label.pack(pady=(0, 10))
        
        # Get abilities
        abilities = self.controller.get_champion_abilities()
        if abilities:
            for ability_key, ability_name in abilities.items():
                ability_frame = tk.Frame(self.abilities_frame, bg='#2b2b2b')
                ability_frame.pack(fill='x', pady=2)
                
                key_label = tk.Label(ability_frame,
                                   text=f"{ability_key}:",
                                   font=('Segoe UI', 9, 'bold'),
                                   fg='#00ff88',
                                   bg='#2b2b2b',
                                   width=3)
                key_label.pack(side='left')
                
                name_label = tk.Label(ability_frame,
                                     text=ability_name,
                                     font=('Segoe UI', 9),
                                     fg='#ffffff',
                                     bg='#2b2b2b')
                name_label.pack(side='left', padx=(10, 0))
        else:
            no_abilities_label = tk.Label(self.abilities_frame,
                                         text="❌ No abilities found for this champion",
                                         font=('Segoe UI', 9),
                                         fg='#ff6666',
                                         bg='#2b2b2b')
            no_abilities_label.pack()
    
    def on_language_change(self, event=None):
        self.config['language'] = self.language_var.get()
        self.save_config()
        self.log_message(f"🌍 Language changed to {self.language_var.get()}")
        
        # Reinitialize controller with new language
        speech_engine = self.config.get('speech_engine', 'vosk')
        self.controller = LoLVoiceControllerV2(self.language_var.get(), speech_engine)
        keybinds = {
            'Flash': self.config.get('flash_key', 'f'),
            'Summoner2': self.config.get('summoner2_key', 'd')
        }
        self.controller.update_keybinds(keybinds)
        self.log_message("✅ Controller reinitialized with new language")
        self.update_champion_display()
    
    def on_keybind_change(self, event=None):
        self.config['flash_key'] = self.flash_var.get()
        self.config['summoner2_key'] = self.summ2_var.get()
        self.save_config()
        
        if self.controller:
            keybinds = {
                'Flash': self.flash_var.get(),
                'Summoner2': self.summ2_var.get()
            }
            self.controller.update_keybinds(keybinds)
            self.log_message("⌨️ Keybinds updated")
    
    def on_auto_update_change(self):
        self.config['auto_update'] = self.auto_update_var.get()
        self.save_config()
        status = "enabled" if self.auto_update_var.get() else "disabled"
        self.log_message(f"🔄 Auto-update {status}")
    
    def on_engine_change(self, event=None):
        """Handle speech recognition engine change"""
        new_engine = self.engine_var.get()
        self.log_message(f"🔄 Changing speech engine to: {new_engine}")
        
        # Update config
        self.config['speech_engine'] = new_engine
        self.save_config()
        self.log_message(f"💾 Config saved with engine: {new_engine}")
        
        self.log_message(f"🔧 Speech engine changed to: {new_engine}")
        
        # Update speed indicator
        speed_texts = {
            'vosk': '⚡ Fast (Offline)',
            'speech_recognition': '🚀 Ultra Fast',
            'whisper': '⚡ Fast & Accurate'
        }
        self.speed_label.config(text=speed_texts.get(new_engine, '⚡ Fast'))
        self.log_message(f"🎯 Speed indicator updated: {speed_texts.get(new_engine, '⚡ Fast')}")
        
        # Log engine details
        engine_details = {
            'vosk': 'Używa speech_recognition.recognize_vosk() - offline, szybki',
            'speech_recognition': 'Używa speech_recognition.recognize_google() - ultra szybki, wymaga internetu',
            'whisper': 'Używa speech_recognition.recognize_whisper() - szybki i dokładny'
        }
        self.log_message(f"ℹ️  {engine_details.get(new_engine, 'Nieznany silnik')}")
        
        # Reinitialize controller with new engine
        if self.controller:
            self.log_message("🔧 Updating controller with new speech engine...")
            success = self.controller.change_speech_engine(new_engine)
            if success:
                self.log_message("✅ Controller updated with new speech engine")
            else:
                self.log_message("❌ Failed to update controller")
        else:
            self.log_message("❌ Controller not available - will be initialized on next start")
        
        # Update Vosk status display
        if new_engine == 'vosk':
            self.update_vosk_status()
        else:
            self.status_vars['vosk_model'].set("🔧 Using " + new_engine)
            self.log_message(f"📊 Status updated: Using {new_engine}")
    
    def download_vosk_model(self):
        """Download Vosk speech recognition model"""
        self.log_message("📥 Starting Vosk model download...")
        
        # Import and run the download script
        import subprocess
        import sys
        
        # Run the download script in a separate process
        result = subprocess.run([sys.executable, 'download_vosk.py'], 
                             capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            self.log_message("✅ Vosk model downloaded successfully!")
            self.log_message("🔄 Please restart the application to use the new model")
        else:
            error_msg = f"❌ Download failed: {result.stderr}"
            self.log_message(error_msg)
    
    def update_status(self):
        if not self.controller:
            return
        
        # Update game status
        if self.controller.is_game_running():
            self.status_vars['game'].set("🟢 Game Running")
        else:
            self.status_vars['game'].set("🔴 No Game")
        
        # Update champion
        champion = self.controller.get_current_champion()
        if champion:
            self.status_vars['champion'].set(f"🎮 {champion}")
        else:
            self.status_vars['champion'].set("❓ Unknown")
        
        # Update command count
        command_count = self.controller.get_command_count()
        self.status_vars['commands'].set(f"📋 {command_count} commands")
        
        # Update cache status
        status = self.controller.get_status()
        cache_hits = status.get('cache_hits', 0)
        cache_size = status.get('cache_size', 0)
        self.status_vars['cache'].set(f"🚀 {cache_hits} hits ({cache_size} cached)")
        
        # Update speech engine status
        if self.controller:
            if hasattr(self.controller, 'speech_engine'):
                speech_engine = self.controller.speech_engine
                self.log_message(f"🔍 Current speech engine: {speech_engine}")
                if speech_engine == 'vosk':
                    self.update_vosk_status()
                else:
                    self.status_vars['vosk_model'].set(f"🔧 {speech_engine.upper()}")
            else:
                self.log_message("❌ Controller missing speech_engine attribute")
                self.status_vars['vosk_model'].set("❌ Error")
    
    def update_vosk_status(self):
        """Check and update Vosk model status"""
        import os
        
        # Check for Vosk models
        model_paths = [
            "vosk-model-small-pl-0.22",
            "vosk-model-small-en-us-0.15", 
            "vosk-model-pl-0.22",
            "vosk-model-en-us-0.22"
        ]
        
        found_model = None
        current_dir = os.getcwd()
        
        for path in model_paths:
            full_path = os.path.join(current_dir, path)
            if os.path.exists(full_path):
                found_model = path
                break
        
        if found_model:
            self.status_vars['vosk_model'].set(f"✅ {found_model}")
            self.log_message(f"🔍 Vosk model found: {found_model}")
        else:
            self.status_vars['vosk_model'].set("❌ Not Found")
            available_files = [f for f in os.listdir(current_dir) if 'vosk' in f.lower()]
            self.log_message(f"🔍 Vosk models checked in: {current_dir}")
            self.log_message(f"🔍 Available files: {available_files}")
    
    def log_message(self, message: str):
        if hasattr(self, 'log_text') and hasattr(self, 'root') and self.root.winfo_exists():
            timestamp = time.strftime("%H:%M:%S")
            self.log_text.insert('end', f"[{timestamp}] {message}\n")
            self.log_text.see('end')
            self.root.update_idletasks()
        else:
            pass  # No fallback logging
    
    def start_status_updates(self):
        def update_loop():
            while True:
                if hasattr(self, 'root') and self.root.winfo_exists():
                    self.root.after(0, self.update_status)
                    time.sleep(2)
                else:
                    break
        
        status_thread = threading.Thread(target=update_loop, daemon=True)
        status_thread.start()
    
    def run(self):
        self.log_message("🚀 Starting GUI main loop...")
        self.root.mainloop()

if __name__ == "__main__":
    app = LoLVoiceGUI()
    app.run()
