from __future__ import annotations

import platform
import re
import subprocess
from pathlib import Path

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


def extract_action_text_from_image(image_path: Path) -> str:
    """Extract action text allowing uppercase letters only."""
    try:
        with Image.open(image_path) as image:
            gray = ImageOps.grayscale(image)
            candidates: list[str] = []

            raw_text = pytesseract.image_to_string(
                gray,
                config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            ).strip()
            if raw_text:
                candidates.append(raw_text)

            for contrast in (2.0, 2.5, 3.0):
                hi = ImageEnhance.Contrast(gray).enhance(contrast)
                for threshold in (120, 130, 140, 150):
                    bw = hi.point(lambda x: 255 if x > threshold else 0)
                    text = pytesseract.image_to_string(
                        bw,
                        config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                    ).strip()
                    if text:
                        candidates.append(text)

            normalized: list[str] = []
            for text in candidates:
                cleaned = re.sub(r"[^A-Z]", "", text.upper())
                if cleaned:
                    normalized.append(cleaned)

            if normalized:
                return max(normalized, key=len)

            return ""
    except Exception as e:
        print(f"Action OCR error for {image_path}: {e}")
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
        "bottom_right": (0, 0, 0, 0), # left, top, right, bottom
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

            print(
                f"Organized {position}: main, name_and_pot_size ({nps_width}x{nps_height}px), "
                f"middle excluded [{top_end}:{bottom_start}], "
                f"name ({nps_width}x{top_end}px), pot_size ({nps_width}x{nps_height - bottom_start}px)"
            )


def extract_player_text(players_dir: Path, position: str) -> dict[str, str]:
    """Extract text from name.png and pot_size.png for a specific player position.

    Returns dict with keys: 'position', 'name', 'pot_size', 'action'
    """
    position_dir = players_dir / position

    name_image = position_dir / "name.png"
    pot_size_image = position_dir / "pot_size.png"
    action_image = position_dir / "action.png"

    name_text = extract_text_from_image(name_image) if name_image.exists() else ""
    pot_size_text = (
        extract_pot_size_text_from_image(pot_size_image)
        if pot_size_image.exists()
        else ""
    )
    action_text = (
        extract_action_text_from_image(action_image)
        if action_image.exists()
        else ""
    )

    result = {
        "position": position,
        "name": name_text,
        "pot_size": pot_size_text,
        "action": action_text,
    }

    print(f"{position}:")
    print(f"  Name: {name_text}")
    print(f"  Pot Size: {pot_size_text}")
    print(f"  Action: {action_text}")

    return result
