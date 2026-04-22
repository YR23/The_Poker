from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from cold_call_section import COLD_CALL_CHARTS
from iso_raise_section import DEFAULT_ISO_RAISE_HANDS
from over_call_section import OVER_CALL_HANDS
from squeeze_section import SQUEEZE_RANGES
from three_bet_section import THREE_BET_BLUFFS, THREE_BET_DEFAULTS


POSITIONS = ["UTG", "MP", "CO", "BTN", "SB", "BB"]
REPO_ROOT = Path(__file__).resolve().parent
if not (REPO_ROOT / "plays" / "plays.json").exists():
    REPO_ROOT = Path("/Users/inbarrosenblum/Documents/Repos/The_Poker")
PLAYS_JSON_PATH = REPO_ROOT / "plays" / "plays.json"
RFI_CONFIGS_DIR = REPO_ROOT / "configs" / "positions"
SET_MINING_HANDS = {"22", "33", "44", "55", "66", "77", "88", "99"}
STEAL_POSITIONS = {"CO", "BTN", "SB"}
TRACKED_ACTIONS = {"Fold", "Call", "Raise", "Limp"}


@lru_cache(maxsize=1)
def load_plays() -> list[dict[str, Any]]:
    with PLAYS_JSON_PATH.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


@lru_cache(maxsize=1)
def load_rfi_actions() -> dict[str, dict[str, str]]:
    actions: dict[str, dict[str, str]] = {}
    for config_path in sorted(RFI_CONFIGS_DIR.glob("*.json")):
        with config_path.open("r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        actions[data["position"]] = data["hand_actions"]
    return actions


def evaluate_play(play_name: str, hand: str, position: str) -> tuple[Optional[bool], str]:
    rfi_actions = load_rfi_actions()

    if play_name == "Raising First In":
        if position not in rfi_actions:
            return None, f"No RFI chart configured for {position}."
        is_possible = rfi_actions[position].get(hand) == "raise"
        return is_possible, "In RFI raise range." if is_possible else "Not in RFI raise range."

    if play_name == "3-Bet":
        if position not in THREE_BET_DEFAULTS:
            return None, f"No 3-bet chart configured for {position}."
        is_possible = hand in THREE_BET_DEFAULTS[position] or hand in THREE_BET_BLUFFS
        return is_possible, "In 3-bet value/bluff range." if is_possible else "Not in 3-bet value/bluff range."

    if play_name == "4-Bet":
        if position not in THREE_BET_DEFAULTS:
            return None, f"No 4-bet chart configured for {position}."
        is_possible = hand in THREE_BET_DEFAULTS[position] or hand in THREE_BET_BLUFFS
        return is_possible, "In 4-bet value/bluff range." if is_possible else "Not in 4-bet value/bluff range."

    if play_name == "Cold Call":
        if position not in COLD_CALL_CHARTS:
            return None, f"No cold-call chart configured for {position}."
        cold_call = COLD_CALL_CHARTS[position]["cold_call"]
        is_possible = hand in cold_call
        return is_possible, "In cold-call range." if is_possible else "Not in cold-call range."

    if play_name == "Set Mining":
        is_possible = hand in SET_MINING_HANDS
        return is_possible, "Small pocket pair for set mining." if is_possible else "Not a set-mining pocket pair."

    if play_name == "Isolation Raise":
        is_possible = hand in DEFAULT_ISO_RAISE_HANDS
        return is_possible, "In iso-raise range." if is_possible else "Not in iso-raise range."

    if play_name == "Limp":
        return None, "Limp is sequence-based in this app (no hand chart configured)."

    if play_name == "Overcall":
        is_possible = hand in OVER_CALL_HANDS
        return is_possible, "In overcall range." if is_possible else "Not in overcall range."

    if play_name == "Squeeze":
        if position not in SQUEEZE_RANGES:
            return None, f"No squeeze chart configured for {position}."
        ranges = SQUEEZE_RANGES[position]
        is_possible = hand in ranges["default"] or hand in ranges["optional"]
        return is_possible, "In squeeze range (default/optional)." if is_possible else "Not in squeeze range."

    if play_name == "Steal":
        if position not in rfi_actions:
            return None, f"No RFI chart configured for {position}."
        if position not in STEAL_POSITIONS:
            return False, "Steal considered only from CO/BTN/SB."
        is_possible = rfi_actions[position].get(hand) == "raise"
        return is_possible, "In steal/open range from late position." if is_possible else "Not in late-position steal range."

    return None, "Unknown play mapping."


def is_play_context_possible(
    play_name: str,
    hero_position: str,
    prior_actions: list[str],
) -> tuple[Optional[bool], str]:
    has_entry = any(action in {"Call", "Raise"} for action in prior_actions)
    has_raise = any(action == "Raise" for action in prior_actions)
    raises_count = sum(1 for action in prior_actions if action == "Raise")
    has_limp = any(action == "Limp" for action in prior_actions)

    caller_after_raise = False
    seen_raise = False
    for action in prior_actions:
        if action == "Raise":
            seen_raise = True
        elif action == "Call" and seen_raise:
            caller_after_raise = True

    if play_name == "Raising First In":
        is_possible = not has_entry
        return is_possible, "No one entered before you." if is_possible else "Someone already entered the pot."

    if play_name == "Steal":
        if hero_position not in STEAL_POSITIONS:
            return False, "Steal applies only from CO/BTN/SB."
        is_possible = not has_entry
        return is_possible, "Unopened pot from late position." if is_possible else "Pot already opened before you."

    if play_name == "Limp":
        is_possible = not has_raise
        return is_possible, "No raise before you (open-limp/over-limp possible)." if is_possible else "Cannot limp after a raise."

    if play_name == "Isolation Raise":
        is_possible = has_limp and not has_raise
        return is_possible, "Limp(s) before you with no raise." if is_possible else "Needs limp before you and no prior raise."

    if play_name == "3-Bet":
        is_possible = raises_count == 1
        return is_possible, "Exactly one raise before you." if is_possible else "3-bet needs exactly one prior raise."

    if play_name == "4-Bet":
        is_possible = raises_count >= 2
        return is_possible, "Two or more raises before you." if is_possible else "4-bet needs raise + re-raise before you."

    if play_name == "Cold Call":
        if hero_position not in {"UTG", "MP", "CO"}:
            return False, "Cold Call is only considered from UTG/MP/CO in this app."
        is_possible = has_raise
        return is_possible, "Your first action can call a prior raise." if is_possible else "Cold call needs a raise before you."

    if play_name == "Overcall":
        is_possible = has_raise and caller_after_raise
        return is_possible, "Raise + caller before you." if is_possible else "Overcall needs a raise and at least one caller before you."

    if play_name == "Squeeze":
        is_possible = raises_count == 1 and caller_after_raise
        return is_possible, "Raise plus caller(s) before you." if is_possible else "Squeeze needs one raise and caller(s) before you."

    if play_name == "Set Mining":
        is_possible = has_raise
        return is_possible, "Set-mining call is relevant facing a raise." if is_possible else "Set mining here needs a raise before you."

    return None, "No sequence rule configured for this play."


def status_rank(possible: Optional[bool], blocked_by_context: bool) -> int:
    if blocked_by_context:
        return 3
    if possible is True:
        return 0
    if possible is None:
        return 1
    return 2


def status_color_marker(possible: Optional[bool], blocked_by_context: bool) -> str:
    if blocked_by_context:
        return "⚪"
    if possible is True:
        return "🟢"
    if possible is None:
        return "🟡"
    return "🔴"


def evaluate_plays_for_spot(
    hand: Optional[str],
    hero_position: str,
    prior_actions: list[str],
) -> list[dict[str, Any]]:
    evaluated: list[dict[str, Any]] = []
    for play in load_plays():
        if play["name"] == "Limp":
            continue

        if hand is None or not hero_position:
            possible = None
            reason = "Select full hand to evaluate this play."
            blocked_by_context = False
        else:
            context_possible, context_reason = is_play_context_possible(
                play["name"],
                hero_position,
                prior_actions,
            )
            range_possible, range_reason = evaluate_play(play["name"], hand, hero_position)

            if context_possible is False:
                possible = False
                reason = f"Action sequence: {context_reason}"
                blocked_by_context = True
            elif context_possible is True:
                possible = range_possible
                reason = f"Action sequence: {context_reason} {range_reason}"
                blocked_by_context = False
            else:
                possible = range_possible
                reason = range_reason
                blocked_by_context = False

        evaluated.append(
            {
                "play": play,
                "possible": possible,
                "reason": reason,
                "blocked_by_context": blocked_by_context,
            }
        )

    evaluated.sort(key=lambda item: status_rank(item["possible"], item["blocked_by_context"]))
    return evaluated


def infer_prior_actions_from_results(
    results: dict[str, dict[str, Any]],
    hero_seat: str = "bottom_middle",
) -> list[dict[str, str]]:
    hero_position = str(results.get(hero_seat, {}).get("table_position", "")).upper()
    if hero_position not in POSITIONS:
        return []

    position_rank = {position: index for index, position in enumerate(POSITIONS)}
    ordered_players = sorted(
        (
            {
                "seat": seat,
                "position": str(data.get("table_position", "")).upper(),
                "name": str(data.get("name", "")).strip() or seat,
                "raw_action": str(data.get("action", "")).strip().upper(),
            }
            for seat, data in results.items()
            if str(data.get("table_position", "")).upper() in position_rank
        ),
        key=lambda player: position_rank[player["position"]],
    )

    normalized: list[dict[str, str]] = []
    seen_raise = False
    for player in ordered_players:
        if player["seat"] == hero_seat:
            break

        raw_action = player["raw_action"]
        if raw_action in {"", "SB", "BB", "CHECK"}:
            continue

        if raw_action in {"RAISE", "BET", "ALL-IN", "ALLIN"}:
            action = "Raise"
            seen_raise = True
        elif raw_action == "CALL":
            action = "Call" if seen_raise else "Limp"
        elif raw_action == "FOLD":
            action = "Fold"
        else:
            continue

        if action in TRACKED_ACTIONS:
            normalized.append(
                {
                    "seat": player["seat"],
                    "position": player["position"],
                    "name": player["name"],
                    "action": action,
                }
            )

    return normalized