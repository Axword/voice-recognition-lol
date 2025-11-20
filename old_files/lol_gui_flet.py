import asyncio
import json
import os
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict

import flet as ft

from lol_voice_controller import LoLVoiceControllerV2


class LoLVoiceGUI:
    def __init__(self):
        self.page: Optional[ft.Page] = None
        self.controller: Optional[LoLVoiceControllerV2] = None
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="flet-worker")
        self.config_file = "lol_voice_config.json"
        self.config = self.load_config()

        # UI refs
        self.listening_chip = None
        self.game_chip = None
        self.champ_chip = None
        self.cmds_chip = None
        self.model_chip = None
        self.last_chip = None

        self.champion_name_label = None
        self.ability_labels = {}
        self.log_view = None
        self.start_button = None
        self.debug_button = None
        self.test_button = None
        self.refresh_champ_button = None
        self.model_dropdown = None
        self.lang_dropdown = None

    def load_config(self) -> Dict:
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"language": "pl_PL", "recognition_model": "google"}

    def save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as exc:
            self.post_log(f"Error saving config: {exc}", "error")

    async def init_controller(self):
        try:
            self.controller = LoLVoiceControllerV2(
                language=self.config.get("language", "pl_PL"),
                debug=True
            )
            current_model = self.config.get("recognition_model", "google")
            if current_model != self.controller.recognition_model:
                await self.run_in_executor(self.controller.change_recognition_model, current_model)
            self.post_log("Controller initialized.", "info")
        except Exception as e:
            self.show_error("Initialization Error", str(e))

    def run_in_executor(self, func, *args):
        """Run blocking function in thread pool without blocking UI."""
        future = self.executor.submit(func, *args)
        return asyncio.wrap_future(future)

    def post_log(self, message: str, level: str = "info"):
        if not self.log_view:
            return
        color_map = {
            "info": ft.Colors.BLUE_GREY_300,
            "warning": ft.Colors.AMBER_400,
            "error": ft.Colors.RED_400,
        }
        self.log_view.controls.append(
            ft.Text(message.strip(), size=12, color=color_map.get(level, ft.Colors.WHITE))
        )
        self.log_view.scroll_to(offset=-1, duration=300)
        if self.page:
            self.page.update()

    def show_error(self, title: str, message: str):
        dlg = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=lambda _: self.page.close(dlg))],
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    async def toggle_listening(self, e):
        if not self.controller:
            return

        if not self.controller.is_listening:
            self.start_button.disabled = True
            self.start_button.text = "Starting..."
            self.page.update()

            try:
                await self.run_in_executor(self.controller.start_listening)
                self.start_button.text = "Stop Listening"
                self.start_button.style = ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.RED_400)
                self.post_log("Listening started.", "info")
            except Exception as exc:
                self.post_log(f"Start failed: {exc}", "error")
                self.show_error("Start Error", str(exc))
            finally:
                self.start_button.disabled = False
        else:
            self.start_button.disabled = True
            self.start_button.text = "Stopping..."
            self.page.update()

            try:
                await self.run_in_executor(self.controller.stop_listening)
                self.start_button.text = "Start Listening"
                self.start_button.style = ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.GREEN_400)
                self.post_log("Listening stopped.", "warning")
            except Exception as exc:
                self.post_log(f"Stop failed: {exc}", "error")
                self.show_error("Stop Error", str(exc))
            finally:
                self.start_button.disabled = False

        await self.update_status()

    async def test_microphone(self, e):
        if not self.controller:
            return
        self.test_button.disabled = True
        self.page.update()
        try:
            await self.run_in_executor(self.controller.test_microphone)
            self.post_log("Microphone test completed.", "info")
        except Exception as exc:
            self.post_log(f"Microphone test failed: {exc}", "error")
            self.show_error("Mic Test Error", str(exc))
        finally:
            self.test_button.disabled = False

    async def refresh_champion(self, e):
        if not self.controller:
            return
        self.refresh_champ_button.disabled = True
        self.page.update()
        try:
            await self.run_in_executor(self.controller._update_champion)
            self.post_log("Champion refreshed.", "info")
        except Exception as exc:
            self.post_log(f"Refresh failed: {exc}", "error")
            self.show_error("Refresh Error", str(exc))
        finally:
            self.refresh_champ_button.disabled = False
        await self.update_status()

    async def toggle_debug(self, e):
        if not self.controller:
            return
        try:
            self.controller.toggle_debug()
            self.post_log("Debug toggled.", "info")
        except Exception as exc:
            self.post_log(f"Debug toggle failed: {exc}", "error")

    async def change_model(self, e):
        if not self.controller:
            return
        new_model = self.model_dropdown.value
        current = getattr(self.controller, "recognition_model", "google")

        self.model_dropdown.disabled = True
        self.page.update()

        try:
            success = await self.run_in_executor(self.controller.change_recognition_model, new_model)
            if success:
                self.config["recognition_model"] = new_model
                self.save_config()
                self.post_log(f"Model changed to: {new_model}", "info")
            else:
                raise Exception("Model change failed internally.")
        except Exception as exc:
            self.post_log(f"Failed to change model: {exc}", "error")
            self.model_dropdown.value = current
            self.show_error("Model Change Error", str(exc))
        finally:
            self.model_dropdown.disabled = False

        await self.update_status()

    async def change_language(self, e):
        if not self.controller:
            return
        new_lang = self.lang_dropdown.value
        current = getattr(self.controller, "language", "pl_PL")

        self.lang_dropdown.disabled = True
        self.page.update()

        try:
            success = await self.run_in_executor(self.controller.change_language, new_lang)
            if success:
                self.config["language"] = new_lang
                self.save_config()
                self.post_log(f"Language changed to: {new_lang}", "info")
            else:
                raise Exception("Language change failed.")
        except Exception as exc:
            self.post_log(f"Failed to change language: {exc}", "error")
            self.lang_dropdown.value = current
            self.show_error("Language Error", str(exc))
        finally:
            self.lang_dropdown.disabled = False

        await self.update_status()

    async def update_status(self):
        if not self.controller:
            return

        try:
            status = await self.run_in_executor(self.controller.get_status)
        except Exception as exc:
            self.post_log(f"Status fetch error: {exc}", "error")
            return

        gui = getattr(self.controller, "gui_status", None)

        listening = "Active" if status.get("listening") else "Stopped"
        game = "In Game" if status.get("game_active") else "No Game"

        champion_label = "No champion"
        if gui and hasattr(gui, "champion") and gui.champion:
            last = getattr(gui, "last_update", "")
            champion_label = f"{gui.champion} ({last})" if last else gui.champion

        commands = status.get("mappings_count", 0)
        model = status.get("model", "google")

        last_cmd = "-"
        if gui and hasattr(gui, "last_command") and gui.last_command:
            last_cmd = str(gui.last_command)

        # Update chips
        self.listening_chip.label.value = f"Voice: {listening}"
        self.game_chip.label.value = f"Game: {game}"
        self.champ_chip.label.value = f"Champion: {champion_label}"
        self.cmds_chip.label.value = f"Commands: {commands}"
        self.model_chip.label.value = f"Model: {model}"
        self.last_chip.label.value = f"Last: {last_cmd}"

        # Update champion view
        await self.refresh_champion_view()

        if self.page:
            self.page.update()

    async def refresh_champion_view(self):
        if not self.controller or not self.controller.current_champion:
            self.champion_name_label.value = "No champion detected"
            for key in ["Q", "W", "E", "R"]:
                self.ability_labels[key].value = f"{key}: -"
            return

        name = self.controller.current_champion
        self.champion_name_label.value = name

        abilities = self.controller.data_manager.get_champion_abilities(name)
        for key in ["Q", "W", "E", "R"]:
            ability_name = abilities.get(key, "-")
            bind = self.controller.keybinds.get(key, key.lower())
            self.ability_labels[key].value = f"{key}: {ability_name} → {bind}"

    async def periodic_status_update(self):
        while True:
            await asyncio.sleep(1)
            await self.update_status()
                
    def create_status_chip(self, text: str) -> ft.Chip:
        return ft.Chip(
            label=ft.Text(text, size=12, weight=ft.FontWeight.W_500),
            bgcolor=ft.Colors.GREY_800,
            height=32,
            padding=ft.padding.all(6),
            label_padding=ft.padding.symmetric(horizontal=12, vertical=4),
        )
    
    async def build_ui(self, page: ft.Page):
        self.page = page
        page.title = "LoL Voice Controller v0.2"
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 20
        page.window_width = 900
        page.window_height = 640
        page.window_min_width = 860
        page.window_min_height = 620
        page.scroll = "adaptive"

        await self.init_controller()

        # Header
        header = ft.Column([
            ft.Text("LoL Voice Controller", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_400),
            ft.Text("Automatic champion detection and dynamic voice recognition", size=12, color=ft.Colors.GREY_500),
        ], spacing=4)

        # Action buttons
        self.start_button = ft.ElevatedButton(
            "Start Listening",
            style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.GREEN_400),
            on_click=self.toggle_listening,
            width=160
        )
        self.debug_button = ft.OutlinedButton("Toggle Debug", on_click=self.toggle_debug, width=140)

        header_actions = ft.Row([self.start_button, self.debug_button], alignment=ft.MainAxisAlignment.END)

        # Status chips — elegancko i bez duplikacji
        self.listening_chip = self.create_status_chip("Voice: Stopped")
        self.game_chip = self.create_status_chip("Game: No Game")
        self.champ_chip = self.create_status_chip("Champion: -")
        self.cmds_chip = self.create_status_chip("Commands: 0")
        self.model_chip = self.create_status_chip("Model: google")
        self.last_chip = self.create_status_chip("Last: -")

        chips_row = ft.Row([
            self.listening_chip, self.game_chip, self.champ_chip,
            self.cmds_chip, self.model_chip, self.last_chip
        ], wrap=True, spacing=8)

        # Divider
        divider = ft.Divider(height=2, color=ft.Colors.TEAL_400)

        # Controls card
        self.model_dropdown = ft.Dropdown(
            label="Recognition Model",
            value=self.config.get("recognition_model", "google"),
            options=[ft.dropdown.Option(m) for m in ["google", "vosk", "sphinx"]],
            width=200,
            on_change=self.change_model
        )
        self.lang_dropdown = ft.Dropdown(
            label="Language",
            value=self.config.get("language", "pl_PL"),
            options=[ft.dropdown.Option(l) for l in ["pl_PL", "en_US"]],
            width=200,
            on_change=self.change_language
        )

        controls_row = ft.Row([self.model_dropdown, self.lang_dropdown], spacing=20)

        self.test_button = ft.ElevatedButton("Test Microphone", on_click=self.test_microphone)
        self.refresh_champ_button = ft.ElevatedButton("Refresh Champion", on_click=self.refresh_champion)

        buttons_row = ft.Row([self.test_button, self.refresh_champ_button], spacing=12)

        controls_card = ft.Container(
            content=ft.Column([
                controls_row,
                buttons_row
            ], spacing=16),
            padding=20,
            border_radius=12,
            bgcolor=ft.Colors.GREY_900,
            margin=ft.margin.only(bottom=20)
        )

        # Champion card
        self.champion_name_label = ft.Text("No champion detected", size=18, weight=ft.FontWeight.BOLD)

        self.ability_labels = {
            "Q": ft.Text("Q: -", size=14, color=ft.Colors.GREY_300),
            "W": ft.Text("W: -", size=14, color=ft.Colors.GREY_300),
            "E": ft.Text("E: -", size=14, color=ft.Colors.GREY_300),
            "R": ft.Text("R: -", size=14, color=ft.Colors.GREY_300),
        }

        abilities_grid = ft.Column([
            ft.Row([self.ability_labels["Q"], self.ability_labels["W"]], spacing=30),
            ft.Row([self.ability_labels["E"], self.ability_labels["R"]], spacing=30),
        ], spacing=8)

        champion_card = ft.Container(
            content=ft.Column([
                self.champion_name_label,
                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                abilities_grid
            ]),
            padding=20,
            border_radius=12,
            bgcolor=ft.Colors.GREY_900,
            expand=True
        )

        # Log view
        self.log_view = ft.ListView(expand=True, spacing=5, padding=10, auto_scroll=True)
        log_card = ft.Container(
            content=self.log_view,
            padding=15,
            border_radius=12,
            bgcolor=ft.Colors.GREY_900,
            expand=True
        )

        # Layout
        main_layout = ft.Row([
            ft.Column([
                controls_card,
                champion_card
            ], expand=1, spacing=20),
            ft.Column([
                log_card
            ], expand=1, spacing=20)
        ], expand=True, spacing=20)

        footer = ft.Text("Tips: say natural ability names, the matcher will adapt.", size=12, color=ft.Colors.GREY_500)

        page.add(
            header,
            header_actions,
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
            divider,
            chips_row,
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
            main_layout,
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
            footer
        )

        # Start background tasks
        asyncio.create_task(self.periodic_status_update())

    async def on_close(self):
        if self.controller and self.controller.is_listening:
            try:
                await self.run_in_executor(self.controller.stop_listening)
            except Exception:
                pass
        self.executor.shutdown(wait=False, cancel_futures=True)


async def main(page: ft.Page):
    app = LoLVoiceGUI()
    await app.build_ui(page)


if __name__ == "__main__":
    ft.app(target=main)