#!/usr/bin/env python3
"""
Modern Tkinter GUI for LoL Voice Controller v0.2
Clean, minimal, dark-themed interface with live status and logs.
"""

from __future__ import annotations

import json
import logging
import os
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Optional

from controller.lol_whisp_controller import LoLVoiceController


class TkLogHandler(logging.Handler):
    """Logging handler that forwards controller logs to the GUI log view."""
    def __init__(self, gui_ref: "LoLVoiceGUI") -> None:
        super().__init__()
        self.gui_ref = gui_ref

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            level = record.levelno
            tag = "info"
            if level >= logging.ERROR:
                tag = "error"
            elif level >= logging.WARNING:
                tag = "warning"
            self.gui_ref.post_log(msg, tag)
        except Exception:
            pass
from concurrent.futures import ThreadPoolExecutor
import traceback

class LoLVoiceGUI:
    """Dark, modern Tkinter GUI for controlling LoL voice automation."""
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.controller: Optional[LoLVoiceController] = None
        self.is_running = False

        # Worker pool for background tasks
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="gui-worker")
        self._pending_tasks = 0  # licznik aktywnych zadań, by poprawnie włączać/wyłączać UI
        self._last_combo_states = {}  # przywracanie stanów comboboxów

        self.config_file = "lol_voice_config.json"
        self.config = self.load_config()

        self.vars = {
            "listening": tk.StringVar(value="Stopped"),
            "game": tk.StringVar(value="No Game"),
            "champion": tk.StringVar(value="No champion"),
            "commands": tk.StringVar(value="0 commands"),
            "model": tk.StringVar(value="google"),
            "last_command": tk.StringVar(value="No commands yet"),
        }

        self.model_var = tk.StringVar(value=self.config.get("recognition_model", "google"))
        self.language_var = tk.StringVar(value=self.config.get("language", "pl_PL"))

        self.setup_window()
        self.setup_style()
        self.create_layout()
        self.attach_controller()
        self.bind_events()
        self.schedule_status_updates()

    def setup_window(self) -> None:
        """Initialize main window properties and center on screen."""
        self.root.title("LoL Voice Controller v0.2")
        self.root.geometry("900x640")
        self.root.minsize(860, 620)
        self.root.configure(bg="#1f2125")
        self.root.update_idletasks()
        w, h = 900, 640
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def setup_style(self) -> None:
        """Configure ttk styles for a dark, modern look."""
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        bg = "#1f2125"
        card_bg = "#2b2f36"
        text = "#e6e6e6"
        muted = "#a8adb4"
        accent = "#00e7a7"
        danger = "#ff5c7c"
        warning = "#f4c430"

        self.root.configure(bg=bg)
        self.style.configure(".", background=bg, foreground=text, fieldbackground=card_bg)

        self.style.configure("Title.TLabel", background=bg, foreground=accent, font=("Segoe UI", 20, "bold"))
        self.style.configure("Subtitle.TLabel", background=bg, foreground=muted, font=("Segoe UI", 10))
        self.style.configure("Muted.TLabel", background=bg, foreground=muted, font=("Segoe UI", 10))
        self.style.configure("Value.TLabel", background=bg, foreground=text, font=("Segoe UI", 11, "bold"))

        self.style.configure("Card.TLabelframe", background=card_bg, foreground=text, borderwidth=0, relief="flat")
        self.style.configure("Card.TLabelframe.Label", background=card_bg, foreground=muted, font=("Segoe UI", 10, "bold"))
        self.style.configure("TFrame", background=bg)
        self.style.configure("Card.TFrame", background=card_bg)

        self.style.configure("TButton", font=("Segoe UI", 10), padding=8)
        self.style.map("TButton",
                       background=[("active", "#2f3540")],
                       relief=[("pressed", "sunken"), ("!pressed", "flat")])

        self.style.configure("Accent.TButton", foreground=bg, background=accent, font=("Segoe UI", 11, "bold"))
        self.style.map("Accent.TButton",
                       background=[("active", "#00d59a")],
                       foreground=[("disabled", "#666666")])

        self.style.configure("Danger.TButton", foreground=bg, background=danger, font=("Segoe UI", 11, "bold"))
        self.style.map("Danger.TButton", background=[("active", "#ff3c62")])

        self.style.configure("Chip.TLabel", background="#26313a", foreground=text, font=("Segoe UI", 9), padding=6)

        self.colors = {"accent": accent, "danger": danger, "warning": warning, "muted": muted, "card": card_bg}

    def create_layout(self) -> None:
        """Build the window layout: header, status, controls, champion, logs."""
        container = ttk.Frame(self.root, padding=24, style="TFrame")
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container, style="TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="LoL Voice Controller", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Automatic champion detection and dynamic voice recognition", style="Subtitle.TLabel").pack(anchor="w")

        header_actions = ttk.Frame(header, style="TFrame")
        header_actions.pack(anchor="e", pady=(10, 0))
        self.start_btn = ttk.Button(header_actions, text="Start Listening", style="Accent.TButton", command=self.toggle_listening, width=18)
        self.start_btn.grid(row=0, column=0, padx=(0, 10))
        self.debug_btn = ttk.Button(header_actions, text="Toggle Debug", command=self.on_toggle_debug, width=16)
        self.debug_btn.grid(row=0, column=1)

        divider = ttk.Frame(container, height=2, style="TFrame")
        divider.pack(fill="x", pady=(16, 8))
        divider.configure(style="TFrame")
        divider.configure(height=2)
        divider_canvas = tk.Canvas(divider, height=2, bg=self.colors["accent"], highlightthickness=0, bd=0)
        divider_canvas.pack(fill="x")

        status = ttk.Frame(container, style="TFrame")
        status.pack(fill="x", pady=(8, 16))

        self.chips = {
            "voice": ttk.Label(status, text="Voice: Stopped", style="Chip.TLabel"),
            "game": ttk.Label(status, text="Game: No Game", style="Chip.TLabel"),
            "champ": ttk.Label(status, text="Champion: -", style="Chip.TLabel"),
            "cmds": ttk.Label(status, text="Commands: 0", style="Chip.TLabel"),
            "model": ttk.Label(status, text="Model: google", style="Chip.TLabel"),
            "last": ttk.Label(status, text="Last: -", style="Chip.TLabel"),
        }

        col = 0
        for key in ("voice", "game", "champ", "cmds", "model", "last"):
            self.chips[key].grid(row=0, column=col, padx=(0 if col == 0 else 8, 8))
            col += 1

        content = ttk.Frame(container, style="TFrame")
        content.pack(fill="both", expand=True)

        left = ttk.Frame(content, style="TFrame")
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        right = ttk.Frame(content, style="TFrame")
        right.pack(side="right", fill="both", expand=True, padx=(10, 0))

        self.controls_card = ttk.Labelframe(left, text="Controls", style="Card.TLabelframe", padding=16)
        self.controls_card.pack(fill="x")

        controls_row = ttk.Frame(self.controls_card, style="Card.TFrame")
        controls_row.pack(fill="x")

        model_frame = ttk.Frame(controls_row, style="Card.TFrame")
        model_frame.pack(side="left", padx=(0, 24))
        ttk.Label(model_frame, text="Recognition Model", style="Muted.TLabel").pack(anchor="w")
        self.model_combo = ttk.Combobox(model_frame, textvariable=self.model_var, values=["google", "vosk", "sphinx"], state="readonly", width=14)
        self.model_combo.pack(pady=(6, 0))

        lang_frame = ttk.Frame(controls_row, style="Card.TFrame")
        lang_frame.pack(side="left", padx=(0, 24))
        ttk.Label(lang_frame, text="Language", style="Muted.TLabel").pack(anchor="w")
        self.lang_combo = ttk.Combobox(lang_frame, textvariable=self.language_var, values=["pl_PL", "en_US"], state="readonly", width=14)
        self.lang_combo.pack(pady=(6, 0))

        buttons_row = ttk.Frame(self.controls_card, style="Card.TFrame")
        buttons_row.pack(fill="x", pady=(12, 0))
        self.test_btn = ttk.Button(buttons_row, text="Test Microphone", command=self.on_test_microphone, width=18)
        self.test_btn.pack(side="left")
        self.update_champ_btn = ttk.Button(buttons_row, text="Refresh Champion", command=self.on_update_champion, width=18)
        self.update_champ_btn.pack(side="left", padx=(12, 0))

        self.champion_card = ttk.Labelframe(left, text="Champion", style="Card.TLabelframe", padding=16)
        self.champion_card.pack(fill="both", expand=True, pady=(12, 0))

        self.champion_name = ttk.Label(self.champion_card, text="No champion detected", style="Value.TLabel")
        self.champion_name.pack(anchor="w")

        self.abilities_frame = ttk.Frame(self.champion_card, style="Card.TFrame")
        self.abilities_frame.pack(fill="x", pady=(10, 0))
        self.ability_labels = {
            "Q": ttk.Label(self.abilities_frame, text="Q: -", style="Muted.TLabel"),
            "W": ttk.Label(self.abilities_frame, text="W: -", style="Muted.TLabel"),
            "E": ttk.Label(self.abilities_frame, text="E: -", style="Muted.TLabel"),
            "R": ttk.Label(self.abilities_frame, text="R: -", style="Muted.TLabel"),
        }
        self.ability_labels["Q"].grid(row=0, column=0, sticky="w", padx=(0, 24), pady=4)
        self.ability_labels["W"].grid(row=0, column=1, sticky="w", padx=(0, 24), pady=4)
        self.ability_labels["E"].grid(row=1, column=0, sticky="w", padx=(0, 24), pady=4)
        self.ability_labels["R"].grid(row=1, column=1, sticky="w", padx=(0, 24), pady=4)

        self.log_card = ttk.Labelframe(right, text="Log", style="Card.TLabelframe", padding=12)
        self.log_card.pack(fill="both", expand=True)

        self.log_text = tk.Text(self.log_card, bg="#1b1e23", fg="#e6e6e6", insertbackground="#e6e6e6",
                                bd=0, relief="flat", wrap="word", height=18, font=("Consolas", 10))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_configure("info", foreground="#cfd8dc")
        self.log_text.tag_configure("warning", foreground=self.colors["warning"])
        self.log_text.tag_configure("error", foreground=self.colors["danger"])

        footer = ttk.Frame(container, style="TFrame")
        footer.pack(fill="x", pady=(10, 0))
        ttk.Label(footer, text="Tips: say natural ability names, the matcher will adapt.", style="Muted.TLabel").pack(anchor="w")

    def bind_events(self) -> None:
        """Bind UI events to handlers."""
        self.model_combo.bind("<<ComboboxSelected>>", self.on_model_change)
        self.lang_combo.bind("<<ComboboxSelected>>", self.on_language_change)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def attach_controller(self) -> None:
        """Create controller instance and connect it to the GUI."""
        try:
            self.controller = LoLVoiceController(language=self.language_var.get(), debug=True)
            if self.model_var.get() != self.controller.recognition_model:
                self.controller.change_recognition_model(self.model_var.get())
            self.save_config()
            self.attach_logger()
            self.post_log("GUI ready.", "info")
            self.update_status(force=True)
        except Exception as exc:
            messagebox.showerror("Initialization Error", str(exc))

    def attach_logger(self) -> None:
        """Attach a logging handler to mirror controller logs inside GUI."""
        if not self.controller:
            return
        handler = TkLogHandler(self)
        handler.setFormatter(logging.Formatter("%(message)s"))
        # uniknij duplikowania handlerów
        if handler not in self.controller.logger.handlers:
            self.controller.logger.addHandler(handler)

    # === Helpers: busy state, async tasks ===

    def set_interactive_enabled(self, enabled: bool) -> None:
        """Enable/disable interactive widgets and set busy cursor."""
        try:
            widgets = [
                getattr(self, "start_btn", None),
                getattr(self, "debug_btn", None),
                getattr(self, "test_btn", None),
                getattr(self, "update_champ_btn", None),
            ]
            combos = [getattr(self, "model_combo", None), getattr(self, "lang_combo", None)]

            for w in widgets:
                if w is not None:
                    w.configure(state=("normal" if enabled else "disabled"))

            for c in combos:
                if c is not None:
                    if enabled:
                        c.configure(state="readonly")
                    else:
                        c.configure(state="disabled")

            self.root.configure(cursor="" if enabled else "watch")
            self.root.update_idletasks()
        except Exception:
            pass

    def _enter_busy(self) -> None:
        self._pending_tasks += 1
        if self._pending_tasks == 1:
            self.set_interactive_enabled(False)

    def _exit_busy(self) -> None:
        self._pending_tasks = max(0, self._pending_tasks - 1)
        if self._pending_tasks == 0:
            self.set_interactive_enabled(True)

    def submit_task(self, label: str, func, *args, on_done=None) -> None:
        """Run blocking func in a worker thread; update UI safely on completion."""
        if not callable(func):
            return
        self._enter_busy()
        self.post_log(f"[Task] {label} ...", "info")

        future = self.executor.submit(func, *args)

        def _finalize(fut):
            err = None
            res = None
            try:
                res = fut.result()
            except Exception as exc:
                err = exc
            def _ui():
                try:
                    if err:
                        tb = traceback.format_exc()
                        self.post_log(f"[Task] {label} failed: {err}", "error")
                        self.post_log(tb, "error")
                        messagebox.showerror("Task Error", f"{label} failed:\n{err}")
                    else:
                        self.post_log(f"[Task] {label} done.", "info")
                        if on_done:
                            try:
                                on_done(res)
                            except Exception as e2:
                                self.post_log(f"on_done error: {e2}", "error")
                    self.update_status(force=False)
                finally:
                    self._exit_busy()
            self.root.after(0, _ui)

        future.add_done_callback(_finalize)

    # === Handlers ===

    def toggle_listening(self) -> None:
        """Start or stop the listening loop in background."""
        if not self.controller:
            return
        if not self.controller.is_listening:
            # Start listening could be blocking: do it in background
            def after_start(_res=None):
                if self.controller.is_listening:
                    self.start_btn.configure(text="Stop Listening", style="Danger.TButton")
                    self.post_log("Listening started.", "info")
                else:
                    self.post_log("Failed to start listening.", "error")
                self.update_status(force=True)
            self.submit_task("Start Listening", self.controller.start_listening, on_done=after_start)
        else:
            def after_stop(_res=None):
                if not self.controller.is_listening:
                    self.start_btn.configure(text="Start Listening", style="Accent.TButton")
                    self.post_log("Listening stopped.", "warning")
                else:
                    self.post_log("Failed to stop listening.", "error")
                self.update_status(force=True)
            self.submit_task("Stop Listening", self.controller.stop_listening, on_done=after_stop)

    def on_test_microphone(self) -> None:
        """Run a short microphone test in background."""
        if not self.controller:
            return
        self.submit_task("Test Microphone", self.controller.test_microphone)

    def on_update_champion(self) -> None:
        """Trigger champion detection refresh in background."""
        if not self.controller:
            return
        self.submit_task("Refresh Champion", self.controller._update_champion, on_done=lambda _r: self.update_status(force=True))

    def on_toggle_debug(self) -> None:
        """Toggle controller debug logging (fast)."""
        if not self.controller:
            return
        # to szybkie, ale na wszelki wypadek można użyć submit_task
        try:
            self.controller.toggle_debug()
            self.post_log("Debug toggled.", "info")
        except Exception as exc:
            self.post_log(f"Debug toggle failed: {exc}", "error")

    def on_model_change(self, event=None) -> None:
        """Handle recognition model change in background (model load can be heavy)."""
        if not self.controller:
            return
        new_model = self.model_var.get()
        current_model = getattr(self.controller, "recognition_model", None)

        def done(ok: bool) -> None:
            if ok:
                self.config["recognition_model"] = new_model
                self.save_config()
                self.post_log(f"Recognition model changed to: {new_model}", "info")
            else:
                # revert combobox selection
                if current_model:
                    self.model_var.set(current_model)
                self.post_log(f"Failed to change model to {new_model}", "error")
            self.update_status(force=True)

        # odpal w tle (np. Vosk może się długo ładować)
        self.submit_task(f"Change Model -> {new_model}", self.controller.change_recognition_model, new_model, on_done=done)

    def on_language_change(self, event=None) -> None:
        """Handle language change and refresh mappings in background."""
        if not self.controller:
            return
        new_lang = self.language_var.get()
        current_lang = getattr(self.controller, "language", None)

        def done(ok: bool) -> None:
            if ok:
                self.config["language"] = new_lang
                self.save_config()
                self.post_log(f"Language changed to: {new_lang}", "info")
            else:
                if current_lang:
                    self.language_var.set(current_lang)
                self.post_log(f"Failed to change language to {new_lang}", "error")
            self.update_status(force=True)

        self.submit_task(f"Change Language -> {new_lang}", self.controller.change_language, new_lang, on_done=done)

    def update_status(self, force: bool = False) -> None:
        """Fetch current status from controller and update GUI labels."""
        if not self.controller:
            return
        try:
            status = self.controller.get_status()
        except Exception as exc:
            self.post_log(f"Status error: {exc}", "error")
            return

        gui = getattr(self.controller, "gui_status", None)

        self.vars["listening"].set("Active" if status.get("listening") else "Stopped")
        self.vars["game"].set("In Game" if status.get("game_active") else "No Game")
        champion_label = "No champion"
        if gui and getattr(gui, "champion", None):
            last = getattr(gui, "last_update", "")
            champion_label = f"{gui.champion} {f'({last})' if last else ''}"
        self.vars["champion"].set(champion_label)
        self.vars["commands"].set(f"{status.get('mappings_count', 0)} commands")
        self.vars["model"].set(status.get("model", "google"))
        last_cmd_text = "-"
        if gui and getattr(gui, "last_command", None):
            last_cmd_text = str(gui.last_command)
        self.vars["last_command"].set(last_cmd_text)

        self.chips["voice"].configure(text=f"Voice: {self.vars['listening'].get()}")
        self.chips["game"].configure(text=f"Game: {self.vars['game'].get()}")
        self.chips["champ"].configure(text=f"Champion: {self.vars['champion'].get()}")
        self.chips["cmds"].configure(text=f"Commands: {status.get('mappings_count', 0)}")
        self.chips["model"].configure(text=f"Model: {self.vars['model'].get()}")
        self.chips["last"].configure(text=f"Last: {self.vars['last_command'].get()}")

        # synchro comboboxa z aktualnym modelem z kontrolera (jeśli zmienił się po stronie kontrolera)
        if self.model_var.get() != self.vars["model"].get():
            self.model_var.set(self.vars["model"].get())

        self.refresh_champion_view()

        if force:
            try:
                self.root.update_idletasks()
            except Exception:
                pass

    def refresh_champion_view(self) -> None:
        """Update champion section with current champion and abilities."""
        if not self.controller or not self.controller.current_champion:
            self.champion_name.configure(text="No champion detected")
            for k in ("Q", "W", "E", "R"):
                self.ability_labels[k].configure(text=f"{k}: -")
            return

        name = self.controller.current_champion
        self.champion_name.configure(text=name)

        abilities = self.controller.data_manager.get_champion_abilities(name)
        for k in ("Q", "W", "E", "R"):
            n = abilities.get(k, "-")
            bind = self.controller.keybinds.get(k, k.lower())
            self.ability_labels[k].configure(text=f"{k}: {n}  →  {bind}")

    def post_log(self, message: str, tag: str = "info") -> None:
        """Append a message to the log view in a thread-safe way."""
        def _append() -> None:
            try:
                self.log_text.configure(state="normal")
                self.log_text.insert("end", message.strip() + "\n", tag)
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
            except Exception:
                pass
        self.root.after(0, _append)

    def schedule_status_updates(self) -> None:
        """Schedule periodic status refresh using Tkinter's event loop."""
        def _tick() -> None:
            self.update_status()
            self.root.after(1000, _tick)
        self.root.after(1000, _tick)

    def load_config(self) -> Dict:
        """Load persistent configuration from JSON file."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"language": "pl_PL", "recognition_model": "google"}

    def save_config(self) -> None:
        """Persist configuration to JSON file."""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as exc:
            self.post_log(f"Error saving config: {exc}", "error")

    def on_close(self) -> None:
        """Gracefully shutdown the controller and close the app."""
        try:
            if self.controller and self.controller.is_listening:
                # stop może blokować – zróbmy to szybko, bez czekania na zakończenie
                try:
                    self.controller.stop_listening()
                except Exception:
                    pass
        finally:
            try:
                # zamknij pulę wątków
                self.executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
            self.root.destroy()

    def run(self) -> None:
        """Start the Tkinter main loop."""
        self.is_running = True
        try:
            self.root.mainloop()
        finally:
            self.is_running = False


if __name__ == "__main__":
    app = LoLVoiceGUI()
    app.run()