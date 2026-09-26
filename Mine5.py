import cv2
import numpy as np
import pydirectinput
import time
import hashlib
import sys
from PIL import ImageGrab

# ==============================================================================
# CONFIGURATION SETTINGS
# ==============================================================================
GAME_WINDOW_TITLE = "Roblox"  # Exact title on the game's top window bar

# Absolute X/Y coordinates of your "Auto Mine" pickaxe button 
AUTOMINE_ICON_X = 49  
AUTOMINE_ICON_Y = 332
WINDOW_WIDTH = 816
WINDOW_HEIGHT = 638

# Tuning Parameters
BLOCK_REACH_TIMEOUT = 3.0   # Seconds to hold click on an ore before skipping/resetting
MIN_TARGET_SIZE = 500       # Minimum pixel area of a highlighted block anomaly

# HSV Color Masking Boundaries (Isolates glowing Purples, Reds, and Cyans)
# Calibrate these to match your game's unique highlight brightness
COLOR_BOUNDS = [
    (np.array([0, 150, 150]), np.array([10, 255, 255])),     # Red 1
    (np.array([165, 150, 150]), np.array([180, 255, 255])), # Red 2
    (np.array([130, 100, 100]), np.array([160, 255, 255])), # Purple
    (np.array([80, 100, 100]), np.array([100, 255, 255]))   # Cyan / Turquoise
]
# ==============================================================================

class CompleteMiningBot:
    def __init__(self):
        self.window_rect = None
        self.current_target = None
        self.target_start_time = 0
        self.last_hash = None
        self.last_change_time = time.time()
        
    def locate_game_window(self):
        """Finds the window position dynamically to handle moving/resizing."""
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)
            if windows:
                win = windows[0]
                if win.isMinimized: win.restore()
                win.activate()
                time.sleep(0.5)
                self.window_rect = (win.left, win.top, win.width, win.height)
                print(f"✅ Linked to game window at: {self.window_rect}")
                return True
        except Exception as e:
            print(f"⚠️ Window look-up failed ({e}). Defaulting to screen-space fallback.")
        self.window_rect = (-7, 0, 816, 638)
        return True

    def capture_frame(self):
        """Safely captures screen image matrices inside window dimensions."""
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
        """Filters out thin straight grid lines and perfect round geometric UI icons."""
        area = cv2.contourArea(contour)
        if area < MIN_TARGET_SIZE: 
            return False
            
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = float(w) / h
        
        # If it's a long stringy line (like a grid border), ignore it
        if aspect_ratio > 4.0 or aspect_ratio < 0.25:
            return False
            
        # Check structural complexity (circularity)
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0: return False
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        
        # Perfect shapes/flat text plates score 0.8 - 1.0. 
        # Irregular ores/clunky boxes score much lower.
        if 0.78 < circularity <= 1.0:
            return False
            
        return True

    def scan_for_ores(self, frame):
        """Processes the screenshot frame to isolate actual mining block centers."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        master_mask = np.zeros(hsv.shape[:2], dtype="uint8")
        
        for lower, upper in COLOR_BOUNDS:
            mask = cv2.inRange(hsv, lower, upper)
            master_mask = cv2.bitwise_or(master_mask, mask)
            
        # Clean up loose stray pixel artifacts
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        clean_mask = cv2.morphologyEx(master_mask, cv2.MORPH_OPEN, kernel)
        
        contours, _ = cv2.findContours(clean_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        valid_targets = []
        for contour in contours:
            if self.is_actual_ore(contour):
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    # Map the relative mask coordinates back to absolute screen positions
                    abs_x = self.window_rect[0] + int(M["m10"] / M["m00"])
                    abs_y = self.window_rect[1] + int(M["m01"] / M["m00"])
                    valid_targets.append((abs_x, abs_y))
                    
        return valid_targets

    def trigger_teleport_reset(self):
        """Toggles the auto-mine macro switch off/on to push player back to the top."""
        print("\n🔄 Reach block limit or pit floor encountered! Teleporting...")
        try:
            pydirectinput.mouseUp()  # Break active manual click hold
            time.sleep(0.1)
            
            # Click off
            pydirectinput.moveTo(AUTOMINE_ICON_X, AUTOMINE_ICON_Y)
            pydirectinput.click()
            time.sleep(0.5)
            
            # Click on
            pydirectinput.click()
            print("🚀 Teleport processed. Returning to active tracking loops.")
            time.sleep(1.5)  # Screen layout stabilization buffer
        except Exception as e:
            print(f"⚠️ UI error during click sequence ({e}).")

    def run_bot(self):
        print("🤖 Core Engine Booting up. Bring your game window to the foreground!")
        self.locate_game_window()
        print("Starting in 3 seconds...")
        time.sleep(3)
        
        while True:
            frame = self.capture_frame()
            if frame is None: continue
            
            # Search for real blocks matching the color and geometric profile
            targets = self.scan_for_ores(frame)
            
            if not targets:
                print("⛏️ No priority blocks found. Letting game mine down / checking state...", end="\r")
                
                # Check for screen movement to see if the game's auto-mine got stuck at the bottom
                h, w, _ = frame.shape
                center_zone = frame[int(h*0.3):int(h*0.7), int(w*0.3):int(w*0.7)]
                current_hash = hashlib.md5(center_zone.tobytes()).hexdigest()
                
                if self.last_hash is None:
                    self.last_hash = current_hash
                    self.last_change_time = time.time()
                elif current_hash == self.last_hash:
                    # Screen isn't moving and no ores are left in reach -> must be at the bottom
                    if time.time() - self.last_change_time >= BLOCK_REACH_TIMEOUT:
                        self.trigger_teleport_reset()
                        self.last_hash = None
                        self.current_target = None
                else:
                    self.last_hash = current_hash
                    self.last_change_time = time.time()
                
                time.sleep(0.1)
                continue
                
            # --- TARGET SELECTION & MINING INTERACTION ENGINE ---
            # Sort top-to-bottom so the bot clears objects logically
            targets.sort(key=lambda pos: pos[1])
            best_target = targets[0]
            
            # If we don't have a target, or the current one moved significantly
            if self.current_target is None or abs(best_target[0] - self.current_target[0]) > 30 or abs(best_target[1] - self.current_target[1]) > 30:
                self.current_target = best_target
                self.target_start_time = time.time()
                
                print(f"\n🎯 Target Lock Sighted! Moving cursor to block center: {self.current_target}")
                
                # PHYSICAL MOUSE ACTIONS: Move mouse directly to object coordinates and press down
                pydirectinput.moveTo(self.current_target[0], self.current_target[1])
                pydirectinput.mouseDown()
                
            # If we are holding down the click but the block isn't breaking (out of reach limit)
            elif time.time() - self.target_start_time > BLOCK_REACH_TIMEOUT:
                print(f"\n⚠️ Block at {self.current_target} is out of reach range limit.")
                pydirectinput.mouseUp() # Let go of the current block
                
                # Execute the safety reset macro to bounce back to the top of the pit
                self.trigger_teleport_reset()
                self.current_target = None 
                
            time.sleep(0.05) # Maintain frame-rate synchronization with engine

if __name__ == "__main__":
    bot = CompleteMiningBot()
    try:
        bot.run_bot()
    except KeyboardInterrupt:
        pydirectinput.mouseUp()
        print("\n🛑 Automated processes safely disconnected.")
