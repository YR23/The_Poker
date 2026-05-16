"""Count distinct five-card straights completable from a flop with two more ranks."""

from __future__ import annotations

from dataclasses import dataclass

from treys import Card

from equity_mc import parse_flop

RANK_ORDER = "23456789TJQKA"

# All 10 hold'em straights (wheel + nine consecutive windows), low → high along the straight.
_STRAIGHT_SEQUENCES: tuple[tuple[str, ...], ...] = (
    tuple("A2345"),
    *(tuple(RANK_ORDER[i : i + 5]) for i in range(9)),
)


@dataclass(frozen=True)
class StraightRiskInfo:
    count: int
    label: str
    emoji: str
    completions: tuple[str, ...]

    @property
    def completions_text(self) -> str:
        return " · ".join(self.completions)


def flop_rank_chars(flop: list[int]) -> frozenset[str]:
    return frozenset(Card.int_to_str(c)[0].upper() for c in flop[:3])


def _format_completion(straight: tuple[str, ...], missing: frozenset[str]) -> str:
    ordered = [r for r in straight if r in missing]
    if len(ordered) != 2:
        raise ValueError("expected exactly two missing ranks")
    if ordered == list(straight[:2]):
        return f"{ordered[1]}-{ordered[0]}"
    return f"{ordered[0]}-{ordered[1]}"


def straight_completions(flop: list[int]) -> tuple[str, ...]:
    """
    Rank pairs still needed to complete each possible straight (e.g. T-9-8 → 7-6, 7-J, J-Q).
    """
    if len(flop) < 3:
        raise ValueError("Need at least 3 flop cards")
    flop_ranks = flop_rank_chars(flop)
    out: list[str] = []
    for straight in _STRAIGHT_SEQUENCES:
        straight_set = frozenset(straight)
        if flop_ranks <= straight_set and len(straight_set - flop_ranks) == 2:
            out.append(_format_completion(straight, straight_set - flop_ranks))
    return tuple(out)


def count_possible_straights(flop: list[int]) -> int:
    return len(straight_completions(flop))


def classify_straight_risk(flop: list[int]) -> StraightRiskInfo:
    completions = straight_completions(flop)
    n = len(completions)
    if n == 0:
        return StraightRiskInfo(
            count=0,
            label="No straight threat",
            emoji="✓",
            completions=(),
        )
    if n == 1:
        return StraightRiskInfo(
            count=1,
            label="1 possible straight",
            emoji="⚠",
            completions=completions,
        )
    return StraightRiskInfo(
        count=n,
        label=f"{n} possible straights",
        emoji="⚠",
        completions=completions,
    )


def straight_risk_from_flop_text(flop_compact: str) -> StraightRiskInfo:
    return classify_straight_risk(parse_flop(flop_compact))
