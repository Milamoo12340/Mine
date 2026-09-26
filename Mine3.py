import time
import hashlib
import numpy as np
import pydirectinput
from PIL import ImageGrab

# ==============================================================================
# CONFIGURATION SETTINGS
# ==============================================================================
# A small screen box inside the mining area to monitor for movement/changes
# (e.g., center screen where your character is breaking blocks)
SCAN_X, SCAN_Y, SCAN_W, SCAN_H = 860, 440, 200, 200  

# Absolute X/Y coordinates of your "Auto Mine" pickaxe button
AUTOMINE_ICON_X = 960  
AUTOMINE_ICON_Y = 950  

# How many seconds of total stillness/no screen changes before we assume we are stuck
STUCK_TIMEOUT = 3.0  
# ==============================================================================

def get_screen_hash():
    """Takes a quick screenshot of the mining zone and returns a unique hash string."""
    screenshot = ImageGrab.grab(bbox=(SCAN_X, SCAN_Y, SCAN_X + SCAN_W, SCAN_Y + SCAN_H))
    # Convert image data into a string of numbers to check for changes
    img_bytes = np.array(screenshot).tobytes()
    return hashlib.md5(img_bytes).hexdigest()

def trigger_teleport_reset():
    """Breaks the auto-mine lock by toggling the button off and back on."""
    print("\n⚠️ Screen freeze detected! Resetting to the top...")
    
    # Move to the icon and click it OFF to break the game's automation lock
    pydirectinput.moveTo(AUTOMINE_ICON_X, AUTOMINE_ICON_Y)
    pydirectinput.click()
    time.sleep(0.5) # Wait for the game to register the stop command
    
    # Click it back ON to teleport back to the top of the grid and restart auto-mining
    pydirectinput.click()
    print("🚀 Teleport successful. Resuming stuck-monitoring loop...")
    time.sleep(1.5) # Buffer time to allow the teleport screen transition to clear

def run_unstuck_bot():
    print("🤖 Unstuck Monitor Ready. Bring the game window to the foreground!")
    print("Activate your in-game Auto-Mine now.")
    time.sleep(3)
    
    last_hash = get_screen_hash()
    last_change_time = time.time()
    
    while True:
        current_hash = get_screen_hash()
        
        # If the screen data matches the previous check, the visual state is frozen
        if current_hash == last_hash:
            time_stuck = time.time() - last_change_time
            print(f"⏳ Screen is static... Checked for: {time_stuck:.1f}s", end="\r")
            
            if time_stuck >= STUCK_TIMEOUT:
                trigger_teleport_reset()
                # Reset timers after triggering the teleport
                last_hash = get_screen_hash()
                last_change_time = time.time()
        else:
            # The screen changed (blocks are breaking, things are moving!) -> Reset timer
            last_hash = current_hash
            last_change_time = time.time()
            
        time.sleep(0.2) # Sample the screen 5 times a second to keep CPU usage low

if __name__ == "__main__":
    run_unstuck_bot()
