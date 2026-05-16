"""Classify flop by highest card rank (board texture)."""

from __future__ import annotations

from dataclasses import dataclass

from treys import Card

from equity_mc import parse_flop

RANK_ORDER = "23456789TJQKA"

BOARD_HIGH_TIERS: tuple[tuple[str, str, str], ...] = (
    ("A", "Ace-high board", "🂡"),
    ("TK", "T–K high board", "👑"),
    ("9", "9-high board", "🂩"),
)


@dataclass(frozen=True)
class FlopHighInfo:
    tier_id: str
    label: str
    emoji: str
    high_rank: str


def _rank_index(rank_ch: str) -> int:
    return RANK_ORDER.index(rank_ch.upper())


def high_rank_from_flop_cards(flop: list[int]) -> str:
    if len(flop) < 3:
        raise ValueError("Need at least 3 flop cards")
    best = max(flop[:3], key=lambda c: Card.get_rank_int(c))
    return Card.int_to_str(best)[0].upper()


def classify_flop_high(flop: list[int]) -> FlopHighInfo:
    """Bucket flop by its highest card: Ace, T–K, or 9 and below."""
    hi = high_rank_from_flop_cards(flop)
    if hi == "A":
        tier_id = "A"
    elif _rank_index(hi) >= _rank_index("T"):
        tier_id = "TK"
    else:
        tier_id = "9"
    for tid, label, emoji in BOARD_HIGH_TIERS:
        if tid == tier_id:
            return FlopHighInfo(tier_id=tid, label=label, emoji=emoji, high_rank=hi)
    raise RuntimeError(f"Unknown tier {tier_id}")


def classify_flop_text(flop_compact: str) -> FlopHighInfo:
    return classify_flop_high(parse_flop(flop_compact))
