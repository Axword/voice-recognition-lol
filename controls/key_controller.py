from pynput import mouse, keyboard

class KeyController:
    def __init__(self):
        self.mouse = mouse.Controller()
        self.keyboard = keyboard.Controller()

    def press_key(self, key: str):
        if key == "right_click":
            self.mouse.click(mouse.Button.right, 1)
            return
        self.keyboard.press(key)
        self.keyboard.release(key)
