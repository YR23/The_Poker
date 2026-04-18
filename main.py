"""
main.py - Poker card detector for a fixed temp screenshot.

Usage:
    python main.py          # detect once
    python main.py --debug  # also save debug crop images to ./debug/
"""

import argparse
import cv2
import subprocess

from detector.card_reader import read_hole_cards, save_debug_crops


TEMP_SCREENSHOT = "/tmp/temp.png"


def detect_once(debug: bool = False) -> None:
    print(f"Capturing screenshot: {TEMP_SCREENSHOT}")
    try:
        subprocess.run(["screencapture", "-x", TEMP_SCREENSHOT], check=True)
    except (OSError, subprocess.CalledProcessError):
        print(f"Error: Could not capture screenshot to {TEMP_SCREENSHOT}!")
        return

    print(f"Reading screenshot: {TEMP_SCREENSHOT}")
    img = cv2.imread(TEMP_SCREENSHOT)
    
    if img is None:
        print(f"Error: Could not load {TEMP_SCREENSHOT}!")
        return

    if debug:
        save_debug_crops(img)

    card1, card2 = read_hole_cards(img)
    print(f"\nPyrex's hole cards: [{card1}] [{card2}]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Poker card detector - live screenshot to /tmp/temp.png")
    parser.add_argument("--debug", action="store_true", help="Save debug crop images to ./debug/")
    args = parser.parse_args()

    detect_once(debug=args.debug)


if __name__ == "__main__":
    main()
