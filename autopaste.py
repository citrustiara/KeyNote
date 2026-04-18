import platform
import time

def trigger_paste():
    # Local imports to avoid requiring keyboard in headless tests if ever
    import keyboard
    time.sleep(0.1)
    os_name = platform.system()
    if os_name == "Darwin":
        keyboard.send("cmd+v")
    else:
        keyboard.send("ctrl+v")
