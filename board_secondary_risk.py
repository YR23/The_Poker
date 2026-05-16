"""Classify flop secondary risks (all matching patterns)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from treys import Card

from board_texture import _rank_index, high_rank_from_flop_cards
from equity_mc import parse_flop

LOW_RANK_MAX = "8"  # L in AKL: 8 and below
TWO_LOW_RANK_MAX = "7"  # two-low pattern: 7 and below (incl. 6−)


@dataclass(frozen=True)
class SecondaryRiskMatch:
    category_id: str
    label: str
    detail: str
    emoji: str


@dataclass(frozen=True)
class SecondaryRiskInfo:
    matches: tuple[SecondaryRiskMatch, ...]

    @property
    def matched(self) -> bool:
        return len(self.matches) > 0

    @property
    def category_id(self) -> str:
        if not self.matches:
            return "none"
        if len(self.matches) == 1:
            return self.matches[0].category_id
        return "multi"

    @property
    def category_ids(self) -> tuple[str, ...]:
        return tuple(m.category_id for m in self.matches)

    @property
    def label(self) -> str:
        return " · ".join(m.label for m in self.matches)

    @property
    def subtitle(self) -> str:
        return "\n".join(f"{m.label} — {m.detail}" for m in self.matches)

    @property
    def emoji(self) -> str:
        if len(self.matches) == 1:
            return self.matches[0].emoji
        return "⚠"


def _flop_ranks_suits(flop: list[int]) -> tuple[list[str], list[str]]:
    ranks: list[str] = []
    suits: list[str] = []
    for c in flop[:3]:
        s = Card.int_to_str(c)
        ranks.append(s[0].upper())
        suits.append(s[1].lower())
    return ranks, suits


def _is_low_rank(rank_ch: str) -> bool:
    return _rank_index(rank_ch) <= _rank_index(LOW_RANK_MAX)


def _is_two_low_card_rank(rank_ch: str) -> bool:
    return _rank_index(rank_ch) <= _rank_index(TWO_LOW_RANK_MAX)


def is_high_monotone(flop: list[int]) -> bool:
    """Three cards same suit; highest card T or above."""
    _, suits = _flop_ranks_suits(flop)
    if len(set(suits)) != 1:
        return False
    hi = high_rank_from_flop_cards(flop)
    return _rank_index(hi) >= _rank_index("T")


def is_akl(flop: list[int]) -> bool:
    """Ace + King + low (8 or below); rainbow or two-tone (not monotone)."""
    ranks, suits = _flop_ranks_suits(flop)
    if len(set(suits)) < 2:
        return False
    if len(set(ranks)) != 3:
        return False
    if "A" not in ranks or "K" not in ranks:
        return False
    third = next(r for r in ranks if r not in ("A", "K"))
    return _is_low_rank(third)


def is_hll(flop: list[int]) -> bool:
    """One high card plus a paired low rank (e.g. J-4-4)."""
    ranks, _ = _flop_ranks_suits(flop)
    counts = Counter(ranks)
    if len(counts) != 2:
        return False
    items = counts.most_common()
    if items[0][1] == 2 and items[1][1] == 1:
        pair_rank, high_rank = items[0][0], items[1][0]
    elif items[1][1] == 2 and items[0][1] == 1:
        pair_rank, high_rank = items[1][0], items[0][0]
    else:
        return False
    return _rank_index(high_rank) > _rank_index(pair_rank)


def is_two_low_cards(flop: list[int]) -> bool:
    """Exactly two flop cards are low (7 or below); the third is higher."""
    ranks, _ = _flop_ranks_suits(flop)
    low_count = sum(1 for r in ranks if _is_two_low_card_rank(r))
    return low_count == 2


def _match_high_monotone(flop: list[int]) -> SecondaryRiskMatch | None:
    if not is_high_monotone(flop):
        return None
    hi = high_rank_from_flop_cards(flop)
    return SecondaryRiskMatch(
        category_id="monotone",
        label="High monotone",
        detail=f"Three suited · {hi}-high",
        emoji="🎨",
    )


def _match_hll(flop: list[int]) -> SecondaryRiskMatch | None:
    if not is_hll(flop):
        return None
    ranks, _ = _flop_ranks_suits(flop)
    counts = Counter(ranks)
    pair_rank = next(r for r, n in counts.items() if n == 2)
    high_rank = next(r for r, n in counts.items() if n == 1)
    return SecondaryRiskMatch(
        category_id="hll",
        label="HLL board",
        detail=f"High {high_rank} · paired {pair_rank}s",
        emoji="🎯",
    )


def _match_akl(flop: list[int]) -> SecondaryRiskMatch | None:
    if not is_akl(flop):
        return None
    ranks, suits = _flop_ranks_suits(flop)
    low = next(r for r in ranks if r not in ("A", "K"))
    tone = "Rainbow" if len(set(suits)) == 3 else "Two-tone"
    return SecondaryRiskMatch(
        category_id="akl",
        label="AKL board",
        detail=f"A · K · {low} · {tone}",
        emoji="👑",
    )


def _match_two_low(flop: list[int]) -> SecondaryRiskMatch | None:
    if not is_two_low_cards(flop):
        return None
    ranks, _ = _flop_ranks_suits(flop)
    lows = sorted(
        (r for r in ranks if _is_two_low_card_rank(r)),
        key=_rank_index,
        reverse=True,
    )
    high = next(r for r in ranks if not _is_two_low_card_rank(r))
    return SecondaryRiskMatch(
        category_id="two_low",
        label="Two low cards",
        detail=f"High {high} · {lows[0]} · {lows[1]} (≤{TWO_LOW_RANK_MAX})",
        emoji="⬇",
    )


def classify_secondary_risk(flop: list[int]) -> SecondaryRiskInfo:
    """Return every secondary pattern that applies to this flop."""
    matches: list[SecondaryRiskMatch] = []
    for builder in (_match_high_monotone, _match_hll, _match_akl, _match_two_low):
        m = builder(flop)
        if m is not None:
            matches.append(m)
    return SecondaryRiskInfo(matches=tuple(matches))


def secondary_risk_from_flop_text(flop_compact: str) -> SecondaryRiskInfo:
    return classify_secondary_risk(parse_flop(flop_compact))
