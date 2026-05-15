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
