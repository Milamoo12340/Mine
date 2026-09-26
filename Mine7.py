import cv2
import numpy as np
import pydirectinput
import time
import hashlib
import sys
from PIL import ImageGrab

# ==============================================================================
# CONFIGURATION SETTINGS (MAPPED TO YOUR ENVIRONMENT DATA)
# ==============================================================================
# Fixed Window bounds supplied by user diagnostics
WINDOW_LEFT = -7
WINDOW_TOP = 0
WINDOW_WIDTH = 816
WINDOW_HEIGHT = 638

# Absolute screen target coordinates supplied by user diagnostics
AUTOMINE_ICON_X = 42
AUTOMINE_ICON_Y = 327

# Bounding box constraints containing the visual block matrix within the window
# (Clipped inward from the main bounds to prevent clicking top title bars/edges)
GRID_X = max(0, WINDOW_LEFT)
GRID_Y = max(0, WINDOW_TOP)
GRID_W = WINDOW_WIDTH
GRID_H = WINDOW_HEIGHT

# Performance Metrics
BLOCK_REACH_TIMEOUT = 3.0   # Seconds to attempt mining an anomaly block before fallback
MIN_TARGET_SIZE = 400       # Minimum area of pixels required to define an anomaly shape

# Saturated color bands targeting glowing highlight variations
COLOR_BOUNDS = [
    (np.array(), np.array()),     # Red spectrum 1
    (np.array(), np.array()), # Red spectrum 2
    (np.array(), np.array()), # Purple spectrum
    (np.array(), np.array())   # Cyan / Teal spectrum
]
# ==============================================================================

class TargetAndBreakBot:
    def __init__(self):
        self.current_target = None
        self.target_start_time = 0
        self.last_hash = None
        self.last_change_time = time.time()

    def capture_grid_frame(self):
        """Captures only the screen data active inside the game canvas boundaries."""
        try:
            screenshot = ImageGrab.grab(bbox=(GRID_X, GRID_Y, GRID_X + GRID_W, GRID_Y + GRID_H))
            return np.array(screenshot)
        except Exception as e:
            print(f"⚠️ Screen capture read delay encountered ({e}). Retrying loop...")
            time.sleep(0.5)
            return None

    def is_valid_ore_shape(self, contour):
        """Verifies geometric profiles to filter out thin lines and flat circular UI icons."""
        area = cv2.contourArea(contour)
        if area < MIN_TARGET_SIZE:
            return False

        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = float(w) / h
        
        # Eliminate structural grid perimeter lines
        if aspect_ratio > 3.8 or aspect_ratio < 0.26:
            return False

        # Filter out uniform circles/squares like HUD overlay buttons
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0: return False
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        
        if 0.79 < circularity <= 1.0:
            return False

        return True

    def scan_for_ores(self, frame):
        """Scans the display space, isolating the center coordinate coordinates of anomalies."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        master_mask = np.zeros(hsv.shape[:2], dtype="uint8")
        
        for lower, upper in COLOR_BOUNDS:
            mask = cv2.inRange(hsv, lower, upper)
            master_mask = cv2.bitwise_or(master_mask, mask)
            
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        clean_mask = cv2.morphologyEx(master_mask, cv2.MORPH_OPEN, kernel)
        
        contours, _ = cv2.findContours(clean_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        valid_targets = []
        for contour in contours:
            if self.is_valid_ore_shape(contour):
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    # Translate localized region coordinates out to global screen workspace coordinates
                    abs_x = GRID_X + int(M["m10"] / M["m00"])
                    abs_y = GRID_Y + int(M["m01"] / M["m00"])
                    valid_targets.append((abs_x, abs_y))
                    
        return valid_targets

    def execute_teleport_reset(self):
        """Macro function driving click inputs to cycle AutoMine and push back to top."""
        print(f"\n🔄 Execution stall or depth limit hit. Teleporting via screen pos ({AUTOMINE_ICON_X}, {AUTOMINE_ICON_Y})...")
        try:
            pydirectinput.mouseUp()  # Release standard breaking click locks
            time.sleep(0.1)
            
            # Navigate cleanly to the exact auto-mine coordinate position
            pydirectinput.moveTo(AUTOMINE_ICON_X, AUTOMINE_ICON_Y)
            pydirectinput.click()
            time.sleep(0.5)  # Processing safety delay
            
            pydirectinput.click()
            print("🚀 Teleport cycle completed. Re-entering active mining parameters.")
            time.sleep(1.5)  # Grid reconstruction buffer time
        except Exception as e:
            print(f"⚠️ Interface click execution exception ({e}). Continuing script structure...")

    def run_main_loop(self):
        print("🤖 System parameters locked to provided geometry configuration profile.")
        print("Bring the window forward. Activating automation loop matrices in 3 seconds...")
        time.sleep(3)
        
        while True:
            frame = self.capture_grid_frame()
            if frame is None: continue
            
            targets = self.scan_for_ores(frame)
            
            if not targets:
                print("⛏️ No priority blocks sighted. In-game macro mining... Checking depth stall...", end="\r")
                
                # Check pixel states to determine if we hit the floor or are out of reach options
                h, w, _ = frame.shape
                center_zone = frame[int(h*0.3):int(h*0.7), int(w*0.3):int(w*0.7)]
                current_hash = hashlib.md5(center_zone.tobytes()).hexdigest()
                
                if self.last_hash is None:
                    self.last_hash = current_hash
                    self.last_change_time = time.time()
                elif current_hash == self.last_hash:
                    # If scene elements are motionless and no priority targets exist -> process reset
                    if time.time() - self.last_change_time >= BLOCK_REACH_TIMEOUT:
                        self.execute_teleport_reset()
                        self.last_hash = None
                        self.current_target = None
                else:
                    self.last_hash = current_hash
                    self.last_change_time = time.time()
                
                time.sleep(0.1)
                continue
            
            # --- CURSOR TARGETING AND DIRECT PHYSICAL MINING INPUTS ---
            targets.sort(key=lambda pos: pos) # Track priority top-to-bottom
            best_target = targets
            
            # If tracking target initializes freshly or jumps grid locations
            if self.current_target is None or abs(best_target - self.current_target) > 25 or abs(best_target - self.current_target) > 25:
                self.current_target = best_target
                self.target_start_time = time.time()
                
                print(f"\n💎 Anomaly block verified! Overriding cursor to coordinates: {self.current_target}")
                
                # Drive cursor position directly onto the object center point and compress left mouse button
                pydirectinput.moveTo(self.current_target, self.current_target)
                pydirectinput.mouseDown()
                
            # If mouse hold has targeted the same block layout without clearing it beyond threshold time limits
            elif time.time() - self.target_start_time > BLOCK_REACH_TIMEOUT:
                print(f"\n⚠️ Target {self.current_target} flagged as out of reach limit or blocked.")
                pydirectinput.mouseUp()
                self.execute_teleport_reset()
                self.current_target = None
                
            time.sleep(0.05)

if __name__ == "__main__":
    bot = TargetAndBreakBot()
    try:
        bot.run_main_loop()
    except KeyboardInterrupt:
        pydirectinput.mouseUp()
        print("\n🛑 Automated mining routines securely stopped by user command.")
        sys.exit(0)
