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
# Change this to match the exact name text on the top bar of your game window!
GAME_WINDOW_TITLE = "Game"  

# Saturated color profiles for the X-Ray overlays (Purples, Reds, Cyans)
COLOR_BOUNDS = [
    (np.array([0, 150, 50]), np.array([10, 255, 255])),    # Red variant 1
    (np.array([160, 150, 50]), np.array([180, 255, 255])), # Red variant 2
    (np.array([130, 100, 50]), np.array([160, 255, 255])), # Purple
    (np.array([80, 100, 50]), np.array([100, 255, 255]))   # Cyan / Turquoise
]

# Timers & Parameters
STUCK_TIMEOUT = 3.5  # Seconds of screen stillness before forcing a teleport reset
# ==============================================================================

class SelfHealingBot:
    def __init__(self):
        self.window_rect = None
        self.automine_x = None
        self.automine_y = None
        self.last_hash = None
        self.last_change_time = time.time()
        
    def locate_game_window(self):
        """Attempts to find the game window dynamically to handle resizing or moving."""
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)
            if windows:
                win = windows[0]
                # If window is minimized, try restoring it
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(0.5)
                
                # Fetch absolute bounding box adjustments
                self.window_rect = (win.left, win.top, win.width, win.height)
                print(f"✅ Found game window! Position: {self.window_rect}")
                return True
        except Exception as e:
            print(f"⚠️ Fallback: Could not use automated window detection ({e}).")
        
        # Human Fallback Mode: If automated detection fails, ask the user to position manually
        print("\n🔧 [Fallback] Manual Setup: Please position your game window.")
        print("Press ENTER in this console when your game is visible and ready...")
        input()
        # Default full-screen fallback assumptions if we can't capture window bounds
        self.window_rect = (0, 0, 1920, 1080)
        return True

    def calibrate_automine_icon(self):
        """Allows the user to dynamically map the Auto-Mine location before starting."""
        print("\n🎯 CALIBRATION STEP:")
        print("Move your real mouse cursor directly over the in-game 'Auto-Mine' icon.")
        for i in range(5, 0, -1):
            print(f"Capturing mouse position in {i} seconds...", end="\r")
            time.sleep(1)
        
        # Grab current cursor position dynamically
        mx, my = pydirectinput.position()
        self.automine_x, self.automine_y = mx, my
        print(f"\n✅ Successfully mapped Auto-Mine position to global coordinates: ({mx}, {my})")

    def capture_roi(self):
        """Safely captures the active region of interest, adapting to display anomalies."""
        try:
            x, y, w, h = self.window_rect
            # Safety checks to prevent negative or corrupted bounding boxes
            x, y = max(0, x), max(0, y)
            w, h = max(100, w), max(100, h)
            
            screenshot = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            return np.array(screenshot)
        except Exception as e:
            print(f"💥 Capture error encountered ({e}). Recalibrating display area...")
            time.sleep(1)
            self.locate_game_window() # Re-verify window location instead of crashing
            return None

    def trigger_teleport_reset(self):
        """Safely click off/on the mapped auto-mine icon to reset to the top."""
        if not self.automine_x or not self.automine_y:
            print("❌ Cannot teleport: Auto-Mine coordinates are missing. Recalibrating...")
            self.calibrate_automine_icon()
            return

        print("\n🔄 Screen freeze detected! Resetting to top via dynamic teleport...")
        try:
            pydirectinput.mouseUp()  # Safely release accidental stuck clicks
            time.sleep(0.1)
            
            # Navigate to the dynamically registered icon position
            pydirectinput.moveTo(self.automine_x, self.automine_y)
            pydirectinput.click()
            time.sleep(0.6)  # Give UI time to process state change
            
            pydirectinput.click()
            print("🚀 Teleport triggered successfully! Resuming tracking layers...")
            time.sleep(1.5)  # Buffer time for the game to complete the load transition
        except Exception as e:
            print(f"⚠️ Interaction anomaly during click cycle ({e}). Retrying in 1s...")
            time.sleep(1)

    def monitor_loop(self):
        print("\n🤖 Booting core system. Preparing loops...")
        self.locate_game_window()
        self.calibrate_automine_icon()
        
        print("\n🔥 System fully armed! Activate your auto-miner. Script running...")
        
        # Prime the screen state hashes
        frame = self.capture_roi()
        if frame is not None:
            self.last_hash = hashlib.md5(frame.tobytes()).hexdigest()
        self.last_change_time = time.time()

        while True:
            frame = self.capture_roi()
            if frame is None:
                continue  # Skip iteration if screen capture dropped out

            # Process a small, centralized region of the frame to check for block breaking changes
            h, w, _ = frame.shape
            center_zone = frame[int(h*0.3):int(h*0.7), int(w*0.3):int(w*0.7)]
            current_hash = hashlib.md5(center_zone.tobytes()).hexdigest()

            if current_hash == self.last_hash:
                stuck_duration = time.time() - self.last_change_time
                print(f"⏳ Verification layer static... Stuck time: {stuck_duration:.1f}s", end="\r")
                
                if stuck_duration >= STUCK_TIMEOUT:
                    self.trigger_teleport_reset()
                    # Flush the timers cleanly to clear out past cycles
                    self.last_change_time = time.time()
                    new_frame = self.capture_roi()
                    if new_frame is not None:
                        self.last_hash = hashlib.md5(new_frame[int(h*0.3):int(h*0.7), int(w*0.3):int(w*0.7)].tobytes()).hexdigest()
            else:
                # Changes detected! Game is currently active and breaking blocks -> Keep moving forward
                self.last_hash = current_hash
                self.last_change_time = time.time()

            time.sleep(0.2) # Sample frame rate safety throttle

if __name__ == "__main__":
    bot = SelfHealingBot()
    try:
        bot.monitor_loop()
    except KeyboardInterrupt:
        print("\n🛑 Execution paused safely by user. Goodbye!")
        sys.exit(0)
