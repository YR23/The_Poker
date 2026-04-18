"""
card_reader.py - Detect Pyrex's hole cards from the fixed /tmp/temp.png screenshot.

Layout assumptions:
    - Input is the same full-screen desktop screenshot layout as /tmp/temp.png.
    - CoinPoker sits on the right side of the desktop.
    - Pyrex's hole cards stay in a fixed on-screen position.
"""

import cv2
import numpy as np
import pytesseract
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Region-of-interest constants  (all values are fractions of window w/h)
# ---------------------------------------------------------------------------

# Bounding box that contains BOTH hole cards in the full desktop screenshot.
CARD_ROI = {
    "x_start": 0.706,
    "x_end":   0.776,
    "y_start": 0.681,
    "y_end":   0.847,
}

FIXED_SCREEN_SIZE = (3440, 1440)
FIXED_CARD_ROI_ABS = {"x0": 2430, "x1": 2670, "y0": 980, "y1": 1220}
FIXED_CARD_SPLIT = {"left_end": 115, "right_start": 124}

# Within the CARD_ROI sub-image, left and right card extents (fractions)
LEFT_CARD = {"x_start": 0.0, "x_end": 0.48}
RIGHT_CARD = {"x_start": 0.52, "x_end": 1.00}

# Within each card, the rank text sits in the top-left corner
RANK_ROI = {"x_start": 0.05, "x_end": 0.44, "y_start": 0.02, "y_end": 0.36}

# Within each card, use the large visible center area for general suit work.
SUIT_ROI = {"x_start": 0.08, "x_end": 0.90, "y_start": 0.08, "y_end": 0.80}

# New theme: suit is color-coded near the top-left rank/symbol area.
SUIT_COLOR_ROI = {"x_start": 0.00, "x_end": 0.40, "y_start": 0.00, "y_end": 0.50}

RANKS = {"10": "T", "1O": "T", "l0": "T"}  # OCR quirks for ten

SUIT_NAMES = {"h": "Hearts", "d": "Diamonds", "s": "Spades", "c": "Clubs"}


def _rank_from_text(text: str) -> str:
    """Normalize OCR text and return a valid single-char rank or '?' if unknown."""
    text = text.strip().upper().replace("O", "0").replace("l", "1").replace("I", "1")
    text = RANKS.get(text, text)

    valid = {"2","3","4","5","6","7","8","9","T","J","Q","K","A","10"}

    for token in [text[:2], text[:1]]:
        if token in valid:
            return "T" if token == "10" else token

    # Common artifact: rank + extra leading '1' from neighboring glyph (e.g. '17').
    if len(text) >= 2 and text[0] == "1" and text[1] in {"2","3","4","5","6","7","8","9","T","J","Q","K","A"}:
        return text[1]

    return "?"


def _draw_template_suit(symbol: str, size: int = 220) -> np.ndarray:
    """Render a simple binary template for suit-shape matching."""
    img = np.zeros((size, size), dtype=np.uint8)
    cx, cy = size // 2, size // 2

    if symbol == "d":
        pts = np.array([
            [cx, int(size * 0.16)],
            [int(size * 0.80), cy],
            [cx, int(size * 0.84)],
            [int(size * 0.20), cy],
        ], dtype=np.int32)
        cv2.fillConvexPoly(img, pts, 255)
    elif symbol == "h":
        cv2.circle(img, (int(size * 0.38), int(size * 0.34)), int(size * 0.18), 255, -1)
        cv2.circle(img, (int(size * 0.62), int(size * 0.34)), int(size * 0.18), 255, -1)
        pts = np.array([
            [int(size * 0.18), int(size * 0.42)],
            [int(size * 0.82), int(size * 0.42)],
            [cx, int(size * 0.86)],
        ], dtype=np.int32)
        cv2.fillConvexPoly(img, pts, 255)
    elif symbol == "s":
        cv2.circle(img, (int(size * 0.40), int(size * 0.45)), int(size * 0.16), 255, -1)
        cv2.circle(img, (int(size * 0.60), int(size * 0.45)), int(size * 0.16), 255, -1)
        pts = np.array([
            [cx, int(size * 0.14)],
            [int(size * 0.16), int(size * 0.56)],
            [int(size * 0.84), int(size * 0.56)],
        ], dtype=np.int32)
        cv2.fillConvexPoly(img, pts, 255)
        stem = np.array([
            [int(size * 0.47), int(size * 0.56)],
            [int(size * 0.53), int(size * 0.56)],
            [int(size * 0.57), int(size * 0.80)],
            [int(size * 0.43), int(size * 0.80)],
        ], dtype=np.int32)
        cv2.fillConvexPoly(img, stem, 255)
    else:  # "c"
        cv2.circle(img, (int(size * 0.36), int(size * 0.42)), int(size * 0.16), 255, -1)
        cv2.circle(img, (int(size * 0.64), int(size * 0.42)), int(size * 0.16), 255, -1)
        cv2.circle(img, (cx, int(size * 0.26)), int(size * 0.16), 255, -1)
        stem = np.array([
            [int(size * 0.47), int(size * 0.50)],
            [int(size * 0.53), int(size * 0.50)],
            [int(size * 0.56), int(size * 0.72)],
            [int(size * 0.44), int(size * 0.72)],
        ], dtype=np.int32)
        cv2.fillConvexPoly(img, stem, 255)

    return img


def _template_contour(symbol: str):
    img = _draw_template_suit(symbol)
    contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return max(contours, key=cv2.contourArea)


SUIT_TEMPLATE_CONTOURS = {
    "d": _template_contour("d"),
    "h": _template_contour("h"),
    "s": _template_contour("s"),
    "c": _template_contour("c"),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _crop_rel(img: np.ndarray, x0f: float, x1f: float, y0f: float, y1f: float) -> np.ndarray:
    h, w = img.shape[:2]
    x0, x1 = int(w * x0f), int(w * x1f)
    y0, y1 = int(h * y0f), int(h * y1f)
    return img[y0:y1, x0:x1]


def _crop_abs(img: np.ndarray, x0: int, x1: int, y0: int, y1: int) -> np.ndarray:
    return img[y0:y1, x0:x1]


def _auto_card_roi_bounds(window_img: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """Return absolute bounds for hole cards if two white card-like blobs are found."""
    h, w = window_img.shape[:2]
    lower_y0 = int(h * 0.60)
    lower = window_img[lower_y0:, :]
    if lower.size == 0:
        return None

    hsv = cv2.cvtColor(lower, cv2.COLOR_BGR2HSV)
    white_mask = cv2.inRange(hsv, np.array([0, 0, 150]), np.array([180, 80, 255]))

    kernel = np.ones((5, 5), np.uint8)
    white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_OPEN, kernel)
    white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[int, int, int, int, int, float]] = []

    card_min_area = max(800, int(w * h * 0.001))
    card_min_w = max(20, int(w * 0.015))
    card_min_h = max(30, int(h * 0.04))
    card_max_w = max(150, int(w * 0.15))
    card_max_h = max(300, int(h * 0.40))

    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        area = cw * ch
        if area < card_min_area or cw < card_min_w or ch < card_min_h:
            continue
        if cw > card_max_w or ch > card_max_h:
            continue

        portrait_ratio = ch / max(cw, 1)
        if portrait_ratio < 0.8 or portrait_ratio > 3.0:
            continue

        abs_x = x
        abs_y = y + lower_y0
        if abs_y < int(h * 0.62):
            continue

        cx = abs_x + cw / 2
        if cx < (w * 0.30) or cx > (w * 0.70):
            continue

        score = abs(cx - (w / 2))
        candidates.append((abs_x, abs_y, cw, ch, area, score))

    if not candidates:
        return None

    candidates.sort(key=lambda t: (t[5], -t[4]))

    # Pick up to two candidates near center with similar top edge.
    picked = [candidates[0]]
    for cand in candidates[1:]:
        if abs(cand[1] - picked[0][1]) < int(h * 0.10):
            picked.append(cand)
            break
    if len(picked) < 2:
        return None

    x0 = min(t[0] for t in picked)
    y0 = min(t[1] for t in picked)
    x1 = max(t[0] + t[2] for t in picked)
    y1 = max(t[1] + t[3] for t in picked)

    center_x = (x0 + x1) / 2
    if center_x < (w * 0.35) or center_x > (w * 0.65):
        return None

    pad_x = max(2, int(w * 0.01))
    pad_y = max(1, int(h * 0.01))
    x0 = max(0, x0 - pad_x)
    y0 = max(0, y0 - pad_y)
    x1 = min(w, x1 + pad_x)
    y1 = min(h, y1 + pad_y)

    roi_w = x1 - x0
    roi_h = y1 - y0
    if roi_w < int(w * 0.06) or roi_w > int(w * 0.35):
        return None
    if roi_h < int(h * 0.08) or roi_h > int(h * 0.40):
        return None

    return x0, x1, y0, y1


def extract_card_roi(window_img: np.ndarray) -> np.ndarray:
    """Crop the fixed region containing both hole cards from the full screenshot."""
    h, w = window_img.shape[:2]
    if (w, h) == FIXED_SCREEN_SIZE:
        return _crop_abs(
            window_img,
            FIXED_CARD_ROI_ABS["x0"], FIXED_CARD_ROI_ABS["x1"],
            FIXED_CARD_ROI_ABS["y0"], FIXED_CARD_ROI_ABS["y1"],
        )

    return _crop_rel(
        window_img,
        CARD_ROI["x_start"], CARD_ROI["x_end"],
        CARD_ROI["y_start"], CARD_ROI["y_end"],
    )


def _split_cards(roi: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    h, w = roi.shape[:2]
    if (w, h) == (240, 240):
        left = roi[:, :FIXED_CARD_SPLIT["left_end"]]
        right = roi[:, FIXED_CARD_SPLIT["right_start"]:]
        return left, right

    left  = roi[:, :int(w * LEFT_CARD["x_end"])]
    right = roi[:, int(w * RIGHT_CARD["x_start"]):]
    return left, right


# ---------------------------------------------------------------------------
# Rank detection via OCR
# ---------------------------------------------------------------------------

def _detect_rank(card_img: np.ndarray) -> str:
    h, w = card_img.shape[:2]
    
    # Try tighter corner crops first. On the current temp screenshot the rank
    # glyph is reliable there, while the mid-card crops can include extra pips.
    rank_regions = [
        (0.00, 0.40, 0.00, 0.32, "red_corner"),
        (0.00, 0.45, 0.00, 0.35, "corner"),
        (0.00, 0.34, 0.00, 0.30, "tight_corner"),
        (0.15, 0.50, 0.05, 0.40, "mid"),
        (0.10, 0.55, 0.00, 0.45, "expanded"),
    ]
    
    for y_start, y_end, x_start, x_end, region_name in rank_regions:
        base_rank_crop = card_img[int(h*y_start):int(h*y_end), int(w*x_start):int(w*x_end)]
        rank_crop = base_rank_crop
        if rank_crop.size == 0:
            continue
            
        rank_crop = cv2.resize(rank_crop, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(rank_crop, cv2.COLOR_BGR2GRAY)

        thresh_variants = [
            cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
            cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1],
        ]

        hsv = cv2.cvtColor(rank_crop, cv2.COLOR_BGR2HSV)
        red_mask1 = cv2.inRange(hsv, np.array([0, 70, 50]), np.array([10, 255, 255]))
        red_mask2 = cv2.inRange(hsv, np.array([160, 70, 50]), np.array([180, 255, 255]))
        red_pct = cv2.countNonZero(red_mask1 | red_mask2) / (rank_crop.shape[0] * rank_crop.shape[1])
        if region_name == "red_corner" and red_pct > 0.15:
            red_rank_crop = cv2.resize(base_rank_crop, None, fx=8, fy=8, interpolation=cv2.INTER_CUBIC)
            red_hsv = cv2.cvtColor(red_rank_crop, cv2.COLOR_BGR2HSV)
            sat = red_hsv[:, :, 1]
            for thresh_var in [
                cv2.threshold(sat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
                cv2.threshold(sat, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1],
            ]:
                for psm in [6, 7, 8, 10, 13]:
                    text = pytesseract.image_to_string(
                        thresh_var,
                        config=f"--oem 3 --psm {psm} -c tessedit_char_whitelist=23456789TJQKA",
                    ).strip().upper()
                    rank = _rank_from_text(text)
                    if rank != "?":
                        return rank
            continue

        if red_pct > 0.15:
            sat = hsv[:, :, 1]
            thresh_variants.insert(0, cv2.threshold(sat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1])
            thresh_variants.insert(1, cv2.threshold(sat, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1])

        for thresh_var in thresh_variants:
            for psm in [6, 7, 8, 10, 13]:
                text = pytesseract.image_to_string(
                    thresh_var,
                    config=f"--oem 3 --psm {psm} -c tessedit_char_whitelist=23456789TJQKA",
                ).strip().upper()
                rank = _rank_from_text(text)
                if rank != "?":
                    return rank
    
    return "?"


# ---------------------------------------------------------------------------
# Suit detection via colour + contour
# ---------------------------------------------------------------------------

def _detect_suit(card_img: np.ndarray) -> str:
    """Detect suit from theme color in the top-left rank/symbol area.

    Mapping for this theme:
      - green -> clubs (c)
      - blue  -> diamonds (d)
      - red   -> hearts (h)
      - black/dark -> spades (s)
    """
    suit_crop = _crop_rel(
        card_img,
        SUIT_COLOR_ROI["x_start"], SUIT_COLOR_ROI["x_end"],
        SUIT_COLOR_ROI["y_start"], SUIT_COLOR_ROI["y_end"],
    )
    if suit_crop.size == 0:
        return "s"

    hsv = cv2.cvtColor(suit_crop, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]

    # Ignore near-white background.
    color_mask = (s > 55) & (v > 45)
    dark_mask = (v < 75) & (s < 70)

    total = suit_crop.shape[0] * suit_crop.shape[1]
    color_pixels = int(np.count_nonzero(color_mask))
    dark_pixels = int(np.count_nonzero(dark_mask))

    if color_pixels < max(12, total // 80) and dark_pixels > total // 25:
        return "s"

    if color_pixels == 0:
        return "s"

    red_count = int(np.count_nonzero((((h <= 10) | (h >= 165)) & color_mask)))
    green_count = int(np.count_nonzero(((h >= 35) & (h <= 95) & color_mask)))
    blue_count = int(np.count_nonzero(((h >= 95) & (h <= 140) & color_mask)))

    best = max(
        [("h", red_count), ("c", green_count), ("d", blue_count)],
        key=lambda t: t[1],
    )

    if best[1] == 0:
        return "s"
    return best[0]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_hole_cards(window_img: np.ndarray) -> tuple[str, str]:
    """
    Detect Pyrex's two hole cards from a full window screenshot.

    Returns a tuple of two card strings, e.g. ("8s", "5d").
    """
    roi = extract_card_roi(window_img)
    left_card, right_card = _split_cards(roi)

    left_rank  = _detect_rank(left_card)
    left_suit  = _detect_suit(left_card)
    right_rank = _detect_rank(right_card)
    right_suit = _detect_suit(right_card)

    return f"{left_rank}{left_suit}", f"{right_rank}{right_suit}"


def save_debug_crops(window_img: np.ndarray, output_dir: str = "debug") -> None:
    """Save intermediate crops to disk so you can calibrate the ROI constants."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    cv2.imwrite(f"{output_dir}/00_window_full.png", window_img)

    # Draw the current CARD_ROI on top of the full window for quick calibration.
    h, w = window_img.shape[:2]
    x0 = int(w * CARD_ROI["x_start"])
    x1 = int(w * CARD_ROI["x_end"])
    y0 = int(h * CARD_ROI["y_start"])
    y1 = int(h * CARD_ROI["y_end"])
    overlay = window_img.copy()
    cv2.rectangle(overlay, (x0, y0), (x1, y1), (0, 255, 0), 2)
    cv2.imwrite(f"{output_dir}/00_window_with_roi.png", overlay)

    roi = extract_card_roi(window_img)
    cv2.imwrite(f"{output_dir}/00_card_roi.png", roi)

    left, right = _split_cards(roi)
    cv2.imwrite(f"{output_dir}/01_left_card.png", left)
    cv2.imwrite(f"{output_dir}/02_right_card.png", right)

    for name, card in [("left", left), ("right", right)]:
        rank_crop = _crop_rel(card, RANK_ROI["x_start"], RANK_ROI["x_end"],
                              RANK_ROI["y_start"], RANK_ROI["y_end"])
        suit_crop = _crop_rel(card, SUIT_ROI["x_start"], SUIT_ROI["x_end"],
                              SUIT_ROI["y_start"], SUIT_ROI["y_end"])
        cv2.imwrite(f"{output_dir}/03_{name}_rank.png", rank_crop)
        cv2.imwrite(f"{output_dir}/04_{name}_suit.png", suit_crop)

    print(f"Debug crops saved to '{output_dir}/'")
