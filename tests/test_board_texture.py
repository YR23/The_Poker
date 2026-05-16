"""Tests for flop high-card classification."""

from __future__ import annotations

from board_texture import classify_flop_text


def test_ace_high_flop() -> None:
    info = classify_flop_text("Ah7d2c")
    assert info.tier_id == "A"
    assert info.label == "Ace-high board"
    assert info.high_rank == "A"


def test_king_high_is_tk_bucket() -> None:
    info = classify_flop_text("Kh7d2c")
    assert info.tier_id == "TK"
    assert info.high_rank == "K"


def test_nine_high_flop() -> None:
    info = classify_flop_text("9h7d2c")
    assert info.tier_id == "9"
    assert info.label == "9-high board"
    assert info.high_rank == "9"
