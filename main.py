#!/usr/bin/env python3
from controller.lol_whisp_controller import LoLVoiceController
import time


def main():
    controller = LoLVoiceController(debug=True)
    controller.start_listening()
    print("🎮 Voice control active. Say 'Q', 'W', 'E', or ability names.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
        controller.stop_listening()

if __name__ == "__main__":
    main()
