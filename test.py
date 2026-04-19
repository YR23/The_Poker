import json
import random
from pathlib import Path

RANKS = "AKQJT98765432"
CONFIG_DIR = Path("configs/positions")


def build_all_hands() -> list[str]:
    hands = []
    for i, r1 in enumerate(RANKS):
        for j, r2 in enumerate(RANKS):
            if i == j:
                h = r1 + r2
            elif i < j:
                h = r1 + r2 + "s"
            else:
                h = r2 + r1 + "o"
            if h not in hands:
                hands.append(h)
    return hands


def load_position_actions() -> dict[str, dict[str, str]]:
    actions_by_position = {}
    for config_path in sorted(CONFIG_DIR.glob("*.json")):
        with config_path.open("r", encoding="ascii") as f:
            data = json.load(f)
        position = data["position"]
        actions_by_position[position] = data["hand_actions"]
    return actions_by_position


def main() -> None:
    rng = random.SystemRandom()

    actions_by_position = load_position_actions()
    if len(actions_by_position) < 5:
        raise ValueError("Need at least 5 position config files in configs/positions.")

    all_hands = build_all_hands()
    sample_hands = rng.sample(all_hands, 5)
    sample_positions = rng.sample(list(actions_by_position.keys()), 5)

    print("Random sample of 5 hands and 5 positions:")
    for idx, (hand, position) in enumerate(zip(sample_hands, sample_positions), start=1):
        action = actions_by_position[position].get(hand, "fold")
        print(f"{idx}. Position={position}, Hand={hand} -> Action={action.upper()}")


if __name__ == "__main__":
    main()
