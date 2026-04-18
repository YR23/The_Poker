"""
GTO preflop RFI (Raise First In) ranges based on solver data.

Positions: UTG, LJ, HJ, CO, BTN, SB
Actions: Raise / Call / Fold

Hand notation matches main.py output:
  - Pocket pair : "AA", "KK", ...
  - Suited      : "AKs", "AQs", ...
  - Offsuit     : "AKo", "AQo", ...
"""

# ── UTG  (~13.7%) ─────────────────────────────────────────────────────────────
_UTG = {
    # Row A
    "AA", "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s",
    # Row K
    "AKo", "KK", "KQs", "KJs", "KTs", "K9s",
    # Row Q
    "AQo", "KQo", "QQ", "QJs", "QTs", "Q9s",
    # Row J
    "AJo", "JJ", "JTs",
    # Row T
    "TT", "T9s",
    # Row 9
    "99",
    # Row 8
    "88",
    # Row 7
    "77",
    # Row 6
    "66",
}

# ── UTG+1  (~16.3%) ───────────────────────────────────────────────────────────
_UTG1 = _UTG | {
    "77",
    "A9s", "A8s", "A3s", "A2s",
    "K9s",
    "J9s", "98s", "87s", "76s",
    "KJo",
}

# ── UTG+2  (~19.2%) ───────────────────────────────────────────────────────────
_UTG2 = _UTG1 | {
    "66",
    "A7s", "A6s",
    "K8s", "K7s",
    "Q9s",
    "T8s", "65s", "54s",
    "QJo",
}

# ── Lojack  (~23.5%) ──────────────────────────────────────────────────────────
_LJ = _UTG2 | {
    "55",
    "A5s",
    "K6s", "K5s",
    "Q8s",
    "J8s", "86s", "75s",
    "KTo",
}

# ── Hijack  (~27.9%) ──────────────────────────────────────────────────────────
_HJ = {
    # Row A
    "AA", "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
    # Row K
    "AKo", "KK", "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s", "K4s",
    # Row Q
    "AQo", "KQo", "QQ", "QJs", "QTs", "Q9s", "Q8s",
    # Row J
    "AJo", "KJo", "QJo", "JJ", "JTs", "J9s", "J8s",
    # Row T
    "ATo", "KTo", "QTo", "JTo", "TT", "T9s", "T8s", "T7s",
    # Row 9
    "A9o", "99", "98s", "97s",
    # Row 8
    "A8o", "88", "87s",
    # Row 7
    "77", "76s",
    # Row 6
    "66", "65s",
    # Row 5
    "55", "54s",
    # Row 4
    "44",
    # Row 3
    "33",
    # Row 2
    "22",
}

# ── Cutoff  (~37.3%) ──────────────────────────────────────────────────────────
_CO = {
    # Row A
    "AA", "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
    # Row K
    "AKo", "KK", "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s", "K4s", "K3s", "K2s",
    # Row Q
    "AQo", "KQo", "QQ", "QJs", "QTs", "Q9s", "Q8s", "Q7s", "Q6s", "Q5s",
    # Row J
    "AJo", "KJo", "QJo", "JJ", "JTs", "J9s", "J8s", "J7s",
    # Row T
    "ATo", "KTo", "QTo", "JTo", "TT", "T9s", "T8s", "T7s", "T6s",
    # Row 9
    "A9o", "K9o", "Q9o", "J9o", "T9o", "99", "98s", "97s", "96s",
    # Row 8
    "A8o", "88", "87s", "86s",
    # Row 7
    "A7o", "77", "76s", "75s",
    # Row 6
    "A6o", "66", "65s",
    # Row 5
    "A5o", "55", "54s",
    # Row 4
    "44",
    # Row 3
    "33",
    # Row 2
    "22",
}

# ── Button  (~54.8%) ──────────────────────────────────────────────────────────
_BTN = {
    # Row A
    "AA", "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
    # Row K
    "AKo", "KK", "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s", "K4s", "K3s", "K2s",
    # Row Q
    "AQo", "KQo", "QQ", "QJs", "QTs", "Q9s", "Q8s", "Q7s", "Q6s", "Q5s", "Q4s", "Q3s", "Q2s",
    # Row J
    "AJo", "KJo", "QJo", "JJ", "JTs", "J9s", "J8s", "J7s", "J6s", "J5s", "J4s", "J3s",
    # Row T
    "ATo", "KTo", "QTo", "JTo", "TT", "T9s", "T8s", "T7s", "T6s", "T5s", "T4s", "T3s",
    # Row 9
    "A9o", "K9o", "Q9o", "J9o", "T9o", "99", "98s", "97s", "96s", "95s",
    # Row 8
    "A8o", "K8o", "Q8o", "J8o", "T8o", "98o", "88", "87s", "86s", "85s",
    # Row 7
    "A7o", "K7o", "T7o", "97o", "87o", "77", "76s", "75s", "74s",
    # Row 6
    "A6o", "K6o", "66", "65s", "64s",
    # Row 5
    "A5o", "K5o", "55", "54s", "53s",
    # Row 4
    "A4o", "44", "43s",
    # Row 3
    "A3o", "33",
    # Row 2
    "A2o", "22",
}

# ── Small Blind  (exact chart transcription) ─────────────────────────────────
# Orange in the chart = raise, green = call, white = fold.
_SB_RAISE = {
    # Row A
    "AJs", "ATs", "A9s", "A5s", "AQo", "AJo",
    # Row K
    "KQs", "KJs", "KTs", "KTo", "K6o",
    # Row Q
    "QQ", "QTs", "Q6o",
    # Row J
    "JJ", "J9s", "J3s", "J2s", "J7o",
    # Row T
    "TT", "T5s", "T4s", "T8o",
    # Row 9
    "96s", "98o",
    # Row 8
    "86s", "87o",
    # Row 7
    "75s",
    # Row 6
    "64s",
    # Row 5
    "53s", "52s",
    # Row 4
    "43s",
}

_SB_CALL = {
    # Row A
    "AA", "AKs", "AQs", "A8s", "A7s", "A6s", "A4s", "A3s", "A2s",
    "AKo", "ATo", "A9o", "A8o", "A7o", "A6o", "A5o", "A4o", "A3o", "A2o",
    # Row K
    "KK", "K9s", "K8s", "K7s", "K6s", "K5s", "K4s", "K3s", "K2s",
    "KQo", "KJo", "K9o", "K8o", "K7o", "K5o", "K4o", "K3o", "K2o",
    # Row Q
    "QJs", "Q9s", "Q8s", "Q7s", "Q6s", "Q5s", "Q4s", "Q3s", "Q2s",
    "QJo", "QTo", "Q9o", "Q8o", "Q7o", "Q5o", "Q4o", "Q3o", "Q2o",
    # Row J
    "JTs", "J8s", "J7s", "J6s", "J5s", "J4s",
    "JTo", "J9o", "J8o", "J6o", "J5o", "J4o", "J3o", "J2o",
    # Row T
    "T9s", "T8s", "T7s", "T6s", "T3s", "T2s",
    "T9o", "T7o", "T6o", "T5o", "T4o", "T3o",
    # Row 9
    "99", "98s", "97s", "95s", "94s", "93s", "92s",
    "97o", "96o", "95o",
    # Row 8
    "88", "87s", "85s", "84s", "83s", "82s",
    "86o", "85o",
    # Row 7
    "77", "76s", "74s", "73s", "72s",
    "76o", "75o",
    # Row 6
    "66", "65s", "63s", "62s",
    "65o", "64o",
    # Row 5
    "55", "54s",
    "54o",
    # Row 4
    "44", "42s",
    # Row 3
    "33", "32s",
    # Row 2
    "22",
}


def _all_hand_labels() -> set[str]:
    ranks = "AKQJT98765432"
    hands: set[str] = set()
    for i, r1 in enumerate(ranks):
        for j, r2 in enumerate(ranks):
            if i == j:
                hands.add(f"{r1}{r2}")
            elif i < j:
                hands.add(f"{r1}{r2}s")
            else:
                hands.add(f"{r2}{r1}o")
    return hands


_SB_FOLD = _all_hand_labels() - _SB_RAISE - _SB_CALL

# ── Master lookup ─────────────────────────────────────────────────────────────
RANGES: dict = {
    "UTG":   {"raise": _UTG,       "call": set(),     "fold": None},
    "LJ":    {"raise": _LJ,        "call": set(),     "fold": None},
    "HJ":    {"raise": _HJ,        "call": set(),     "fold": None},
    "CO":    {"raise": _CO,        "call": set(),     "fold": None},
    "BTN":   {"raise": _BTN,       "call": set(),     "fold": None},
    "SB":    {"raise": _SB_RAISE,  "call": _SB_CALL,  "fold": _SB_FOLD},
}

_ALIASES = {
    "utg": "UTG",
    "lj": "LJ", "lojack": "LJ",
    "hj": "HJ", "hijack": "HJ",
    "co": "CO", "cutoff": "CO",
    "btn": "BTN", "button": "BTN",
    "sb": "SB", "smallblind": "SB", "small_blind": "SB",
}

VALID_POSITIONS = list(RANGES.keys())


def get_action(position: str, hand: str) -> str:
    """Return 'Raise', 'Call', or 'Fold' for a position and hand shorthand."""
    pos = _ALIASES.get(position.lower(), position.upper())
    if pos not in RANGES:
        return f"Unknown position '{position}'. Valid: {', '.join(VALID_POSITIONS)}"

    rng = RANGES[pos]

    if hand in rng["raise"]:
        return "Raise"

    if pos == "SB":
        if rng["fold"] and hand in rng["fold"]:
            return "Fold"
        if rng["call"] and hand in rng["call"]:
            return "Call"
        return "Fold"

    return "Fold"
