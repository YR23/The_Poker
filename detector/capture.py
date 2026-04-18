"""
capture.py - Locate and screenshot the CoinPoker window on macOS.
"""

import subprocess
import mss
import numpy as np


def get_window_bounds(app_name: str = "CoinPoker") -> dict:
    """
    Return the bounding box of the first window of `app_name` using AppleScript.
    Returns dict with keys: left, top, width, height (all in screen pixels).
    """
    script = f'''
    tell application "System Events"
        tell process "{app_name}"
            set winPos to position of window 1
            set winSize to size of window 1
            set x to item 1 of winPos
            set y to item 2 of winPos
            set w to item 1 of winSize
            set h to item 2 of winSize
            return (x as string) & "," & (y as string) & "," & (w as string) & "," & (h as string)
        end tell
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(
            f"Could not locate '{app_name}' window.\n"
            f"Make sure CoinPoker is open and visible.\n"
            f"AppleScript error: {result.stderr.strip()}"
        )
    parts = result.stdout.strip().split(",")
    x, y, w, h = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
    return {"left": x, "top": y, "width": w, "height": h}


def capture_window(app_name: str = "CoinPoker") -> tuple[np.ndarray, dict]:
    """
    Capture the CoinPoker window and return (image_bgr, bounds).
    image_bgr is a NumPy array in BGR format (OpenCV-compatible).
    """
    bounds = get_window_bounds(app_name)
    with mss.mss() as sct:
        monitor = {
            "left": bounds["left"],
            "top": bounds["top"],
            "width": bounds["width"],
            "height": bounds["height"],
        }
        raw = sct.grab(monitor)
        # mss gives BGRA; drop alpha and keep BGR
        img_bgra = np.array(raw)
        img_bgr = img_bgra[:, :, :3]
    return img_bgr, bounds
