"""
main.py - Poker card detector for a fixed temp screenshot.

Usage:
    python main.py                  # detect once
    python main.py -p BTN           # detect + GTO action for Button
    python main.py --debug          # also save debug crop images to ./debug/
"""

import argparse
import cv2
import subprocess

from detector.card_reader import read_hole_cards, save_debug_crops
from detector.ranges import get_action


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

    rank_order = "23456789TJQKA"
    r1, s1 = card1[0], card1[1]
    r2, s2 = card2[0], card2[1]

    # Sort so higher rank is first
    if rank_order.index(r1) < rank_order.index(r2):
        r1, r2 = r2, r1
        s1, s2 = s2, s1

    if r1 == r2:
        hand_str = f"{r1}{r2}"      # pocket pair — no suffix
    elif s1 == s2:
        hand_str = f"{r1}{r2}s"    # suited
    else:
        hand_str = f"{r1}{r2}o"    # offsuit

    print(f"\nHole cards : [{card1}] [{card2}]")
    print(f"Hand       : {hand_str}")

    action = get_action("SB", hand_str)
    print("Position   : SB")
    print(f"Action     : {action}")
    print(f"Do         : {action}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Poker card detector - live screenshot to /tmp/temp.png"
    )
    parser.add_argument("--debug", action="store_true", help="Save debug crop images to ./debug/")
    args = parser.parse_args()

    detect_once(debug=args.debug)


if __name__ == "__main__":
    main()
