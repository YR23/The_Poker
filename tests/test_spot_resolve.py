"""Tests for spot_resolve chart mapping."""

from __future__ import annotations

from spot_resolve import (
    hero_action_for_villain,
    resolve_chart,
    resolve_spot,
    villain_range_for_spot,
)


def test_hero_action_inverse() -> None:
    assert hero_action_for_villain("RFI") == "Call"
    assert hero_action_for_villain("3Bet") == "RFI"


def test_resolve_bb_vs_mp_rfi_20bb() -> None:
    seat, spot = resolve_chart("BB", "MP", "RFI", "20bb")
    assert seat == "BB"
    assert spot == "vs MP RFI"
    assert resolve_spot("BB", "MP", "RFI", "20bb") == "vs MP RFI"


def test_resolve_mp_vs_bb_3bet_20bb() -> None:
    seat, spot = resolve_chart("MP", "BB", "3Bet", "20bb")
    assert seat == "MP"
    assert spot == "vs BB 3Bet"


def test_villain_call_uses_villain_folder_vs_hero_rfi() -> None:
    seat, spot = resolve_chart("BU", "BB", "Call", "100bb")
    assert seat == "BB"
    assert spot == "vs BU RFI"


def test_villain_range_bb_defend_vs_bu_call() -> None:
    chart_seat, spot, hero_act, combos, weights = villain_range_for_spot(
        "BU", "BB", "Call", "100bb"
    )
    assert chart_seat == "BB"
    assert spot == "vs BU RFI"
    assert hero_act == "RFI"
    assert len(combos) > 0
    assert len(weights) == len(combos)


def test_villain_range_from_spot_rfi() -> None:
    chart_seat, spot, hero_act, combos, weights = villain_range_for_spot(
        "BB", "MP", "RFI", "20bb"
    )
    assert chart_seat == "BB"
    assert spot == "vs MP RFI"
    assert hero_act == "Call"
    assert len(combos) > 0
