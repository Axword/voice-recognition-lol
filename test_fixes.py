#!/usr/bin/env python3
"""Test all fixes"""

from lol_voice_controller_v2 import LoLVoiceControllerV2

def main():
    controller = LoLVoiceControllerV2('pl_PL')
    
    print("=== TESTING HWEI FIXES ===")
    test_commands = [
        'temat katastrofa',
        'temat spokój', 
        'temat udręka',
        'czyszczenie pędzla',
        'niszczycielski ogień',
        'przeszywający pocisk'
    ]
    
    for cmd in test_commands:
        match = controller.find_best_match(cmd)
        if match:
            phrase, key, confidence = match
            print(f"✅ '{cmd}' -> {key} (score: {confidence:.2f})")
        else:
            print(f"❌ '{cmd}' -> No match")
    
    print("\n=== TESTING ATTACK COMMANDS ===")
    attack_commands = ['attack', 'atak', 'auto']
    for cmd in attack_commands:
        match = controller.find_best_match(cmd)
        if match:
            phrase, key, confidence = match
            print(f"✅ '{cmd}' -> {key} (score: {confidence:.2f})")
        else:
            print(f"❌ '{cmd}' -> No match")
    
    print("\n=== TESTING FLASH KEYBINDS ===")
    flash_commands = ['flash', 'błysk']
    for cmd in flash_commands:
        match = controller.find_best_match(cmd)
        if match:
            phrase, key, confidence = match
            print(f"✅ '{cmd}' -> {key} (score: {confidence:.2f})")
        else:
            print(f"❌ '{cmd}' -> No match")

if __name__ == "__main__":
    main()
