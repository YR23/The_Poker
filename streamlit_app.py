import subprocess
from datetime import datetime
from pathlib import Path

import cv2
import streamlit as st

from detector.card_reader import read_hole_cards

TEMP_IMAGE_PATH = Path("/tmp/temp.png")


def capture_screen_to(path: Path) -> tuple[bool, str]:
    """Capture the full screen to the given path using macOS screencapture."""
    try:
        subprocess.run(["screencapture", "-x", str(path)], check=True)
        return True, ""
    except (OSError, subprocess.CalledProcessError) as exc:
        return False, str(exc)


def load_bgr_image(path: Path):
    img = cv2.imread(str(path))
    if img is None:
        return None
    return img


def main() -> None:
    st.set_page_config(page_title="Poker Card Detector", layout="centered")
    st.title("Poker Card Detector")
    st.write("Capture your screen and detect your two hole cards.")

    col1, col2 = st.columns([1, 1])
    with col1:
        capture_clicked = st.button("Capture And Detect", type="primary", use_container_width=True)
    with col2:
        keep_last = st.checkbox("Keep last screenshot", value=True)

    if capture_clicked:
        ok, err = capture_screen_to(TEMP_IMAGE_PATH)
        if not ok:
            st.error(f"Capture failed: {err}")
            return

        img_bgr = load_bgr_image(TEMP_IMAGE_PATH)
        if img_bgr is None:
            st.error(f"Could not read image: {TEMP_IMAGE_PATH}")
            return

        card1, card2 = read_hole_cards(img_bgr)
        st.success(f"Detected cards: {card1}  {card2}")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.caption(f"Captured at {timestamp} from {TEMP_IMAGE_PATH}")

        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        st.image(img_rgb, caption="Captured screen", use_container_width=True)

        if not keep_last and TEMP_IMAGE_PATH.exists():
            TEMP_IMAGE_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
