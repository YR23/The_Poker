"""Tests for equity_mc parsing, filtering, and Monte Carlo."""

from __future__ import annotations

import random

import pytest
from treys import Card

from equity_mc import (
    combos_from_matrix,
    expand_range_string,
    expand_range_token,
    filter_combos_dead,
    parse_board,
    parse_flop,
    parse_hero,
    run_monte_carlo,
)


def test_aa_expands_to_six_combos() -> None:
    combos = expand_range_token("AA")
    assert len(combos) == 6
    assert all(a != b for a, b in combos)


def test_aks_four_combos() -> None:
    combos = expand_range_token("AKs")
    assert len(combos) == 4


def test_expand_range_string_dedupes() -> None:
    c = expand_range_string("AKs, AKs")
    assert len(c) == 4


def test_pair_range_tt_77() -> None:
    combos = expand_range_token("TT-77")
    assert len(combos) == 24  # 4 pairs × 6


def test_parse_hero_flop_no_duplicate() -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        parse_hero("AhAh")


def test_parse_bad_suit() -> None:
    with pytest.raises(ValueError, match="Bad suit"):
        parse_flop("2x3y4z")


def test_filter_combos_dead_removes_blocked() -> None:
    dead = {Card.new("Ah"), Card.new("Ad"), Card.new("As"), Card.new("Ac")}
    combos = expand_range_token("AA")
    filtered = filter_combos_dead(combos, dead)
    assert filtered == []


def test_no_villain_combos_raises() -> None:
    hero = parse_hero("AsAh")
    flop = parse_flop("2c3d4h")
    villain = [tuple(sorted((hero[0], hero[1])))]
    with pytest.raises(ValueError, match="No villain combos"):
        run_monte_carlo(hero, flop, villain, 10, random.Random(0))


def test_aa_vs_kk_equity_high() -> None:
    hero = parse_hero("AhAs")
    flop = parse_flop("2c3d4h")
    villain = expand_range_token("KK")
    rng = random.Random(0)
    r = run_monte_carlo(hero, flop, villain, 400, rng, progress_callback=None)
    assert r.equity > 0.88


def test_combos_from_matrix_respects_idle() -> None:
    st = [[0] * 13 for _ in range(13)]
    st[0][0] = 1  # AA
    st[0][1] = 1  # AKs in app convention (row<col)
    c = combos_from_matrix(st, idle_state=0)
    assert len(c) == 6 + 4


def test_ats_plus_includes_four_suited() -> None:
    c = expand_range_token("ATs+")
    assert len(c) == 16  # AJs, AQs, AKs, ATs × 4 suits each... 4 hand types × 4 = 16


def test_parse_board_five_cards() -> None:
    b = parse_board("2c3d4h5s6c")
    assert len(b) == 5


def test_full_board_no_runout() -> None:
    hero = parse_hero("AhKh")
    board = parse_board("QhJhTh2c3d")  # hero has flush
    villain = expand_range_token("AA")
    r = run_monte_carlo(hero, board, villain, 50, random.Random(2))
    assert r.wins == 50
    assert r.losses == 0


def test_weighted_villain_sampling() -> None:
    hero = parse_hero("AhAs")
    flop = parse_flop("2c3d4h")
    villain = expand_range_token("KK")
    weights = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    r = run_monte_carlo(hero, flop, villain, 200, random.Random(3), combo_weights=weights)
    assert r.equity > 0.85


def test_run_monte_carlo_progress_callback() -> None:
    calls: list[tuple[int, int]] = []

    def cb(d: int, t: int) -> None:
        calls.append((d, t))

    hero = parse_hero("KhKd")
    flop = parse_flop("2c3d9h")
    villain = expand_range_token("QQ")
    run_monte_carlo(hero, flop, villain, 100, random.Random(1), progress_callback=cb, progress_every=25)
    assert calls
