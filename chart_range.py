"""Load villain ranges from chart/{stack}bb/{position}/*.json strategy files."""

from __future__ import annotations

import json
from pathlib import Path

from equity_mc import expand_range_token

CHART_BASE = Path(__file__).resolve().parent / "chart"

# Old default path (100bb); prefer chart_root("100bb") or list_positions(stack_bb=...).
CHART_ROOT = CHART_BASE / "100bb"

POSITION_ORDER = ("UTG", "MP", "LJ", "HJ", "CO", "BU", "SB", "BB")

DEFAULT_ACTION_ORDER = ("fold", "call", "raise 2.5bb", "raise 12.5bb", "all-in")

PREFERRED_VILLAIN_ACTIONS = ("raise 12.5bb", "raise 2.5bb", "all-in", "call")


def chart_root(stack_bb: str) -> Path:
    return CHART_BASE / stack_bb


def parse_weights_blob(blob: str) -> dict[str, float]:
    if not blob or not blob.strip():
        return {}
    out: dict[str, float] = {}
    for part in blob.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        hand, _, rest = part.partition(":")
        hand = hand.strip()
        try:
            out[hand] = float(rest)
        except ValueError:
            continue
    return out


def load_strategy(path: Path) -> dict[str, dict[str, float]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    strat: dict[str, dict[str, float]] = {}
    for action in DEFAULT_ACTION_ORDER:
        blob = raw.get(action, "")
        if isinstance(blob, str):
            strat[action] = parse_weights_blob(blob)
        elif isinstance(blob, dict):
            strat[action] = {k: float(v) for k, v in blob.items()}
        else:
            strat[action] = {}
    for key, val in raw.items():
        if key in strat:
            continue
        if isinstance(val, str):
            strat[key] = parse_weights_blob(val)
        elif isinstance(val, dict):
            strat[key] = {k: float(v) for k, v in val.items()}
    return strat


def list_positions(stack_bb: str = "100bb") -> list[str]:
    root = chart_root(stack_bb)
    if not root.is_dir():
        return []
    found = [p.name for p in root.iterdir() if p.is_dir()]

    def sort_key(name: str) -> tuple[int, str]:
        try:
            return (POSITION_ORDER.index(name), name)
        except ValueError:
            return (len(POSITION_ORDER), name)

    return sorted(found, key=sort_key)


def chart_path(position: str, spot: str, stack_bb: str = "100bb") -> Path:
    return chart_root(stack_bb) / position / f"{spot}.json"


def list_spots(position: str, stack_bb: str = "100bb") -> list[str]:
    d = chart_root(stack_bb) / position
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.json"))


def actions_with_mass(strat: dict[str, dict[str, float]], *, min_weight: float = 0.0) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for action in DEFAULT_ACTION_ORDER:
        if action in strat and any(w > min_weight for w in strat[action].values()):
            ordered.append(action)
            seen.add(action)
    for action in sorted(strat.keys()):
        if action in seen:
            continue
        if any(w > min_weight for w in strat[action].values()):
            ordered.append(action)
            seen.add(action)
    return ordered


PREFERRED_VILLAIN_ACTIONS_20BB = ("all-in", "raise 12.5bb", "raise 2.5bb", "call")


def suggest_villain_action(
    strat: dict[str, dict[str, float]], *, stack_bb: str | None = None
) -> str | None:
    acts = actions_with_mass(strat)
    if not acts:
        return None
    prefs = (
        PREFERRED_VILLAIN_ACTIONS_20BB
        if stack_bb == "20bb"
        else PREFERRED_VILLAIN_ACTIONS
    )
    for pref in prefs:
        if pref in acts:
            return pref
    return acts[0]


def hand_weights_for_actions(
    strat: dict[str, dict[str, float]], actions: list[str]
) -> dict[str, float]:
    out: dict[str, float] = {}
    for action in actions:
        for hand, w in strat.get(action, {}).items():
            if w > 0:
                out[hand] = out.get(hand, 0.0) + w
    return out


def villain_range_from_chart(
    position: str,
    spot: str,
    actions: list[str],
    *,
    min_weight: float = 0.0,
    stack_bb: str = "100bb",
) -> tuple[list[tuple[int, int]], list[float]]:
    """Expand chart action line(s) to combos with per-combo weights."""
    path = chart_path(position, spot, stack_bb=stack_bb)
    if not path.is_file():
        raise ValueError(f"Chart not found: {path}")
    strat = load_strategy(path)
    if not actions:
        raise ValueError("Select at least one chart action")
    unknown = [a for a in actions if a not in strat]
    if unknown:
        raise ValueError(f"Unknown action(s): {', '.join(unknown)}")

    hw = hand_weights_for_actions(strat, actions)
    combos: list[tuple[int, int]] = []
    weights: list[float] = []
    for hand, w in hw.items():
        if w <= min_weight:
            continue
        try:
            hand_combos = expand_range_token(hand)
        except ValueError as e:
            raise ValueError(f"Bad hand label {hand!r} in chart") from e
        for c in hand_combos:
            combos.append(tuple(sorted(c)))
            weights.append(w)

    if not combos:
        raise ValueError(
            f"No hands with weight > {min_weight} for action(s): {', '.join(actions)}"
        )
    return combos, weights


def list_chart_actions(position: str, spot: str, stack_bb: str = "100bb") -> list[str]:
    path = chart_path(position, spot, stack_bb=stack_bb)
    if not path.is_file():
        return []
    return actions_with_mass(load_strategy(path))
