import time
import json
from pathlib import Path
from reader_utils import extract_player_sections, process_positions_parallel

DCIM_DIR = Path(__file__).resolve().parent / "DCIM"
PLAYERS_DIR = DCIM_DIR / "players"
ALL_POSITIONS = [
    "top_left", "top_middle", "top_right",
    "bottom_left", "bottom_middle", "bottom_right",
]

STATE_PATH = Path(__file__).resolve().parent / "last_table_state.json"


def load_last_state():
    if STATE_PATH.exists():
        with open(STATE_PATH, "r") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

def get_current_state():
    extract_player_sections(DCIM_DIR)
    return process_positions_parallel(PLAYERS_DIR, ALL_POSITIONS, max_workers=6)


def main():
    last_state = load_last_state()
    print("[AutoTracker] Starting. Press Ctrl+C to stop.")
    while True:
        current_state = get_current_state()
        changed = False
        for pos, pdata in current_state.items():
            name = (pdata.get("name") or "").strip()
            action = (pdata.get("action") or "").strip()
            prev_action = (last_state.get(pos, {}).get("action") or "").strip()
            if name and action and action != prev_action:
                print(f"[AutoTracker] {name} at {pos} did: {action}")
                changed = True
        if changed:
            save_state(current_state)
        # TODO: Add logic to detect if it's hero's turn and pause
        time.sleep(2)

if __name__ == "__main__":
    main()
