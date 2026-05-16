"""Tests for flop secondary-risk patterns."""

from __future__ import annotations

from board_secondary_risk import (
    classify_secondary_risk,
    is_akl,
    is_high_monotone,
    is_hll,
    is_two_low_cards,
    secondary_risk_from_flop_text,
)
from equity_mc import parse_flop


def test_high_monotone_ace_broadway() -> None:
    flop = parse_flop("AhKhQh")
    assert is_high_monotone(flop)
    info = secondary_risk_from_flop_text("AhKhQh")
    assert info.category_ids == ("monotone",)
    assert info.label == "High monotone"


def test_low_monotone_not_high_monotone() -> None:
    flop = parse_flop("7h5h3h")
    assert not is_high_monotone(flop)
    assert not classify_secondary_risk(flop).matched


def test_monotone_only_when_suited_akl() -> None:
    flop = parse_flop("AhKh7h")
    assert is_high_monotone(flop)
    assert not is_akl(flop)
    assert secondary_risk_from_flop_text("AhKh7h").category_ids == ("monotone",)


def test_akl_rainbow() -> None:
    flop = parse_flop("AhKd7c")
    assert is_akl(flop)
    info = secondary_risk_from_flop_text("AhKd7c")
    assert info.category_ids == ("akl",)
    assert "Rainbow" in info.subtitle


def test_akl_two_tone() -> None:
    info = secondary_risk_from_flop_text("AhKd7d")
    assert "Two-tone" in info.subtitle


def test_akl_rejects_nine_low() -> None:
    assert not is_akl(parse_flop("AhKd9c"))


def test_hll_paired_low() -> None:
    flop = parse_flop("Jh4d4c")
    assert is_hll(flop)
    info = secondary_risk_from_flop_text("Jh4d4c")
    assert "hll" in info.category_ids
    assert "paired 4" in info.subtitle


def test_hll_rejects_high_pair() -> None:
    assert not is_hll(parse_flop("JhJd4c"))


def test_hll_and_two_low_together() -> None:
    info = secondary_risk_from_flop_text("Jh4d4c")
    assert info.category_ids == ("hll", "two_low")
    assert "HLL board" in info.label
    assert "Two low cards" in info.label
    assert info.subtitle.count("\n") == 1


def test_two_low_k72() -> None:
    flop = parse_flop("Kh7d2c")
    assert is_two_low_cards(flop)
    info = secondary_risk_from_flop_text("Kh7d2c")
    assert info.category_ids == ("two_low",)
    assert "High K" in info.subtitle


def test_two_low_q53() -> None:
    assert is_two_low_cards(parse_flop("Qh5d3c"))


def test_three_low_cards_not_two_low_pattern() -> None:
    assert not is_two_low_cards(parse_flop("7c6s3d"))
    assert not secondary_risk_from_flop_text("7c6s3d").matched


def test_akl_and_two_low_not_combined() -> None:
    assert is_akl(parse_flop("AhKd7c"))
    assert not is_two_low_cards(parse_flop("AhKd7c"))


def test_unclassified_flop() -> None:
    info = secondary_risk_from_flop_text("9h8d2c")
    assert not info.matched
