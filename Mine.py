import cv2
import numpy as np
import pydirectinput
import time
import hashlib
import sys
from PIL import ImageGrab

# ==============================================================================
# SELF-HEALING CONFIGURATION
# ==============================================================================
GAME_WINDOW_TITLE = "Game"  # Change this to match your game window title

# Absolute X/Y coordinates of your "Auto Mine" pickaxe button
AUTOMINE_ICON_X = 960  
AUTOMINE_ICON_Y = 950  

STUCK_TIMEOUT = 3.5  # Seconds of screen stillness before forcing a teleport reset

# HSV color range for the highlights (adjust if the shade changes down the hole)
PURPLE_LOWER = np.array([130, 50, 50])
PURPLE_UPPER = np.array([165, 255, 255])
# ==============================================================================

class AdvancedAnomalyBot:
    def __init__(self):
        self.window_rect = None
        self.last_hash = None
        self.last_change_time = time.time()
        
    def locate_game_window(self):
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)
            if windows:
                win = windows[0]
                if win.isMinimized: win.restore()
                win.activate()
                time.sleep(0.5)
                self.window_rect = (win.left, win.top, win.width, win.height)
                print(f"✅ Found game window! Position: {self.window_rect}")
                return True
        except Exception:
            pass
        self.window_rect = (0, 0, 1920, 1080)
        return True

    def capture_roi(self):
        try:
            x, y, w, h = self.window_rect
            x, y = max(0, x), max(0, y)
            w, h = max(100, w), max(100, h)
            screenshot = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            return np.array(screenshot)
        except Exception:
            self.locate_game_window()
            return None

    def is_actual_ore(self, contour):
        """
        Analyzes the geometry of a shape to ensure it is a clunky block/chest 
        and NOT a UI icon or a straight grid line.
        """
        # 1. Ignore tiny floating artifacts or single pixels
        area = cv2.contourArea(contour)
        if area < 400: 
            return False
            
        # 2. Filter out straight grid lines using a bounding box comparison
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = float(w) / h
        
        # If the shape is an incredibly long thin line (like a grid line), skip it
        if aspect_ratio > 4.0 or aspect_ratio < 0.25:
            return False
            
        # 3. Filter out perfect UI icons (like circles or perfect squares)
        # We calculate the complexity of the shape outline
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0: return False
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        
        # In-game UI buttons/icons usually have a highly uniform shape (circularity near 0.8 - 1.0)
        # Clunky ores with irregular textures will have a lower, chaotic circularity score
        if 0.75 < circularity <= 1.0:
            # Looks like a clean UI icon element, skip it
            return False
            
        return True

    def trigger_teleport_reset(self):
        print("\n🔄 Screen freeze detected! Resetting to top via dynamic teleport...")
        try:
            pydirectinput.mouseUp()
            time.sleep(0.1)
            pydirectinput.moveTo(AUTOMINE_ICON_X, AUTOMINE_ICON_Y)
            pydirectinput.click()
            time.sleep(0.6)
            pydirectinput.click()
            time.sleep(1.5)
        except Exception as e:
            print(f"⚠️ Teleport error ({e}). Retrying loop...")

    def monitor_loop(self):
        self.locate_game_window()
        print("\n🔥 System Armed! Activate your auto-miner. Script running...")
        
        frame = self.capture_roi()
        if frame is not None:
            self.last_hash = hashlib.md5(frame.tobytes()).hexdigest()
        self.last_change_time = time.time()

        while True:
            frame = self.capture_roi()
            if frame is None: continue

            # --- ANOMALY DETECTION ENGINE ---
            # Convert screen to HSV color space to look for the purple highlight
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            purple_mask = cv2.inRange(hsv, PURPLE_LOWER, PURPLE_UPPER)
            
            # Find the shapes of all purple objects currently on the screen
            contours, _ = cv2.findContours(purple_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            valid_ore_visible = False
            for contour in contours:
                # If the shape passes our geometry tests, it's a real block target!
                if self.is_actual_ore(contour):
                    valid_ore_visible = True
                    break

            # --- STUCK & MOTION ENGINE ---
            # Crop the center section of the viewport to watch for structural mining progress
            h, w, _ = frame.shape
            center_zone = frame[int(h*0.3):int(h*0.7), int(w*0.3):int(w*0.7)]
            current_hash = hashlib.md5(center_zone.tobytes()).hexdigest()

            if current_hash == self.last_hash:
                stuck_duration = time.time() - self.last_change_time
                print(f"⏳ Monitoring mine depth... Stuck time: {stuck_duration:.1f}s | Ore Sighted: {valid_ore_visible}", end="\r")
                
                # If the screen is frozen OR we are stuck staring at blocks out of reach
                if stuck_duration >= STUCK_TIMEOUT:
                    self.trigger_teleport_reset()
                    self.last_change_time = time.time()
            else:
                # Things are moving/breaking successfully -> Reset the stuck timer safely
                self.last_hash = current_hash
                self.last_change_time = time.time()

            time.sleep(0.2)

if __name__ == "__main__":
    bot = AdvancedAnomalyBot()
    try:
        bot.monitor_loop()
    except KeyboardInterrupt:
        sys.exit(0)
