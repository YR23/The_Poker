"""Map hero/villain seats + villain preflop action → chart seat folder, spot, JSON lines."""

from __future__ import annotations

from chart_range import list_spots, villain_range_from_chart

VILLAIN_PREFLOP_ACTIONS = ("RFI", "3Bet", "Call", "All-in", "ISO")

HERO_ACTION_FOR_VILLAIN: dict[str, str] = {
    "RFI": "Call",
    "3Bet": "RFI",
    "Call": "RFI",
    "All-in": "Call",
    "ISO": "Call",
}


def hero_action_for_villain(villain_action: str) -> str:
    return HERO_ACTION_FOR_VILLAIN.get(villain_action, "Call")


def chart_json_lines_for_villain(villain_action: str, stack_bb: str) -> list[str]:
    if villain_action == "RFI":
        if stack_bb == "20bb":
            return ["raise 2.5bb", "all-in"]
        return ["raise 2.5bb", "raise 12.5bb"]
    if villain_action == "3Bet":
        if stack_bb == "20bb":
            return ["raise 12.5bb", "all-in"]
        return ["raise 12.5bb"]
    if villain_action == "Call":
        return ["call"]
    if villain_action == "All-in":
        return ["all-in"]
    if villain_action == "ISO":
        return ["raise 2.5bb", "raise 12.5bb", "all-in"]
    return ["call"]


def _pick_spot(spots: list[str], exact: str, *, contains: tuple[str, ...] = ()) -> str | None:
    if exact in spots:
        return exact
    for s in spots:
        if all(part in s for part in contains):
            return s
    return None


def resolve_chart(
    hero_pos: str, villain_pos: str, villain_action: str, stack_bb: str
) -> tuple[str, str]:
    """
    Return (chart_seat_folder, spot_stem).

    Charts are stored from the acting player's seat folder.
    When villain calls hero's open, use villain's defend chart: BB/vs BU RFI (call line).
    When villain opens, use hero's defend chart: BB/vs MP RFI (villain raise lines).
    When villain 3bets hero's open, use hero's chart: MP/vs BB 3Bet.
    """
    if villain_action == "Call":
        seat = villain_pos
        spots = list_spots(seat, stack_bb)
        if not spots:
            raise ValueError(f"No charts for seat {seat} at {stack_bb}")
        spot = _pick_spot(
            spots,
            f"vs {hero_pos} RFI",
            contains=(f"vs {hero_pos}", "RFI"),
        )
        if not spot:
            raise ValueError(
                f"No defend-vs-open chart for {seat} vs {hero_pos} RFI at {stack_bb}. "
                f"Available: {', '.join(spots[:8])}…"
            )
        return seat, spot

    seat = hero_pos
    spots = list_spots(seat, stack_bb)
    if not spots:
        raise ValueError(f"No charts for seat {seat} at {stack_bb}")

    if villain_action == "RFI":
        spot = _pick_spot(
            spots,
            f"vs {villain_pos} RFI",
            contains=(f"vs {villain_pos}", "RFI"),
        )
    elif villain_action == "3Bet":
        spot = _pick_spot(
            spots,
            f"vs {villain_pos} 3Bet",
            contains=(f"vs {villain_pos}", "3Bet"),
        )
    elif villain_action == "All-in":
        spot = _pick_spot(
            spots,
            f"vs {villain_pos} All-in",
            contains=(f"vs {villain_pos}", "All-in"),
        )
    elif villain_action == "ISO":
        spot = None
        for cand in (f"vs {villain_pos} ISO", "vs BB ISO", f"BB vs {villain_pos} LFI"):
            spot = _pick_spot(spots, cand)
            if spot:
                break
        if not spot:
            for s in spots:
                if "ISO" in s or "LFI" in s:
                    spot = s
                    break
    else:
        spot = None

    if not spot:
        raise ValueError(
            f"No chart spot for {hero_pos} vs {villain_pos} "
            f"(villain {villain_action}) at {stack_bb}. "
            f"Available: {', '.join(spots[:8])}…"
        )
    return seat, spot


def resolve_spot(hero_pos: str, villain_pos: str, villain_action: str, stack_bb: str) -> str:
    """Spot stem only (legacy); prefer resolve_chart."""
    _, spot = resolve_chart(hero_pos, villain_pos, villain_action, stack_bb)
    return spot


def villain_range_for_spot(
    hero_pos: str,
    villain_pos: str,
    villain_action: str,
    stack_bb: str,
) -> tuple[str, str, str, list[tuple[int, int]], list[float]]:
    """Returns (chart_seat, spot, hero_action_label, combos, weights)."""
    chart_seat, spot = resolve_chart(hero_pos, villain_pos, villain_action, stack_bb)
    lines = chart_json_lines_for_villain(villain_action, stack_bb)
    combos, weights = villain_range_from_chart(chart_seat, spot, lines, stack_bb=stack_bb)
    return chart_seat, spot, hero_action_for_villain(villain_action), combos, weights
