#!/usr/bin/env python3
"""
LoL Voice Controller - Main Entry Point
Supports both CLI and GUI modes with real-time status display
"""

import sys
import time
import argparse
import os
from typing import Optional
from datetime import datetime

# Colored output support
try:
    from colorama import init, Fore, Back, Style
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    # Fallback for no colorama
    class Fore:
        GREEN = YELLOW = CYAN = RED = BLUE = MAGENTA = WHITE = RESET = ''
    class Style:
        BRIGHT = DIM = RESET_ALL = ''

from controller.lol_whisp_controller import LoLVoiceController


class CLIInterface:
    """Command-line interface for the voice controller."""
    
    def __init__(self, controller: LoLVoiceController):
        self.controller = controller
        self.last_status_line_length = 0
        
    def clear_screen(self):
        """Clear terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self):
        """Print application header."""
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'='*60}")
        print(f"{Fore.CYAN}{Style.BRIGHT}       LoL Voice Controller - Whisper Edition")
        print(f"{Fore.CYAN}{Style.BRIGHT}{'='*60}{Style.RESET_ALL}\n")
    
    def print_status(self):
        """Print current status in a formatted way."""
        status = self.controller.get_status()
        
        if self.last_status_line_length > 0:
            print('\r' + ' ' * self.last_status_line_length, end='\r')
        
        listening = status.get('listening', False)
        game_active = status.get('game_active', False)
        champion = status.get('champion', 'None')
        mappings = status.get('mappings_count', 0)
        last_cmd = status.get('last_command', '-')
        
        voice_status = f"{Fore.GREEN}● ACTIVE" if listening else f"{Fore.RED}● STOPPED"
        game_status = f"{Fore.GREEN}IN GAME" if game_active else f"{Fore.YELLOW}MENU"
        
        status_parts = [
            f"[{voice_status}{Style.RESET_ALL}]",
            f"[{game_status}{Style.RESET_ALL}]",
            f"[{Fore.CYAN}Champion: {champion}{Style.RESET_ALL}]",
            f"[{Fore.MAGENTA}Commands: {mappings}{Style.RESET_ALL}]",
        ]
        
        if last_cmd and last_cmd != "No commands yet":
            status_parts.append(f"[{Fore.WHITE}Last: {last_cmd[:20]}{Style.RESET_ALL}]")
        
        status_line = " ".join(status_parts)
        
        print(f"\r{status_line}", end='', flush=True)
        self.last_status_line_length = len(status_line)
    
    def print_instructions(self):
        """Print usage instructions."""
        print(f"{Fore.YELLOW}🎮 Voice Commands:{Style.RESET_ALL}")
        print(f"  • Say ability letters: {Fore.GREEN}'Q', 'W', 'E', 'R'{Style.RESET_ALL}")
        print(f"  • Say summoner spells: {Fore.GREEN}'Flash', 'Teleport'{Style.RESET_ALL}")
        print(f"  • Natural ability names work too!\n")
        
        backend = getattr(self.controller, 'whisper_backend', 'unknown')
        backend_info = {
            "pywhispercpp": "C++ (Fast CPU)",
            "faster-whisper-gpu": "GPU Accelerated",
            "faster-whisper-cpu": "Optimized CPU",
            "openai-whisper": "Standard"
        }.get(backend, backend)
        
        print(f"{Fore.CYAN}⚙️  Configuration:{Style.RESET_ALL}")
        print(f"  • Language: {self.controller.language}")
        print(f"  • Whisper Backend: {backend_info}")
        print(f"  • Recognition Mode: {getattr(self.controller.mapping_manager, 'mode', 'letters')}\n")
        
        print(f"{Fore.YELLOW}📌 Controls:{Style.RESET_ALL}")
        print(f"  • Press {Fore.RED}Ctrl+C{Style.RESET_ALL} to stop")
        print(f"  • Press {Fore.GREEN}Enter{Style.RESET_ALL} to see updated status\n")
    
    def run_interactive(self):
        """Run the interactive CLI mode."""
        self.clear_screen()
        self.print_header()
        
        if not self.controller.whisper_model:
            print(f"{Fore.RED}❌ Error: Whisper model not loaded!{Style.RESET_ALL}")
            print("Please install one of: pywhispercpp, faster-whisper, or openai-whisper")
            return
        
        self.print_instructions()
        
        print(f"{Fore.GREEN}🚀 Starting voice recognition...{Style.RESET_ALL}\n")
        self.controller.start_listening()
        
        time.sleep(1)
        print(f"{Fore.GREEN}{Style.BRIGHT}✅ Voice control is now ACTIVE!{Style.RESET_ALL}")
        print(f"{'-'*60}\n")
        try:
            import threading
            def update_status():
                while self.controller.is_listening:
                    self.print_status()
                    time.sleep(1)
            
            status_thread = threading.Thread(target=update_status, daemon=True)
            status_thread.start()
            
            while self.controller.is_listening:
                try:
                    input() 
                    print("\n" + "="*60)
                    self.print_current_detailed_status()
                    print("="*60 + "\n")
                except EOFError:
                    break
        except KeyboardInterrupt:
            print(f"\n\n{Fore.YELLOW}🛑 Shutting down...{Style.RESET_ALL}")
        finally:
            self.controller.stop_listening()
            print(f"{Fore.RED}✓ Voice control stopped.{Style.RESET_ALL}")
    
    def print_current_detailed_status(self):
        """Print detailed current status."""
        status = self.controller.get_status()
        
        print(f"\n{Fore.CYAN}📊 Detailed Status:{Style.RESET_ALL}")
        print(f"  • Listening: {status.get('listening', False)}")
        print(f"  • Game Active: {status.get('game_active', False)}")
        print(f"  • Current Champion: {status.get('champion', 'None')}")
        print(f"  • Loaded Commands: {status.get('mappings_count', 0)}")
        print(f"  • Language: {status.get('language', 'Unknown')}")
        print(f"  • Last Update: {status.get('last_update', 'Never')}")
        print(f"  • Last Command: {status.get('last_command', 'None')}")


def main():
    """Main entry point with argument parsing."""
    
    parser = argparse.ArgumentParser(
        description="LoL Voice Controller - Control League of Legends with your voice",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s              # Start with GUI
  %(prog)s --cli        # Start in CLI mode
  %(prog)s --no-debug   # Start without debug messages
  %(prog)s --lang en_US # Start with English recognition
        """
    )
    
    parser.add_argument(
        "--cli", 
        action="store_true",
        help="Run in CLI mode instead of GUI"
    )
    
    parser.add_argument(
        "--gui",
        action="store_true", 
        help="Run in GUI mode (default)"
    )
    
    parser.add_argument(
        "--lang", "--language",
        default="pl_PL",
        choices=["pl_PL", "en_US"],
        help="Recognition language (default: pl_PL)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        default=True,
        help="Enable debug output (default: True)"
    )
    
    parser.add_argument(
        "--no-debug",
        action="store_false",
        dest="debug",
        help="Disable debug output"
    )
    
    args = parser.parse_args()
    use_cli = args.cli or not args.gui
    
    # If no mode specified, try GUI first
    if not args.cli and not args.gui:
        try:
            from gui.lol_voice_gui import LoLVoiceGUI
            use_cli = False
        except ImportError:
            print(f"{Fore.YELLOW}⚠️  GUI not available, starting in CLI mode{Style.RESET_ALL}")
            use_cli = True
    
    if use_cli:
        # CLI Mode
        try:
            print(f"{Fore.CYAN}Initializing Voice Controller...{Style.RESET_ALL}")
            controller = LoLVoiceController(
                language=args.lang,
                debug=args.debug
            )
            
            cli = CLIInterface(controller)
            cli.run_interactive()
            
        except Exception as e:
            print(f"{Fore.RED}❌ Error: {e}{Style.RESET_ALL}")
            import traceback
            if args.debug:
                traceback.print_exc()
            sys.exit(1)
    else:
        # GUI Mode
        try:
            from gui.lol_voice_gui import LoLVoiceGUI
            
            print(f"{Fore.CYAN}Starting GUI...{Style.RESET_ALL}")
            app = LoLVoiceGUI()
            app.run()
            
        except ImportError as e:
            print(f"{Fore.RED}❌ Cannot start GUI: {e}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Try running with --cli flag for command-line mode{Style.RESET_ALL}")
            sys.exit(1)
        except Exception as e:
            print(f"{Fore.RED}❌ GUI Error: {e}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    # Handle Ctrl+C gracefully
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Interrupted by user{Style.RESET_ALL}")
        sys.exit(0)
    except Exception as e:
        print(f"{Fore.RED}Fatal error: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        sys.exit(1)