"""Tests for flop straight-completion counting."""

from __future__ import annotations

from board_straight_risk import (
    count_possible_straights,
    straight_completions,
    straight_risk_from_flop_text,
)
from equity_mc import parse_flop


def test_t98_has_three_straights() -> None:
    flop = parse_flop("Th9d8c")
    assert count_possible_straights(flop) == 3
    assert straight_completions(flop) == ("7-6", "7-J", "J-Q")
    info = straight_risk_from_flop_text("Th9d8c")
    assert info.count == 3
    assert info.label == "3 possible straights"
    assert info.completions_text == "7-6 · 7-J · J-Q"


def test_t87_has_two_straights() -> None:
    flop = parse_flop("Th8d7c")
    assert count_possible_straights(flop) == 2
    assert straight_completions(flop) == ("6-9", "9-J")


def test_t76_has_one_straight() -> None:
    flop = parse_flop("Th7d6c")
    assert count_possible_straights(flop) == 1
    assert straight_completions(flop) == ("8-9",)
    info = straight_risk_from_flop_text("Th7d6c")
    assert info.label == "1 possible straight"
    assert info.completions_text == "8-9"


def test_rainbow_low_unconnected() -> None:
    flop = parse_flop("2h7dKc")
    assert count_possible_straights(flop) == 0
    assert straight_completions(flop) == ()
