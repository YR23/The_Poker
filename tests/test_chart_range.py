"""Tests for chart_range loading."""

from __future__ import annotations

from chart_range import (
    actions_with_mass,
    chart_path,
    list_chart_actions,
    list_positions,
    list_spots,
    load_strategy,
    suggest_villain_action,
    villain_range_from_chart,
)


def test_list_positions_includes_bb() -> None:
    pos = list_positions()
    assert "BB" in pos


def test_bb_vs_utg_spot_exists() -> None:
    spots = list_spots("BB")
    assert "vs UTG RFI" in spots


def test_bb_vs_utg_has_3bet_action() -> None:
    acts = list_chart_actions("BB", "vs UTG RFI")
    assert "raise 12.5bb" in acts


def test_villain_range_from_chart_non_empty() -> None:
    combos, weights = villain_range_from_chart("BB", "vs UTG RFI", ["raise 12.5bb"])
    assert len(combos) > 0
    assert len(weights) == len(combos)
    assert sum(weights) > 0


def test_suggest_villain_action_prefers_3bet() -> None:
    strat = load_strategy(chart_path("BB", "vs UTG RFI"))
    assert suggest_villain_action(strat) == "raise 12.5bb"


def test_actions_with_mass_skips_empty_fold() -> None:
    strat = load_strategy(chart_path("BB", "vs UTG RFI"))
    acts = actions_with_mass(strat)
    assert "fold" not in acts or any(strat["fold"].values())


def test_40bb_no_utg_mp_rfi_filename() -> None:
    assert "UTG" not in list_positions("40bb")
    assert "MP RFI 19.4%" in list_spots("MP", "40bb")


def test_20bb_no_utg_matches_chart_grid() -> None:
    assert "UTG" not in list_positions("20bb")
    assert "MP RFI 19.1%" in list_spots("MP", "20bb")
    assert "BU RFI 40.8%" in list_spots("BU", "20bb")
    assert "vs BU All-in" in list_spots("BB", "20bb")
    assert "vs BB ISO All-in" in list_spots("SB", "20bb")
    assert "vs CO All-in" in list_spots("HJ", "20bb")
    assert len(list_spots("MP", "20bb")) == 12
    assert len(list_spots("BB", "20bb")) == 9


def test_suggest_villain_action_20bb_prefers_allin() -> None:
    strat = {
        "fold": {"72o": 1.0},
        "call": {},
        "raise 2.5bb": {},
        "raise 12.5bb": {"AA": 0.5},
        "all-in": {"KK": 1.0},
    }
    assert suggest_villain_action(strat, stack_bb="20bb") == "all-in"
