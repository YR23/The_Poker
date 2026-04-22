from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import platform
import re
import subprocess
from pathlib import Path

import cv2
from PIL import Image, ImageEnhance, ImageOps
import pytesseract


def capture_screen(output_path: Path, display_index: int | None = None) -> Path:
    """Capture a macOS screen and write the image to output_path.

    If display_index is provided, captures that specific display via screencapture -D.
    """
    if platform.system() != "Darwin":
        raise RuntimeError("This script uses macOS screencapture and must run on macOS.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = ["screencapture", "-x"]
    if display_index is not None:
        command.extend(["-D", str(display_index)])
    command.append(str(output_path))

    subprocess.run(command, check=True)
    return output_path


def crop_middle_right_to_output(
    input_path: Path,
    output_path: Path,
    width_ratio: float = 0.5,
) -> Path:
    """Read input_path, crop right-side region with 100px top/bottom trim, and save output.

    Example: width_ratio=0.5 means width 1000 -> x range 500..1000.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    height_margin = 85

    with Image.open(input_path) as img:
        width, height = img.size

        left = max(0, min(width - 1, int(width * width_ratio)))
        top = min(height_margin, max(0, height - 1))
        right = width
        bottom = max(top + 1, height - height_margin)

        cropped = img.crop((left, top, right, bottom))
        cropped.save(output_path)

    return output_path


def split_image_grid(input_path: Path, output_dir: Path, rows: int = 2, cols: int = 3) -> list[Path]:
    """Split image into a rows×cols grid and save each cell with position label.

    Saves each base section at: output_dir/{position}/{position}.png
    Returns list of saved image paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(input_path) as img:
        width, height = img.size
        cell_width = width // cols
        cell_height = height // rows

        position_names = [
            ["top_left", "top_middle", "top_right"],
            ["bottom_left", "bottom_middle", "bottom_right"],
        ]

        saved_paths = []
        for row in range(rows):
            for col in range(cols):
                left = col * cell_width
                top = row * cell_height
                right = left + cell_width
                bottom = top + cell_height

                cropped = img.crop((left, top, right, bottom))
                name = position_names[row][col]
                position_dir = output_dir / name
                position_dir.mkdir(parents=True, exist_ok=True)
                output_path = position_dir / f"{name}.png"
                cropped.save(output_path)
                saved_paths.append(output_path)

        return saved_paths


def apply_section_crops(
    output_dir: Path,
    crop_specs: dict[str, tuple[int, int, int, int]],
) -> None:
    """Apply per-section crops to grid images in output_dir.

    crop_specs format: {"position_name": (top_px, bottom_px, left_px, right_px), ...}
    """
    for position, (top_px, bottom_px, left_px, right_px) in crop_specs.items():
        image_path = output_dir / position / f"{position}.png"
        if not image_path.exists():
            continue

        with Image.open(image_path) as img:
            width, height = img.size

            left = left_px
            top = top_px
            right = width - right_px
            bottom = height - bottom_px

            cropped = img.crop((left, top, right, bottom))
            cropped.save(image_path)


def extract_player_sections(dcim_base_dir: Path) -> None:
    """Complete pipeline: crop right, split into 6 player sections, apply fine-tuning crops.

    Files created:
    - dcim_base_dir/main_right.png: cropped right-side image
    - dcim_base_dir/players/{position}/{position}.png: 6 player sections with crops applied
    """
    dcim_dir = Path(dcim_base_dir)
    full_screenshot = dcim_dir / "screen.png"
    right_crop = dcim_dir / "main_right.png"

    # Step 2: Read screenshot, crop middle-right, and save.
    saved_crop = crop_middle_right_to_output(full_screenshot, right_crop)
    print(f"Step 2 complete: {saved_crop}")

    # Step 3: Split cropped image into 6 sections (2x3 grid for 6 poker positions).
    players_dir = dcim_dir / "players"
    split_paths = split_image_grid(right_crop, players_dir, rows=2, cols=3)
    print(f"Step 3 complete: Split into {len(split_paths)} sections")
    TOP_CROP = 150
    for p in split_paths:
        print(f"  - {p.parent.name}/{p.name}")

    # Step 4: Apply per-section crops for fine-tuning.
    crop_specs = {
        "bottom_left": (0, 0, 0, 0),       # no change
        "bottom_middle": (0, 0, 0, 115),    # crop 115px from right
        "bottom_right": (0, 0, 0, 0),      # no change
        "top_left": (TOP_CROP, 0, 0, 0),         # crop 150px from top
        "top_middle": (0, 175, 0, 0),       # crop 150px from bottom
        "top_right": (TOP_CROP, 0, 0, 0),        # crop 150px from top
    }
    apply_section_crops(players_dir, crop_specs)
    print(f"Step 4 complete: Applied per-section crops")


def extract_text_from_image(image_path: Path) -> str:
    """Extract text from image using OCR."""
    try:
        text = pytesseract.image_to_string(Image.open(image_path))
        return text.strip()
    except Exception as e:
        print(f"OCR error for {image_path}: {e}")
        return ""


def extract_pot_size_text_from_image(image_path: Path) -> str:
    """Extract pot size text with OCR settings tuned for numeric values."""
    try:
        with Image.open(image_path) as image:
            gray = ImageOps.grayscale(image)
            candidates: list[str] = []

            # 1) Raw grayscale pass.
            raw_text = pytesseract.image_to_string(
                gray,
                config="--psm 7 -c tessedit_char_whitelist=0123456789.",
            ).strip()
            if raw_text:
                candidates.append(raw_text)

            # 2) Multi-threshold passes to preserve faint decimal points.
            for contrast in (2.0, 2.5, 3.0):
                hi = ImageEnhance.Contrast(gray).enhance(contrast)
                for threshold in (120, 130, 140, 150):
                    bw = hi.point(lambda x: 255 if x > threshold else 0)
                    text = pytesseract.image_to_string(
                        bw,
                        config="--psm 7 -c tessedit_char_whitelist=0123456789.",
                    ).strip()
                    if text:
                        candidates.append(text)

            # Normalize candidates to numeric-like strings.
            normalized: list[str] = []
            for text in candidates:
                cleaned = re.sub(r"[^0-9.]", "", text)
                cleaned = re.sub(r"\.{2,}", ".", cleaned)
                cleaned = cleaned.strip(".")
                if cleaned:
                    normalized.append(cleaned)

            # Prefer formats in this order: x.xx, x.x, x
            for value in normalized:
                if re.fullmatch(r"\d\.\d{2}", value):
                    return value

            for value in normalized:
                if re.fullmatch(r"\d\.\d", value):
                    return value

            for value in normalized:
                if re.fullmatch(r"\d+", value):
                    integer_value = int(value)

                    # If OCR dropped the decimal and integer is too large,
                    # inject a decimal after the first digit so the leading
                    # number remains < 10 (e.g., 54 -> 5.4, 131 -> 1.31).
                    if integer_value >= 21 and len(value) > 1:
                        return f"{value[0]}.{value[1:]}"

                    return value

            # Last fallback: first non-empty cleaned candidate.
            if normalized:
                return normalized[0]

            return ""
    except Exception as e:
        print(f"Pot OCR error for {image_path}: {e}")
        return ""


def is_player_folded(name_image_path: Path, brightness_threshold: int = 150) -> bool:
    """Return True if the player's name text is dim (grey), indicating they have folded.

    Active players have bright white text; folded players have visibly darker/grey text.
    We measure the 95th-percentile pixel brightness of the name image — if even the
    brightest pixels are below the threshold, the text is dim and the player is folded.
    """
    try:
        with Image.open(name_image_path) as img:
            gray = ImageOps.grayscale(img)
            pixels = sorted(gray.getdata())
            # 95th percentile — the brightest part of the text
            p95_index = int(len(pixels) * 0.95)
            p95_brightness = pixels[p95_index]
            return p95_brightness < brightness_threshold
    except Exception:
        return False


def is_dealer_present(
    player_image_path: Path,
    dealer_button_path: Path,
    threshold: float = 0.75,
) -> bool:
    """Detect dealer button using template matching on a player's main image."""
    if not player_image_path.exists() or not dealer_button_path.exists():
        return False

    try:
        scene = cv2.imread(str(player_image_path), cv2.IMREAD_COLOR)
        template = cv2.imread(str(dealer_button_path), cv2.IMREAD_COLOR)

        if scene is None or template is None:
            return False

        sh, sw = scene.shape[:2]
        th, tw = template.shape[:2]
        if th > sh or tw > sw:
            return False

        result = cv2.matchTemplate(scene, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        print(f"[DEALER DEBUG] {player_image_path.name} vs {dealer_button_path.name} max_val={max_val:.4f} (threshold={threshold})")
        return max_val >= threshold
    except Exception as e:
        print(f"Dealer detection error for {player_image_path}: {e}")
        return False


def extract_action_text_from_image(image_path: Path) -> str:
    """Extract action text from an active player's action image.

    Since folded players are already filtered by brightness check,
    the action image should contain clear text (SB, BB, CALL, RAISE, BET, CHECK, ALL-IN).
    Valid actions: FOLD, CHECK, BET, SB, BB, CALL, RAISE, ALL-IN
    """
    from difflib import SequenceMatcher

    VALID_ACTIONS = ["FOLD", "CHECK", "BET", "SB", "BB", "CALL", "RAISE", "ALLIN"]

    def closest_action(text: str, threshold: float = 0.3) -> str:
        text = text.upper()
        best_match = None
        best_score = threshold
        for action in VALID_ACTIONS:
            score = SequenceMatcher(None, text, action).ratio()
            if score > best_score:
                best_score = score
                best_match = action
        return "ALL-IN" if best_match == "ALLIN" else (best_match or "")

    try:
        with Image.open(image_path) as image:
            if image.mode == "RGBA":
                image = image.convert("RGB")

            # Scale up if too small
            min_height = 80
            w, h = image.size
            if h < min_height:
                scale = min_height / h
                image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

            ocr_cfg = "--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ-"
            candidates: list[str] = []

            # Direct read on RGB and inverted (covers both light-on-dark and dark-on-light)
            for variant in (image, ImageOps.invert(image)):
                t = pytesseract.image_to_string(variant, config=ocr_cfg).strip()
                if t:
                    candidates.append(t)

            for text in candidates:
                cleaned = re.sub(r"[^A-Z]", "", text.upper())
                if cleaned:
                    if cleaned in VALID_ACTIONS:
                        action = "ALL-IN" if cleaned == "ALLIN" else cleaned
                        # SB/BB means waiting for their turn — treat as no action
                        if action in {"SB", "BB"}:
                            return ""
                        return action
                    match = closest_action(cleaned)
                    if match:
                        if match in {"SB", "BB"}:
                            return ""
                        return match

            return ""
    except Exception as e:
        print(f"Action OCR error for {image_path}: {e}")
        return ""



def extract_card_text_from_image(image_path: Path) -> str:
    """Extract a single playing card rank from an image.

    Valid values: A K Q J T 2 3 4 5 6 7 8 9 10
    Whitelist is digits + face card letters only.
    """
    VALID_RANKS = {"A", "K", "Q", "J", "10", "2", "3", "4", "5", "6", "7", "8", "9"}

    try:
        with Image.open(image_path) as image:
            if image.mode == "RGBA":
                image = image.convert("RGB")

            # Scale up if too small
            min_height = 60
            w, h = image.size
            if h < min_height:
                scale = min_height / h
                image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

            candidates: list[str] = []
            ocr_cfgs = [
                "--psm 8 -c tessedit_char_whitelist=AKQJTakqjt0123456789",
                "--psm 10 -c tessedit_char_whitelist=AKQJTakqjt0123456789",
            ]

            for variant in (image, ImageOps.invert(image), ImageOps.grayscale(image)):
                for cfg in ocr_cfgs:
                    t = pytesseract.image_to_string(variant, config=cfg).strip()
                    if t:
                        candidates.append(t)

            def normalize_rank(text: str) -> str:
                cleaned = re.sub(r"[^AKQJTakqjt0-9IOlo]", "", text).upper()

                # Strong "10" aliases from common OCR confusion.
                # T alone is also treated as 10 (OCR often reads 10 as T).
                if cleaned in {"10", "1O", "IO", "LO", "TO", "T0", "O", "0", "1", "T"}:
                    return "10"

                # If both 1-like and 0-like symbols are present, treat as 10.
                if any(ch in cleaned for ch in "1ILT") and any(ch in cleaned for ch in "0O"):
                    return "10"

                # Keep only expected rank symbols after alias handling.
                cleaned = re.sub(r"[^AKQJ0-9]", "", cleaned)
                return cleaned

            def has_crossbar(img: Image.Image) -> bool:
                """Return True if a horizontal dark run exists in the middle third of the image.

                'A' has a crossbar; 'J' does not. Works on RGB or grayscale images.
                """
                gray = ImageOps.grayscale(img)
                w, h = gray.size
                mid_top = h // 3
                mid_bot = (2 * h) // 3
                pixels = gray.load()
                for y in range(mid_top, mid_bot):
                    run = sum(1 for x in range(w) if pixels[x, y] < 100)
                    if run >= max(3, w // 4):
                        return True
                return False

            for text in candidates:
                normalized = normalize_rank(text)
                if normalized in VALID_RANKS:
                    # Disambiguate A vs J using crossbar detection
                    if normalized in {"A", "J"}:
                        if normalized == "A" and not has_crossbar(image):
                            normalized = "J"
                        elif normalized == "J" and has_crossbar(image):
                            normalized = "A"
                    return normalized

            # No OCR result — assume 10 (most visually complex rank, often missed)
            return "10"
    except Exception as e:
        print(f"Card OCR error for {image_path}: {e}")
        return ""


def build_preflop_hand_rank(
    left_rank: str,
    right_rank: str,
    left_color: str = "",
    right_color: str = "",
) -> str:
    """Build normalized 2-card notation.

    Examples:
    - Pair: AA (no suffix)
    - Same color: A2s
    - Different color: A2o
    """
    if not left_rank or not right_rank:
        return ""

    rank_alias = {"10": "T", "1O": "T", "IO": "T"}
    l = rank_alias.get(left_rank.upper(), left_rank.upper())
    r = rank_alias.get(right_rank.upper(), right_rank.upper())

    order = "AKQJT98765432"
    if l not in order or r not in order:
        return ""

    if l == r:
        return f"{l}{r}"

    hi_lo = f"{l}{r}" if order.index(l) < order.index(r) else f"{r}{l}"

    # Infer suited/offsuit from detected text colors.
    lc = left_color.lower().strip()
    rc = right_color.lower().strip()
    if lc and rc:
        return f"{hi_lo}s" if lc == rc else f"{hi_lo}o"

    return hi_lo


def detect_card_text_color(image_path: Path) -> str:
    """Detect dominant non-white text color in a card crop.

    Returns one of: red, green, blue, black, or "" when undetermined.
    """
    try:
        with Image.open(image_path) as image:
            if image.mode != "RGB":
                image = image.convert("RGB")

            pixels = list(image.getdata())

            # Ignore near-white paper/background.
            ink_pixels = [
                (r, g, b)
                for (r, g, b) in pixels
                if not (r > 235 and g > 235 and b > 235)
            ]
            if not ink_pixels:
                return ""

            red_count = 0
            green_count = 0
            blue_count = 0
            black_count = 0

            for r, g, b in ink_pixels:
                mx = max(r, g, b)

                # Dark ink (spade/club style symbols, outlines, text)
                if mx < 90:
                    black_count += 1
                    continue

                # Strong chromatic dominance for colored ink
                if r > g * 1.25 and r > b * 1.25 and r > 70:
                    red_count += 1
                elif g > r * 1.20 and g > b * 1.20 and g > 70:
                    green_count += 1
                elif b > r * 1.20 and b > g * 1.20 and b > 70:
                    blue_count += 1

            # If there is substantial color ink, classify by dominant color.
            color_counts = {
                "red": red_count,
                "green": green_count,
                "blue": blue_count,
            }
            dominant_color = max(color_counts, key=color_counts.get)
            dominant_count = color_counts[dominant_color]
            color_total = red_count + green_count + blue_count

            # Trust chromatic signal when enough colored pixels exist and are consistent.
            if color_total >= 120 and dominant_count / color_total >= 0.60:
                return dominant_color

            if dominant_count >= 40 and dominant_count > black_count * 0.35:
                return dominant_color

            # Otherwise default to black if dark ink dominates.
            if black_count >= 25:
                return "black"

            return dominant_color if dominant_count > 0 else ""
    except Exception as e:
        print(f"Card color detection error for {image_path}: {e}")
        return ""


def extract_player_info(player_section_path: Path) -> dict[str, str]:
    """Extract player name and pot size from a single player section image.

    Returns dict with keys: 'position', 'name', 'pot_size', 'raw_text'
    """
    position = player_section_path.stem
    raw_text = extract_text_from_image(player_section_path)

    # For now, return raw text; filtering for name and pot can be refined
    return {
        "position": position,
        "name": "",
        "pot_size": "",
        "raw_text": raw_text,
    }


def detect_player_data(players_dir: Path) -> list[dict]:
    """Extract player info (name, pot size) from all player sections.

    Returns list of dicts with extracted data per player position.
    """
    position_order = [
        "top_left", "top_middle", "top_right",
        "bottom_left", "bottom_middle", "bottom_right",
    ]

    results = []
    for position in position_order:
        player_image = players_dir / position / f"{position}.png"
        if player_image.exists():
            info = extract_player_info(player_image)
            results.append(info)
            print(f"{position}: {info['raw_text'][:100]}")

    return results


def organize_player_sections(players_dir: Path, positions: list[str] | None = None) -> None:
    """Create organized folder structure for each player position.

    Creates: players/{position}/{position}.png (main), action.png,
    name_and_pot_size.png, name.png, pot_size.png

    If positions is None, processes all 6 positions.
    
    Crop margins format: (left, top, right, bottom) - applied after 35%-70% height crop
    """
    if positions is None:
        positions = [
            "top_left", "top_middle", "top_right",
            "bottom_left", "bottom_middle", "bottom_right",
        ]

    # Position-specific crop margins: (left, top, right, bottom)
    crop_margins = {
        "bottom_left": (50, 4, 230, 110),
        "bottom_middle": (160, 35, 40, 74),  # left, top, right, bottom
        "bottom_right": (248, 225, 78, 26),
        "top_left": (110, 95, 210, 197.5),
        "top_middle": (165, 53, 160, 10),
        "top_right": (210, 120, 115, 144),
    }

    # Position-specific action margins from main image: (left, top, right, bottom)
    action_margins = {
        "bottom_left": (80, 190, 375, 410),
        "bottom_middle": (165, 425, 170, 172),
        "bottom_right": (250, 180, 200, 400), # left, top, right, bottom
        "top_left": (120, 157, 330, 295),
        "top_middle": (170, 200, 295, 220),
        "top_right": (210, 160, 220, 290),
    }

    # Position-specific height ranges for cropping: (height_top_percent, height_bottom_percent)
    height_ranges = {
        "bottom_left": (0.35, 0.70),
        "bottom_middle": (0.67, 1.0),         # Bottom 33% only
        "bottom_right": (0.00, 0.55),
        "top_left": (0.2, 1.0),
        "top_middle": (0.4, 0.75),            # Top 33% only
        "top_right": (0.15, 0.9),
    }

    # Position-specific middle exclusion zone around center: (top_px, bottom_px).
    # Example: (3, 5) means exclude [middle-3, middle+5],
    # take top part above it and bottom part below it.
    middle_exclusion_zone = {
        "bottom_left": (0, 0),
        "bottom_middle": (2, 1.5),
        "bottom_right": (2, 1),
        "top_left": (1, 2),
        "top_middle": (1, 2),
        "top_right": (2, 1),
    }

    for position in positions:
        source_image = players_dir / position / f"{position}.png"
        if not source_image.exists():
            print(f"Skipped {position}: image not found")
            continue

        # Create position subfolder
        position_dir = players_dir / position
        position_dir.mkdir(parents=True, exist_ok=True)

        # Copy main image to position folder
        with Image.open(source_image) as img:
            main_output = position_dir / f"{position}.png"
            if source_image != main_output:
                img.save(main_output)

            width, height = img.size

            # Extract action area directly from main position image.
            action_left_m, action_top_m, action_right_m, action_bottom_m = action_margins.get(
                position,
                (0, 0, 0, 0),
            )
            action_left = max(0, min(int(action_left_m), width - 1))
            action_top = max(0, min(int(action_top_m), height - 1))
            action_right = max(action_left + 1, min(width - int(action_right_m), width))
            action_bottom = max(action_top + 1, min(height - int(action_bottom_m), height))

            action_crop = img.crop((action_left, action_top, action_right, action_bottom))
            action_crop.save(position_dir / "action.png")

            # Get position-specific height range
            height_top_pct, height_bottom_pct = height_ranges.get(position, (0.35, 0.70))
            pot_top = int(height * height_top_pct)
            pot_bottom = int(height * height_bottom_pct)
            pot_crop = img.crop((0, pot_top, width, pot_bottom))

            # Apply position-specific margins
            left_m, top_m, right_m, bottom_m = crop_margins.get(position, (50, 4, 230, 110))
            
            pot_width, pot_height = pot_crop.size
            left = max(0, min(int(left_m), pot_width - 1))
            top = max(0, min(int(top_m), pot_height - 1))
            right = max(left + 1, min(pot_width - int(right_m), pot_width))
            bottom = max(top + 1, min(pot_height - int(bottom_m), pot_height))
            final_pot = pot_crop.crop((
                left,
                top,
                right,
                bottom,
            ))
            final_pot.save(position_dir / "name_and_pot_size.png")

            # Split by excluding a configurable middle zone, then keep top and bottom parts.
            nps_width, nps_height = final_pot.size
            mid_height = nps_height // 2

            exclude_top_px, exclude_bottom_px = middle_exclusion_zone.get(position, (0, 0))
            exclude_top_px = int(exclude_top_px)
            exclude_bottom_px = int(exclude_bottom_px)
            top_end = mid_height - exclude_top_px
            bottom_start = mid_height + exclude_bottom_px

            # Keep boundaries valid and ensure both crops have positive height.
            top_end = max(1, min(top_end, nps_height - 1))
            bottom_start = max(top_end + 1, min(bottom_start, nps_height - 1))

            # Top part: name (everything above exclusion zone)
            name_crop = final_pot.crop((0, 0, nps_width, top_end))
            name_crop.save(position_dir / "name.png")

            # Bottom part: pot_size (everything below exclusion zone)
            pot_crop_final = final_pot.crop((0, bottom_start, nps_width, nps_height))
            pot_crop_final.save(position_dir / "pot_size.png")

            # Hero card crops — only for bottom_middle (Pyrex's seat).
            # Same semantics as action_margins: (left, top, right, bottom).
            if position == "bottom_middle":
                hero_left_card_margins = (170, 300, 220, 273)
                hero_right_card_margins = (270, 295, 120, 280)

                ll, lt, lr, lb = hero_left_card_margins
                left_card_box = (
                    max(0, min(int(ll), width - 1)),
                    max(0, min(int(lt), height - 1)),
                    max(max(0, min(int(ll), width - 1)) + 1, min(width - int(lr), width)),
                    max(max(0, min(int(lt), height - 1)) + 1, min(height - int(lb), height)),
                )

                rl, rt, rr, rb = hero_right_card_margins
                right_card_box = (
                    max(0, min(int(rl), width - 1)),
                    max(0, min(int(rt), height - 1)),
                    max(max(0, min(int(rl), width - 1)) + 1, min(width - int(rr), width)),
                    max(max(0, min(int(rt), height - 1)) + 1, min(height - int(rb), height)),
                )

                img.crop(left_card_box).rotate(-8, expand=True).save(position_dir / "hero_card_left.png")
                img.crop(right_card_box).rotate(8, expand=True).save(position_dir / "hero_card_right.png")

            print(
                f"Organized {position}: main, name_and_pot_size ({nps_width}x{nps_height}px), "
                f"middle excluded [{top_end}:{bottom_start}], "
                f"name ({nps_width}x{top_end}px), pot_size ({nps_width}x{nps_height - bottom_start}px)"
            )


def extract_player_text(players_dir: Path, position: str) -> dict[str, str | bool]:
    """Extract text from name.png and pot_size.png for a specific player position.

    Returns dict with keys: 'position', 'name', 'pot_size', 'action', 'is_dealer'
    """
    position_dir = players_dir / position

    name_image = position_dir / "name.png"
    pot_size_image = position_dir / "pot_size.png"
    action_image = position_dir / "action.png"
    player_image = position_dir / f"{position}.png"
    dealer_button_image = players_dir.parent / "dealer.png"

    name_text = extract_text_from_image(name_image) if name_image.exists() else ""
    pot_size_text = (
        extract_pot_size_text_from_image(pot_size_image)
        if pot_size_image.exists()
        else ""
    )

    # Determine active/not-active from name brightness, then run action OCR only for active players.
    if name_image.exists() and is_player_folded(name_image):
        action_text = "FOLD"
    elif action_image.exists():
        action_text = extract_action_text_from_image(action_image)
    else:
        action_text = ""

    is_dealer = is_dealer_present(player_image, dealer_button_image)

    # Hero card OCR — only for bottom_middle (Pyrex's seat)
    hero_card_left = ""
    hero_card_right = ""
    hero_card_left_color = ""
    hero_card_right_color = ""
    hand_rank = ""
    if position == "bottom_middle":
        left_card_img = position_dir / "hero_card_left.png"
        right_card_img = position_dir / "hero_card_right.png"
        if left_card_img.exists():
            hero_card_left = extract_card_text_from_image(left_card_img)
            hero_card_left_color = detect_card_text_color(left_card_img)
        if right_card_img.exists():
            hero_card_right = extract_card_text_from_image(right_card_img)
            hero_card_right_color = detect_card_text_color(right_card_img)
        hand_rank = build_preflop_hand_rank(
            hero_card_left,
            hero_card_right,
            hero_card_left_color,
            hero_card_right_color,
        )

    result = {
        "position": position,
        "name": name_text,
        "pot_size": pot_size_text,
        "action": action_text,
        "is_dealer": is_dealer,
        "hero_card_left": hero_card_left,
        "hero_card_right": hero_card_right,
        "hero_card_left_color": hero_card_left_color,
        "hero_card_right_color": hero_card_right_color,
        "hand_rank": hand_rank,
    }

    print(f"{position}:")
    print(f"  Name: {name_text}")
    print(f"  Pot Size: {pot_size_text}")
    print(f"  Action: {action_text if action_text else 'No action yet'}")
    print(f"  Dealer: {'YES' if is_dealer else 'NO'}")
    if position == "bottom_middle":
        print(f"  Hero cards: {hero_card_left or '?'} | {hero_card_right or '?'}")
        print(f"  Hero colors: {hero_card_left_color or '?'} | {hero_card_right_color or '?'}")
        print(f"  Hand rank: {hand_rank or '?'}")

    return result


def process_positions_parallel(
    players_dir: Path,
    positions: list[str],
    max_workers: int = 6,
) -> dict[str, dict[str, str | bool]]:
    """Organize and extract each player position in parallel.

    This runs the per-position pipeline concurrently:
    1) organize crops for that position
    2) OCR extraction for that position
    """

    def process_one(position: str) -> tuple[str, dict[str, str | bool]]:
        organize_player_sections(players_dir, positions=[position])
        return position, extract_player_text(players_dir, position)

    results: dict[str, dict[str, str | bool]] = {}
    worker_count = max(1, min(max_workers, len(positions)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        for position, result in executor.map(process_one, positions):
            results[position] = result

    return results


def assign_table_positions(results: dict[str, dict[str, str | bool]]) -> str | None:
    """Assign BTN/SB/BB/UTG/MP/CO to results based on detected dealer seat.

    Returns an optional warning message when multiple dealer matches are found.
    """
    clockwise_order = [
        "top_middle",
        "top_right",
        "bottom_right",
        "bottom_middle",
        "bottom_left",
        "top_left",
    ]
    table_roles = ["BTN", "SB", "BB", "UTG", "MP", "CO"]

    for seat in clockwise_order:
        if seat in results:
            results[seat]["table_position"] = ""

    dealer_seats = [
        seat
        for seat in clockwise_order
        if results.get(seat, {}).get("is_dealer", False)
    ]

    if not dealer_seats:
        return None

    dealer_seat = dealer_seats[0]
    dealer_index = clockwise_order.index(dealer_seat)

    for offset, role in enumerate(table_roles):
        seat = clockwise_order[(dealer_index + offset) % len(clockwise_order)]
        if seat in results:
            results[seat]["table_position"] = role

    if len(dealer_seats) > 1:
        return "Multiple dealer matches found. Using the first clockwise match."

    return None


def button_crop_and_check_turn(main_right_path: Path, crop_margins=None, keywords=("YOUR TURN", "MY TURN"), acceptable_chars="XFold/") -> str:
    """
    Crop a region from main_right.png using the exact hero_left_card logic (no rotation), save as button.png,
    OCR the text, and return 'My turn' if a keyword is found.
    crop_margins: (left, top, right, bottom) margins in pixels to crop from each side. If None, use default.
    keywords: tuple of strings to match for 'my turn'.
    acceptable_chars: string of allowed characters to filter OCR output (default: 'XFOLD').
    """
    from PIL import Image
    import pytesseract
    import os
    import re

    # Default margins (same as hero_left_card_margins)
    if crop_margins is None:
        crop_margins = (1050, 1180, 480, 0)

    with Image.open(main_right_path) as img:
        width, height = img.size
        ll, lt, lr, lb = crop_margins
        left = max(0, min(int(ll), width - 1))
        top = max(0, min(int(lt), height - 1))
        right = max(left + 1, min(width - int(lr), width))
        bottom = max(top + 1, min(height - int(lb), height))
        crop_box = (left, top, right, bottom)
        cropped = img.crop(crop_box)
        # Save cropped image as button.png in the same directory as main_right_path
        button_path = os.path.join(os.path.dirname(main_right_path), "button.png")
        cropped.save(button_path)
        ocr_cfg = f"--psm 7 -c tessedit_char_whitelist={acceptable_chars}"
        text = pytesseract.image_to_string(cropped, config=ocr_cfg).upper()
        filtered = re.sub(f"[^{acceptable_chars}]", "", text)
        for kw in keywords:
            if "X/F" in text:
                return False
            if "FOLD" in text:
                return True
    return False