"""
Modern Tkinter GUI for LoL Voice Controller with Whisper
Enhanced with sensitivity control, mapping display, tabs, language selection and translations
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import os
from typing import Dict, Optional
import time
import logging
try:
    from resource_helper import resource_path, get_config_path, ensure_default_config, get_logs_dir
except ImportError:
    # Fallback if resource_helper not found
    def resource_path(path):
        return path
    def get_config_path():
        return 'config/config.json'
    def ensure_default_config():
        return get_config_path()
    def get_logs_dir():
        return 'logs'
from controller.lol_whisp_controller import LoLVoiceController
from gui.translations import TRANSLATIONS

class TkLogHandler(logging.Handler):
    """Logging handler that forwards controller logs to the GUI."""
    def __init__(self, gui_ref):
        super().__init__()
        self.gui_ref = gui_ref

    def emit(self, record):
        try:
            msg = self.format(record)
            tag = "info"
            
            if record.levelno >= logging.ERROR:
                tag = "error"
            elif record.levelno >= logging.WARNING:
                tag = "warning"
            elif "🎤 Heard:" in msg or "Heard:" in msg:
                tag = "command"
            elif "🎯 Executed:" in msg or "💥" in msg or "Executed:" in msg:
                tag = "success"
            
            self.gui_ref.post_console_log(msg, tag)
        except Exception:
            pass


class LoLVoiceGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.controller: Optional[LoLVoiceController] = None
        self.is_running = False
        self.config_file = get_config_path()
        self.config = self.load_config()
        
        self.colors = {
            'bg': '#2b2b2b',
            'fg': '#ffffff',
            'accent': '#00ff88',
            'danger': '#ff4444',
            'warning': '#ffaa00',
            'muted': '#999999',
            'card': '#363636',
            'success': '#00cc66'
        }
        
        # Language configuration for speech recognition
        self.available_languages = {
            'pl_PL': '🇵🇱 Polish',
            'en_US': '🇺🇸 English',
            'de_DE': '🇩🇪 German',
            'fr_FR': '🇫🇷 French',
            'es_ES': '🇪🇸 Spanish',
            'it_IT': '🇮🇹 Italian',
        }
        
        # UI Language
        self.ui_language = self.config.get('ui_language', 'en_US')
        if self.ui_language not in TRANSLATIONS:
            self.ui_language = 'en_US'
        
        self.setup_window()
        self.create_widgets()
        self.initialize_controller()
        self.start_status_updates()

    def t(self, key: str) -> str:
        """Translate key to current UI language."""
        return TRANSLATIONS.get(self.ui_language, TRANSLATIONS['en_US']).get(key, key)

    def setup_window(self):
        """Configure main window."""
        self.root.title(f"{self.t('title')} - Whisper Edition")
        self.root.geometry("920x780")
        self.root.configure(bg=self.colors['bg'])
        self.root.resizable(False, False)
        
        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (920 // 2)
        y = (self.root.winfo_screenheight() // 2) - (780 // 2)
        self.root.geometry(f"920x780+{x}+{y}")
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        """Create all GUI widgets."""
        main_frame = tk.Frame(self.root, bg=self.colors['bg'])
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Title
        title_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        title_frame.pack(fill='x', pady=(0, 15))
        
        title = tk.Label(title_frame, text=f"🎮 {self.t('title')}",
                        font=('Segoe UI', 24, 'bold'),
                        fg=self.colors['accent'], bg=self.colors['bg'])
        title.pack(side='left')
        
        self.whisper_label = tk.Label(title_frame, text="",
                                     font=('Segoe UI', 10),
                                     fg=self.colors['muted'],
                                     bg=self.colors['bg'])
        self.whisper_label.pack(side='left', padx=(20, 0))
        
        # Create notebook (tabs)
        style = ttk.Style()
        style.theme_use('default')
        style.configure('TNotebook', background=self.colors['bg'], borderwidth=0)
        style.configure('TNotebook.Tab', 
                       background=self.colors['card'],
                       foreground=self.colors['fg'],
                       padding=[20, 10],
                       font=('Segoe UI', 10, 'bold'))
        style.map('TNotebook.Tab',
                 background=[('selected', self.colors['accent'])],
                 foreground=[('selected', self.colors['bg'])])
        
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True)
        
        # Create tabs
        self.control_tab = tk.Frame(self.notebook, bg=self.colors['bg'])
        self.mappings_tab = tk.Frame(self.notebook, bg=self.colors['bg'])
        self.console_tab = tk.Frame(self.notebook, bg=self.colors['bg'])
        
        self.notebook.add(self.control_tab, text=f"  {self.t('tab_control')}  ")
        self.notebook.add(self.mappings_tab, text=f"  {self.t('tab_mappings')}  ")
        self.notebook.add(self.console_tab, text=f"  {self.t('tab_console')}  ")
        
        self.create_control_tab()
        self.create_mappings_tab()
        self.create_console_tab()
        
    def create_control_tab(self):
        """Create main control tab with scrollbar."""
        canvas = tk.Canvas(self.control_tab, bg=self.colors['bg'], highlightthickness=0)
        scrollbar = tk.Scrollbar(self.control_tab, orient="vertical", command=canvas.yview)

        scrollable_frame = tk.Frame(canvas, bg=self.colors['bg'])
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=(0, 0))
        scrollbar.pack(side="right", fill="y")
        
        # Mouse wheel scrolling - only when tab is active
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        # Bind when entering canvas area
        canvas.bind('<Enter>', _bind_mousewheel)
        canvas.bind('<Leave>', _unbind_mousewheel)
        
        # Sections
        self.create_status_section(scrollable_frame)
        self.create_options_section(scrollable_frame)
        self.create_controls_section(scrollable_frame)
        self.create_champion_section(scrollable_frame)

    def create_status_section(self, parent):
        """Create status indicators."""
        status_frame = tk.LabelFrame(parent, text=f" {self.t('status')} ",
                                    font=('Segoe UI', 10, 'bold'),
                                    fg=self.colors['fg'],
                                    bg=self.colors['bg'],
                                    relief='groove', bd=1)
        status_frame.pack(fill='x', pady=(0, 12), padx=5)
        
        status_container = tk.Frame(status_frame, bg=self.colors['bg'])
        status_container.pack(fill='x', padx=15, pady=10)
        
        self.status_vars = {
            'listening': tk.StringVar(value=f"🔴 {self.t('stopped')}"),
            'game': tk.StringVar(value=f"🔴 {self.t('no_game')}"),
            'champion': tk.StringVar(value=f"❓ {self.t('none')}"),
            'commands': tk.StringVar(value="0"),
            'last': tk.StringVar(value=self.t('none')),
        }
        
        labels = [
            (f"{self.t('voice')}:", self.status_vars['listening']),
            (f"{self.t('game')}:", self.status_vars['game']),
            (f"{self.t('champion')}:", self.status_vars['champion']),
            (f"{self.t('commands')}:", self.status_vars['commands']),
            (f"{self.t('last_cmd')}:", self.status_vars['last']),
        ]
        
        for i, (label_text, var) in enumerate(labels):
            frame = tk.Frame(status_container, bg=self.colors['bg'])
            frame.pack(side='left', padx=(0, 25))
            
            tk.Label(frame, text=label_text,
                    font=('Segoe UI', 9),
                    fg=self.colors['muted'],
                    bg=self.colors['bg']).pack(anchor='w')
            
            tk.Label(frame, textvariable=var,
                    font=('Segoe UI', 9, 'bold'),
                    fg=self.colors['fg'],
                    bg=self.colors['bg']).pack(anchor='w')

    def create_options_section(self, parent):
        """Create options section."""
        options_frame = tk.LabelFrame(parent, text=f" {self.t('options')} ",
                                     font=('Segoe UI', 10, 'bold'),
                                     fg=self.colors['fg'],
                                     bg=self.colors['bg'],
                                     relief='groove', bd=1)
        options_frame.pack(fill='x', pady=(0, 12), padx=5)
        
        options_container = tk.Frame(options_frame, bg=self.colors['bg'])
        options_container.pack(fill='x', padx=15, pady=12)
        
        left_frame = tk.Frame(options_container, bg=self.colors['bg'])
        left_frame.pack(side='left', fill='both', expand=True)
        
        # Recognition Language
        lang_frame = tk.Frame(left_frame, bg=self.colors['bg'])
        lang_frame.pack(side='left', padx=(0, 30))
        
        tk.Label(lang_frame, text=f"{self.t('language')}:",
                font=('Segoe UI', 9, 'bold'),
                fg=self.colors['fg'],
                bg=self.colors['bg']).pack(anchor='w', pady=(0, 3))
        
        current_lang = self.config.get('language', 'pl_PL')
        lang_display = self.available_languages.get(current_lang, current_lang)
        self.language_button = tk.Button(lang_frame, text=lang_display,
                               font=('Segoe UI', 9),
                               fg=self.colors['accent'],
                               bg=self.colors['card'],
                               relief='flat',
                               cursor='hand2',
                               padx=15, pady=5,
                               command=self.show_language_menu)
        self.language_button.pack(anchor='w')
        
        # Flash Key
        flash_frame = tk.Frame(left_frame, bg=self.colors['bg'])
        flash_frame.pack(side='left', padx=(0, 30))
        
        tk.Label(flash_frame, text=f"{self.t('flash_key')}:",
                font=('Segoe UI', 9, 'bold'),
                fg=self.colors['fg'],
                bg=self.colors['bg']).pack(anchor='w', pady=(0, 3))
        
        flash_buttons = tk.Frame(flash_frame, bg=self.colors['bg'])
        flash_buttons.pack()
        
        self.flash_key_var = tk.StringVar(value=self.config.get('flash_key', 'D'))
        
        for key in ['D', 'F']:
            rb = tk.Radiobutton(flash_buttons,
                              text=key,
                              variable=self.flash_key_var,
                              value=key,
                              font=('Segoe UI', 9),
                              fg=self.colors['fg'],
                              bg=self.colors['bg'],
                              selectcolor=self.colors['card'],
                              activebackground=self.colors['bg'],
                              activeforeground=self.colors['accent'],
                              command=self.on_flash_key_change)
            rb.pack(side='left', padx=5)
        
        # UI Language
        ui_lang_frame = tk.Frame(left_frame, bg=self.colors['bg'])
        ui_lang_frame.pack(side='left')
        
        tk.Label(ui_lang_frame, text="UI Language:",
                font=('Segoe UI', 9, 'bold'),
                fg=self.colors['fg'],
                bg=self.colors['bg']).pack(anchor='w', pady=(0, 3))
        
        ui_lang_display = self.available_languages.get(self.ui_language, '🇬🇧 English')
        self.ui_language_button = tk.Button(ui_lang_frame, text=ui_lang_display,
                               font=('Segoe UI', 9),
                               fg=self.colors['accent'],
                               bg=self.colors['card'],
                               relief='flat',
                               cursor='hand2',
                               padx=15, pady=5,
                               command=self.show_ui_language_menu)
        self.ui_language_button.pack(anchor='w')

    def show_ui_language_menu(self):
        """Show UI language selection menu."""
        menu = tk.Menu(self.root, tearoff=0, 
                      bg=self.colors['card'],
                      fg=self.colors['fg'],
                      activebackground=self.colors['accent'],
                      activeforeground=self.colors['bg'])
        
        for lang_code in ['en_US', 'pl_PL', 'de_DE']:
            if lang_code in TRANSLATIONS:
                lang_name = self.available_languages.get(lang_code, lang_code)
                menu.add_command(label=lang_name,
                               command=lambda lc=lang_code: self.change_ui_language(lc))
        
        try:
            x = self.ui_language_button.winfo_rootx()
            y = self.ui_language_button.winfo_rooty() + self.ui_language_button.winfo_height()
            menu.post(x, y)
        except:
            pass

    def change_ui_language(self, lang_code: str):
        """Change UI language."""
        if lang_code == self.ui_language:
            return
        
        self.config['ui_language'] = lang_code
        self.save_config()
        
        messagebox.showinfo("Language Changed", 
                          "UI language will change after restart.\n\n"
                          "Die UI-Sprache wird nach dem Neustart geändert.\n\n"
                          "Język UI zmieni się po restarcie.")

    def on_flash_key_change(self):
        """Handle flash key change."""
        flash_key = self.flash_key_var.get()
        self.config['flash_key'] = flash_key
        self.save_config()
        
        if self.controller and hasattr(self.controller, 'mapping_manager'):
            self.controller.mapping_manager.flash_key = flash_key
            
        self.post_console_log(f"⚙️ Flash key changed to: {flash_key}", "info")

    def show_language_menu(self):
        """Show language selection menu."""
        menu = tk.Menu(self.root, tearoff=0, 
                      bg=self.colors['card'],
                      fg=self.colors['fg'],
                      activebackground=self.colors['accent'],
                      activeforeground=self.colors['bg'])
        
        for lang_code, lang_name in self.available_languages.items():
            menu.add_command(label=lang_name,
                           command=lambda lc=lang_code: self.change_language(lc))
        
        try:
            x = self.language_button.winfo_rootx()
            y = self.language_button.winfo_rooty() + self.language_button.winfo_height()
            menu.post(x, y)
        except:
            pass

    def change_language(self, lang_code: str):
        """Change recognition language."""
        old_lang = self.config.get('language', 'pl_PL')
        if lang_code == old_lang:
            return
            
        self.config['language'] = lang_code
        self.save_config()
        
        lang_display = self.available_languages.get(lang_code, lang_code)
        self.language_button.configure(text=lang_display)
        
        if self.controller:
            # Update controller language
            self.controller.language = lang_code
            
            # Reload mapping manager with new language
            from controls.mapping_manager import MappingManager
            self.controller.mapping_manager = MappingManager(lang_code)
            
            # Apply current settings
            self.controller.mapping_manager.mode = self.config.get('recognition_mode', 'letters')
            self.controller.mapping_manager.set_sensitivity(self.config.get('spell_sensitivity', 'medium'))
            self.controller.mapping_manager.flash_key = self.config.get('flash_key', 'D')
            
            # Refresh champion mappings if in game
            if self.controller.current_champion_name:
                champion_mappings = self.controller.ability_manager.create_voice_mappings_from_api()
                if champion_mappings:
                    self.controller.mapping_manager.load_champion_mappings(champion_mappings)
            
            self.post_console_log(f"🌍 {self.t('language_changed')}: {lang_display}", "success")
            self.update_mapping_display()

    def create_controls_section(self, parent):
        """Create control buttons with mode selection and sensitivity."""
        controls_frame = tk.LabelFrame(parent, text=f" {self.t('controls')} ",
                                      font=('Segoe UI', 10, 'bold'),
                                      fg=self.colors['fg'],
                                      bg=self.colors['bg'],
                                      relief='groove', bd=1)
        controls_frame.pack(fill='x', pady=(0, 12), padx=5)
        
        controls_container = tk.Frame(controls_frame, bg=self.colors['bg'])
        controls_container.pack(fill='x', padx=15, pady=12)
        
        # Main button
        self.main_button = tk.Button(controls_container,
                                     text=f"🎤 {self.t('start_listening')}",
                                     font=('Segoe UI', 12, 'bold'),
                                     fg=self.colors['bg'],
                                     bg=self.colors['accent'],
                                     activebackground=self.colors['success'],
                                     activeforeground=self.colors['bg'],
                                     relief='flat', bd=0,
                                     padx=30, pady=10,
                                     cursor='hand2',
                                     command=self.toggle_listening)
        self.main_button.pack(pady=(0, 8))
        
        # Info label
        info_label = tk.Label(controls_container,
                            text=f"💡 {self.t('info_start')}",
                            font=('Segoe UI', 9),
                            fg=self.colors['muted'],
                            bg=self.colors['bg'])
        info_label.pack(pady=(0, 12))
        
        # Mode selection
        mode_frame = tk.Frame(controls_container, bg=self.colors['bg'])
        mode_frame.pack(fill='x', pady=(0, 8))
        
        tk.Label(mode_frame, text=f"{self.t('recognition_mode')}:",
                font=('Segoe UI', 10, 'bold'),
                fg=self.colors['fg'],
                bg=self.colors['bg']).pack(anchor='w', pady=(0, 5))
        
        modes_container = tk.Frame(mode_frame, bg=self.colors['bg'])
        modes_container.pack()
        
        self.mode_var = tk.StringVar(value=self.config.get('recognition_mode', 'letters'))
        
        letters_rb = tk.Radiobutton(modes_container,
                                   text=f"📝 {self.t('letters_mode')}",
                                   variable=self.mode_var,
                                   value="letters",
                                   font=('Segoe UI', 10),
                                   fg=self.colors['fg'],
                                   bg=self.colors['bg'],
                                   selectcolor=self.colors['card'],
                                   activebackground=self.colors['bg'],
                                   activeforeground=self.colors['accent'],
                                   command=self.on_mode_change)
        letters_rb.pack(side='left', padx=15)
        
        spells_rb = tk.Radiobutton(modes_container,
                                  text=f"🗣️ {self.t('spells_mode')}",
                                  variable=self.mode_var,
                                  value="spells",
                                  font=('Segoe UI', 10),
                                  fg=self.colors['fg'],
                                  bg=self.colors['bg'],
                                  selectcolor=self.colors['card'],
                                  activebackground=self.colors['bg'],
                                  activeforeground=self.colors['accent'],
                                  command=self.on_mode_change)
        spells_rb.pack(side='left', padx=15)
        
        # Sensitivity control
        self.sensitivity_frame = tk.Frame(controls_container, bg=self.colors['bg'])
        self.sensitivity_frame.pack(fill='x', pady=(8, 0))
        
        tk.Label(self.sensitivity_frame,
                text=f"{self.t('sensitivity')}:",
                font=('Segoe UI', 10, 'bold'),
                fg=self.colors['fg'],
                bg=self.colors['bg']).pack(anchor='w', pady=(0, 5))
        
        sens_container = tk.Frame(self.sensitivity_frame, bg=self.colors['bg'])
        sens_container.pack()
        
        self.sensitivity_var = tk.StringVar(value=self.config.get('spell_sensitivity', 'medium'))
        
        sensitivities = [
            (self.t('low_strict'), "low"),
            (self.t('medium'), "medium"),
            (self.t('high_loose'), "high")
        ]
        
        for text, value in sensitivities:
            rb = tk.Radiobutton(sens_container,
                              text=text,
                              variable=self.sensitivity_var,
                              value=value,
                              font=('Segoe UI', 9),
                              fg=self.colors['fg'],
                              bg=self.colors['bg'],
                              selectcolor=self.colors['card'],
                              activebackground=self.colors['bg'],
                              activeforeground=self.colors['accent'],
                              command=self.on_sensitivity_change)
            rb.pack(side='left', padx=10)
        
        self.sens_desc = tk.Label(self.sensitivity_frame,
                                 text="",
                                 font=('Segoe UI', 8),
                                 fg=self.colors['muted'],
                                 bg=self.colors['bg'])
        self.sens_desc.pack(pady=(5, 0))
        
        self.update_sensitivity_visibility()

    def create_champion_section(self, parent):
        """Create champion info and mapping display."""
        champ_frame = tk.LabelFrame(parent, text=f" {self.t('champion_mappings')} ",
                                   font=('Segoe UI', 10, 'bold'),
                                   fg=self.colors['fg'],
                                   bg=self.colors['bg'],
                                   relief='groove', bd=1)
        champ_frame.pack(fill='x', pady=(0, 15), padx=5)
        
        self.champ_container = tk.Frame(champ_frame, bg=self.colors['bg'])
        self.champ_container.pack(fill='x', padx=15, pady=12)
        
        self.champ_name_label = tk.Label(self.champ_container,
                                         text=self.t('no_champion'),
                                         font=('Segoe UI', 12, 'bold'),
                                         fg=self.colors['accent'],
                                         bg=self.colors['bg'])
        self.champ_name_label.pack(pady=(0, 10))
        
        # Voice commands
        tk.Label(self.champ_container,
                text=f"{self.t('voice_commands')}:",
                font=('Segoe UI', 10, 'bold'),
                fg=self.colors['fg'],
                bg=self.colors['bg']).pack(anchor='w', pady=(0, 8))
        
        self.mapping_labels = {}
        abilities_container = tk.Frame(self.champ_container, bg=self.colors['bg'])
        abilities_container.pack(fill='x')
        
        for i, key in enumerate(['Q', 'W', 'E', 'R']):
            frame = tk.Frame(abilities_container, bg=self.colors['card'])
            frame.pack(side='left', padx=5, pady=2, fill='both', expand=True)
            
            key_label = tk.Label(frame, text=f"{key}:",
                               font=('Segoe UI', 10, 'bold'),
                               fg=self.colors['accent'],
                               bg=self.colors['card'])
            key_label.pack(anchor='w', padx=10, pady=(8, 2))
            
            cmd_label = tk.Label(frame,
                               text=self.t('ability_not_loaded'),
                               font=('Segoe UI', 9),
                               fg=self.colors['fg'],
                               bg=self.colors['card'],
                               wraplength=180,
                               justify='left')
            cmd_label.pack(anchor='w', padx=10, pady=(0, 8))
            
            self.mapping_labels[key] = {
                'command': cmd_label,
            }
        
        self.extra_info = tk.Label(self.champ_container,
                                  text=f"💡 {self.t('always_available')}",
                                  font=('Segoe UI', 9),
                                  fg=self.colors['muted'],
                                  bg=self.colors['bg'])
        self.extra_info.pack(anchor='w', pady=(12, 0))

    def create_mappings_tab(self):
        """Create command mappings reference tab."""
        container = tk.Frame(self.mappings_tab, bg=self.colors['bg'])
        container.pack(fill='both', expand=True, padx=20, pady=20)
        
        title = tk.Label(container,
                        text=f"📖 {self.t('available_commands')}",
                        font=('Segoe UI', 16, 'bold'),
                        fg=self.colors['accent'],
                        bg=self.colors['bg'])
        title.pack(anchor='w', pady=(0, 15))
        
        # Create scrollable frame
        canvas = tk.Canvas(container, bg=self.colors['bg'], highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors['bg'])
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Get flash key from config
        flash_key = self.config.get('flash_key', 'D').upper()
        summ2_key = 'F' if flash_key == 'D' else 'D'
        
        commands = {
            self.t('cat_abilities_letters'): [
                ("Q", "Activate Q ability / Aktywuj umiejętność Q"),
                ("W", "Activate W ability / Aktywuj umiejętność W"),
                ("E", "Activate E ability / Aktywuj umiejętność E"),
                ("R / Ultimate / Ulta", "Activate R ability / Aktywuj umiejętność R"),
            ],
            self.t('cat_abilities_spells'): [
                ("[Spell Name] / [Nazwa zaklęcia]", "Say the actual spell name (e.g., 'Dark Binding', 'Rocket Jump') / Powiedz nazwę zaklęcia"),
                ("Ultimate / Ulta", "Also works for R ability in spell mode / Działa też na R w trybie nazw"),
            ],
            self.t('cat_summoner'): [
                (f"Flash / Flasz / Błysk ({flash_key})", "Use Flash / Użyj Flash"),
                (f"Teleport / TP / Teleportacja ({summ2_key})", f"Use Teleport (key: {summ2_key}) / Użyj Teleportacji"),
                (f"Heal / Hil / Leczenie ({summ2_key})", f"Use Heal (key: {summ2_key}) / Użyj Leczenia"),
                (f"Barrier / Bariera / Shield / Tarcza ({summ2_key})", f"Use Barrier (key: {summ2_key}) / Użyj Bariery"),
                (f"Ignite / Ignajt / Podpalenie ({summ2_key})", f"Use Ignite (key: {summ2_key}) / Użyj Podpalenia"),
                (f"Exhaust / Wyczerpanie ({summ2_key})", f"Use Exhaust (key: {summ2_key}) / Użyj Wyczerpania"),
                (f"Cleanse / Clean / Oczyszczenie ({summ2_key})", f"Use Cleanse (key: {summ2_key}) / Użyj Oczyszczenia"),
                (f"Ghost / Duch ({summ2_key})", f"Use Ghost (key: {summ2_key}) / Użyj Ducha"),
                (f"Smite / Smajt / Karanie ({summ2_key})", f"Use Smite (key: {summ2_key}) / Użyj Karania"),
            ],
            self.t('cat_movement'): [
                ("Stop / Zatrzymaj / Stój / Halt", "Stop movement (S key) / Zatrzymaj ruch (klawisz S)"),
                ("Back / Baza / Recall / Powrót / Base", "Recall to base (B key) / Powrót do bazy (klawisz B)"),
                ("Attack / Atak", "Attack move (A key) / Ruch z atakiem (klawisz A)"),
            ],
            self.t('cat_shop'): [
                ("Shop / Sklep", "Open shop (P key) / Otwórz sklep (klawisz P)"),
            ],
            self.t('cat_special'): [
                ("Random / Losowa / Cokolwiek / Losowo", "Press random ability (Q, W, E, or R) / Naciśnij losową umiejętność"),
                ("Escape / Esc / Anuluj / Cancel", "Press Escape key / Naciśnij klawisz Escape"),
            ],
            self.t('cat_easter'): [
                ("Niewygodnie mi się siedzi",  "🎭"),
                ("Niewdzięczna gówno gra", "😤"),
                ("No i wyłączam streama", "📴"),
            ],
        }
        
        for category, cmds in commands.items():
            cat_frame = tk.LabelFrame(scrollable_frame,
                                    text=f" {category} ",
                                    font=('Segoe UI', 11, 'bold'),
                                    fg=self.colors['accent'],
                                    bg=self.colors['bg'],
                                    relief='groove',
                                    bd=1)
            cat_frame.pack(fill='x', pady=(0, 15))
            
            cmd_container = tk.Frame(cat_frame, bg=self.colors['bg'])
            cmd_container.pack(fill='x', padx=15, pady=10)
            
            for cmd, desc in cmds:
                cmd_frame = tk.Frame(cmd_container, bg=self.colors['card'])
                cmd_frame.pack(fill='x', pady=3)
                
                emoji = "🎭" if category == self.t('cat_easter') else "🎤"
                
                tk.Label(cmd_frame,
                        text=f"  {emoji}  {cmd}",
                        font=('Segoe UI', 10, 'bold'),
                        fg=self.colors['accent'],
                        bg=self.colors['card'],
                        width=35,
                        anchor='w').pack(side='left', padx=10, pady=8)
                
                tk.Label(cmd_frame,
                        text=desc,
                        font=('Segoe UI', 9),
                        fg=self.colors['fg'],
                        bg=self.colors['card'],
                        anchor='w').pack(side='left', fill='x', expand=True, padx=10)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind('<Enter>', _bind_mousewheel)
        canvas.bind('<Leave>', _unbind_mousewheel)

    def create_console_tab(self):
        """Create console logs tab."""
        container = tk.Frame(self.console_tab, bg=self.colors['bg'])
        container.pack(fill='both', expand=True, padx=20, pady=20)
        
        header = tk.Frame(container, bg=self.colors['bg'])
        header.pack(fill='x', pady=(0, 10))
        
        title = tk.Label(header,
                        text=f"💻 {self.t('tab_console')}",
                        font=('Segoe UI', 16, 'bold'),
                        fg=self.colors['accent'],
                        bg=self.colors['bg'])
        title.pack(side='left')
        
        clear_btn = tk.Button(header,
                            text=self.t('clear_console'),
                            font=('Segoe UI', 9),
                            fg=self.colors['fg'],
                            bg=self.colors['card'],
                            activebackground='#444444',
                            relief='flat',
                            bd=0,
                            padx=15,
                            pady=5,
                            cursor='hand2',
                            command=self.clear_console)
        clear_btn.pack(side='right')
        
        text_frame = tk.Frame(container, bg=self.colors['bg'])
        text_frame.pack(fill='both', expand=True)
        
        self.console_text = tk.Text(text_frame,
                                   bg='#1e1e1e',
                                   fg='#00ff88',
                                   font=('Consolas', 9),
                                   wrap='word',
                                   relief='flat',
                                   bd=0,
                                   insertbackground=self.colors['accent'])
        
        console_scrollbar = tk.Scrollbar(text_frame, command=self.console_text.yview)
        self.console_text.configure(yscrollcommand=console_scrollbar.set)
        
        self.console_text.pack(side='left', fill='both', expand=True)
        console_scrollbar.pack(side='right', fill='y')
        
        self.console_text.tag_configure('info', foreground=self.colors['fg'])
        self.console_text.tag_configure('success', foreground=self.colors['accent'])
        self.console_text.tag_configure('warning', foreground=self.colors['warning'])
        self.console_text.tag_configure('error', foreground=self.colors['danger'])
        self.console_text.tag_configure('command', foreground='#4fc3f7')
        
        # Mouse wheel scrolling for console
        def _on_mousewheel(event):
            self.console_text.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_mousewheel(event):
            self.console_text.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_mousewheel(event):
            self.console_text.unbind_all("<MouseWheel>")
        
        text_frame.bind('<Enter>', _bind_mousewheel)
        text_frame.bind('<Leave>', _unbind_mousewheel)

    def initialize_controller(self):
        """Initialize the voice controller."""
        try:
            self.post_console_log(self.t('initializing'), "info")
            
            language = self.config.get('language', 'pl_PL')
            self.controller = LoLVoiceController(language=language, debug=True)
            
            handler = TkLogHandler(self)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.controller.logger.addHandler(handler)
            
            if hasattr(self.controller, 'whisper_backend'):
                backend_map = {
                    "pywhispercpp": "Whisper C++",
                    "faster-whisper-gpu": "GPU",
                    "faster-whisper-cpu": "CPU",
                    "openai-whisper": "OpenAI"
                }
                backend_text = backend_map.get(self.controller.whisper_backend, "Unknown")
                self.whisper_label.configure(text=f"[{backend_text}]")
            
            if self.mode_var.get() != self.controller.mapping_manager.mode:
                self.controller.mapping_manager.mode = self.mode_var.get()
                
            if self.sensitivity_var.get() != self.controller.mapping_manager.sensitivity:
                self.controller.mapping_manager.set_sensitivity(self.sensitivity_var.get())
            
            # Set flash key
            if hasattr(self.controller, 'mapping_manager'):
                flash_key = self.config.get('flash_key', 'D')
                self.controller.mapping_manager.flash_key = flash_key
            
            lang_display = self.available_languages.get(language, language)
            self.language_button.configure(text=lang_display)
            
            self.post_console_log(f"✅ {self.t('ready')}", "success")
        except Exception as e:
            self.post_console_log(f"❌ Failed to initialize: {e}", "error")
            messagebox.showerror("Error", f"Failed to initialize controller:\n{str(e)}")

    def on_mode_change(self):
        """Handle recognition mode change."""
        mode = self.mode_var.get()
        self.config['recognition_mode'] = mode
        self.save_config()
        
        if self.controller:
            self.controller.mapping_manager.mode = mode
            self.controller.mapping_manager.command_cache.clear()
            
        self.update_sensitivity_visibility()
        self.update_mapping_display()
        
        mode_text = self.t('letters_mode') if mode == 'letters' else self.t('spells_mode')
        self.post_console_log(f"⚙️ {self.t('mode_changed')}: {mode_text}", "info")

    def on_sensitivity_change(self):
        """Handle sensitivity change."""
        sensitivity = self.sensitivity_var.get()
        self.config['spell_sensitivity'] = sensitivity
        self.save_config()
        
        if self.controller:
            self.controller.mapping_manager.set_sensitivity(sensitivity)
            
        self.update_sensitivity_description()
        self.post_console_log(f"🎚️ {self.t('sensitivity_changed')}: {sensitivity}", "info")

    def update_sensitivity_visibility(self):
        """Show/hide sensitivity based on mode."""
        if self.mode_var.get() == "spells":
            self.sensitivity_frame.pack(fill='x', pady=(8, 0))
            self.update_sensitivity_description()
        else:
            self.sensitivity_frame.pack_forget()

    def update_sensitivity_description(self):
        """Update sensitivity description."""
        sens = self.sensitivity_var.get()
        desc = self.t(f'sens_desc_{sens}')
        self.sens_desc.configure(text=desc)

    def update_mapping_display(self):
        """Update the display of current voice mappings."""
        if not self.controller:
            return
            
        mode = self.mode_var.get()
        
        if mode == "letters":
            for key in ['Q', 'W', 'E', 'R']:
                self.mapping_labels[key]['command'].configure(
                    text=f'{self.t("say")}: "{key}"'
                )
        else:
            if hasattr(self.controller, 'ability_manager'):
                abilities = self.controller.ability_manager.display_mappings
                if abilities and len(abilities) > 0:
                    for key in ['Q', 'W', 'E', 'R']:
                        if key in abilities:
                            name = abilities[key].get('name', '-')
                            self.mapping_labels[key]['command'].configure(
                                text=f'{self.t("say")}: "{name}"'
                            )
                        else:
                            self.mapping_labels[key]['command'].configure(
                                text=self.t('ability_not_loaded')
                            )
                else:
                    for key in ['Q', 'W', 'E', 'R']:
                        self.mapping_labels[key]['command'].configure(
                            text=self.t('ability_not_loaded')
                        )

    def toggle_listening(self):
        """Start or stop listening."""
        if not self.controller:
            self.post_console_log("❌ Controller not initialized", "error")
            return
            
        if not self.controller.is_listening:
            def start():
                self.controller.start_listening()
                self.root.after(0, lambda: self.on_listening_started())
                
            self.main_button.configure(text="Starting...", state='disabled')
            threading.Thread(target=start, daemon=True).start()
        else:
            def stop():
                self.controller.stop_listening()
                self.root.after(0, lambda: self.on_listening_stopped())
                
            self.main_button.configure(text="Stopping...", state='disabled')
            threading.Thread(target=stop, daemon=True).start()

    def on_listening_started(self):
        """Called when listening starts."""
        self.is_running = True
        self.main_button.configure(
            text=f"🔴 {self.t('stop_listening')}",
            bg=self.colors['danger'],
            state='normal'
        )
        self.status_vars['listening'].set(f"🟢 {self.t('active')}")

    def on_listening_stopped(self):
        """Called when listening stops."""
        self.is_running = False
        self.main_button.configure(
            text=f"🎤 {self.t('start_listening')}",
            bg=self.colors['accent'],
            state='normal'
        )
        self.status_vars['listening'].set(f"🔴 {self.t('stopped')}")

    def update_status(self):
        """Update status display."""
        if not self.controller:
            return
            
        try:
            status = self.controller.get_status()
            
            if status.get('listening'):
                self.status_vars['listening'].set(f"🟢 {self.t('active')}")
            else:
                self.status_vars['listening'].set(f"🔴 {self.t('stopped')}")
                
            if status.get('game_active'):
                self.status_vars['game'].set(f"🟢 {self.t('in_game')}")
            else:
                self.status_vars['game'].set(f"🔴 {self.t('no_game')}")
                
            champion = status.get('champion')
            if champion:
                self.status_vars['champion'].set(f"🎮 {champion}")
                self.champ_name_label.configure(text=champion)
                self.update_mapping_display()
            else:
                self.status_vars['champion'].set(f"❓ {self.t('none')}")
                self.champ_name_label.configure(text=self.t('no_champion'))
                
            if hasattr(self.controller, 'mapping_manager'):
                stats = self.controller.mapping_manager.get_statistics()
                count = stats.get('total_active', 0)
                self.status_vars['commands'].set(str(count))
                
            last = status.get('last_command', 'None')
            if last and last != "No commands yet":
                self.status_vars['last'].set(last[:20])
                
        except Exception as e:
            pass

    def post_console_log(self, message: str, tag: str = "info"):
        """Add message to console log (thread-safe)."""
        def append():
            try:
                self.console_text.configure(state='normal')
                timestamp = time.strftime("%H:%M:%S")
                formatted = f"[{timestamp}] {message}\n"
                self.console_text.insert('end', formatted, tag)
                self.console_text.see('end')
                self.console_text.configure(state='disabled')
                
                lines = int(self.console_text.index('end-1c').split('.')[0])
                if lines > 500:
                    self.console_text.configure(state='normal')
                    self.console_text.delete('1.0', '50.0')
                    self.console_text.configure(state='disabled')
            except:
                pass
                
        self.root.after(0, append)

    def clear_console(self):
        """Clear the console log."""
        self.console_text.configure(state='normal')
        self.console_text.delete('1.0', 'end')
        self.console_text.configure(state='disabled')
        self.post_console_log("Console cleared", "info")

    def start_status_updates(self):
        """Start periodic status updates."""
        def update_loop():
            if self.controller:
                self.update_status()
            self.root.after(2000, update_loop)
            
        self.root.after(2000, update_loop)

    def load_config(self) -> Dict:
        """Load configuration."""
        ensure_default_config()
        config_path = get_config_path()
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading config: {e}")
        
        return {
            'recognition_mode': 'letters',
            'spell_sensitivity': 'medium',
            'language': 'pl_PL',
            'ui_language': 'en_US',
            'flash_key': 'D'
        }

    def save_config(self):
        """Save configuration."""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.post_console_log(f"Error saving config: {e}", "error")

    def on_close(self):
        """Handle window close."""
        if self.controller and self.controller.is_listening:
            self.controller.stop_listening()
        self.save_config()
        self.root.destroy()

    def run(self):
        """Start the GUI."""
        self.root.mainloop()


if __name__ == "__main__":
    app = LoLVoiceGUI()
    app.run()