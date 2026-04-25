from __future__ import annotations

import json
import random
from itertools import combinations

from sim.preflop_engine import (
    initialize_hand,
    run_flop_round,
    run_preflop_round,
    run_river_round,
    run_turn_round,
    summarize_hand,
)


RANKS = "23456789TJQKA"
RANK_ORDER = {r: i for i, r in enumerate(RANKS)}
COLORS = ["black", "red", "blue", "green"]


def _build_deck() -> list[tuple[str, str]]:
    return [(rank, color) for rank in RANKS for color in COLORS]


def _format_starting_hand(card1: tuple[str, str], card2: tuple[str, str]) -> str:
    (r1, c1), (r2, c2) = card1, card2

    high, low = (r1, r2) if RANK_ORDER[r1] >= RANK_ORDER[r2] else (r2, r1)
    if r1 == r2:
        return f"{high}{low}"
    suffix = "s" if c1 == c2 else "o"
    return f"{high}{low}{suffix}"


def _deal_hole_cards(
    positions: list[str], deck: list[tuple[str, str]]
) -> dict[str, list[tuple[str, str]]]:
    hole_cards: dict[str, list[tuple[str, str]]] = {}
    for pos in positions:
        hole_cards[pos] = [deck.pop(), deck.pop()]
    return hole_cards


def _deal_flop(deck: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [deck.pop(), deck.pop(), deck.pop()]


def _deal_turn_or_river(deck: list[tuple[str, str]]) -> tuple[str, str]:
    return deck.pop()


def _is_straight(ranks: list[str]) -> bool:
    values = sorted({RANK_ORDER[r] for r in ranks})
    if len(values) != 5:
        return False
    if values == [0, 1, 2, 3, 12]:
        return True
    return values[-1] - values[0] == 4


def _sorted_ranks_desc(ranks: list[str]) -> list[str]:
    return sorted(ranks, key=lambda r: RANK_ORDER[r], reverse=True)


def _straight_bounds(ranks: list[str]) -> tuple[str, str]:
    values = sorted({RANK_ORDER[r] for r in ranks})
    if values == [0, 1, 2, 3, 12]:
        return ("A", "5")
    low = min(values)
    high = max(values)
    low_rank = next(rank for rank, idx in RANK_ORDER.items() if idx == low)
    high_rank = next(rank for rank, idx in RANK_ORDER.items() if idx == high)
    return (low_rank, high_rank)


def _classify_flop_hand(
    hole_cards: list[tuple[str, str]], board_cards: list[tuple[str, str]]
) -> str:
    all_cards = hole_cards + board_cards
    if len(all_cards) <= 5:
        return _classify_five_card_hand(all_cards, hole_cards, board_cards)

    best_label = "High Card 2"
    best_score = (-1, [])
    for combo in combinations(all_cards, 5):
        label, score = _classify_five_card_hand_with_score(list(combo), hole_cards)
        if score > best_score:
            best_score = score
            best_label = label
    return best_label


def _classify_five_card_hand(
    all_cards: list[tuple[str, str]],
    hole_cards: list[tuple[str, str]],
    board_cards: list[tuple[str, str]],
) -> str:
    label, _ = _classify_five_card_hand_with_score(all_cards, hole_cards)
    return label


def _classify_five_card_hand_with_score(
    all_cards: list[tuple[str, str]], hole_cards: list[tuple[str, str]]
) -> tuple[str, tuple[int, list[int]]]:
    ranks = [rank for rank, _ in all_cards]
    colors = [color for _, color in all_cards]

    rank_counts: dict[str, int] = {}
    for rank in ranks:
        rank_counts[rank] = rank_counts.get(rank, 0) + 1
    counts = sorted(rank_counts.values(), reverse=True)

    is_flush = len(set(colors)) == 1
    is_straight = _is_straight(ranks)
    by_count_then_rank = sorted(
        rank_counts.items(), key=lambda item: (item[1], RANK_ORDER[item[0]]), reverse=True
    )

    if is_straight and is_flush:
        low, high = _straight_bounds(ranks)
        high_idx = RANK_ORDER[high]
        return (f"Straight Flush ({low} to {high})", (8, [high_idx]))
    if counts == [4, 1]:
        quad_rank = next(rank for rank, count in rank_counts.items() if count == 4)
        kicker = max([r for r in ranks if r != quad_rank], key=lambda r: RANK_ORDER[r])
        return (f"Quads of {quad_rank}", (7, [RANK_ORDER[quad_rank], RANK_ORDER[kicker]]))
    if counts == [3, 2]:
        trip_rank = next(rank for rank, count in rank_counts.items() if count == 3)
        pair_rank = next(rank for rank, count in rank_counts.items() if count == 2)
        return (
            f"Full House ({trip_rank} over {pair_rank})",
            (6, [RANK_ORDER[trip_rank], RANK_ORDER[pair_rank]]),
        )
    if is_flush:
        sorted_flush = _sorted_ranks_desc(ranks)
        return (
            f"Flush ({sorted_flush[0]}-high)",
            (5, [RANK_ORDER[r] for r in sorted_flush]),
        )
    if is_straight:
        low, high = _straight_bounds(ranks)
        high_idx = RANK_ORDER[high]
        return (f"Straight ({low} to {high})", (4, [high_idx]))
    if counts == [3, 1, 1]:
        trip_rank = next(rank for rank, count in rank_counts.items() if count == 3)
        hole_ranks = [rank for rank, _ in hole_cards]
        kickers = _sorted_ranks_desc([r for r in ranks if r != trip_rank])
        if hole_ranks[0] == hole_ranks[1] == trip_rank:
            return (
                f"Set of {trip_rank}",
                (3, [RANK_ORDER[trip_rank]] + [RANK_ORDER[r] for r in kickers]),
            )
        return (
            f"Trips of {trip_rank}",
            (3, [RANK_ORDER[trip_rank]] + [RANK_ORDER[r] for r in kickers]),
        )
    if counts == [2, 2, 1]:
        pair_ranks = [rank for rank, count in by_count_then_rank if count == 2]
        kicker = next(rank for rank, count in rank_counts.items() if count == 1)
        return (
            f"Two Pair ({pair_ranks[0]} and {pair_ranks[1]})",
            (2, [RANK_ORDER[pair_ranks[0]], RANK_ORDER[pair_ranks[1]], RANK_ORDER[kicker]]),
        )
    if counts == [2, 1, 1, 1]:
        pair_rank = next(rank for rank, count in rank_counts.items() if count == 2)
        kickers = _sorted_ranks_desc([r for r in ranks if r != pair_rank])
        return (
            f"Pair of {pair_rank}",
            (1, [RANK_ORDER[pair_rank]] + [RANK_ORDER[r] for r in kickers]),
        )
    sorted_high = _sorted_ranks_desc(ranks)
    return (f"High Card {sorted_high[0]}", (0, [RANK_ORDER[r] for r in sorted_high]))


def _format_cards(cards: list[tuple[str, str]]) -> str:
    return " ".join([f"{rank}-{color}" for rank, color in cards])


def _print_action_log(action_history: list[dict[str, float | str]]) -> None:
    print("Action log:")
    for idx, event in enumerate(action_history, start=1):
        street = event["street"]
        position = event["position"]
        action = event["action"]
        amount = event["amount"]
        pot_after = event["pot_after"]
        print(
            f"{idx:02d}. [{street}] {position}: {action} {float(amount):.2f} "
            f"(pot={float(pot_after):.2f})"
        )


def _award_pot_to_winner_if_any(state) -> str | None:
    summary = summarize_hand(state)
    winner_position = summary["winner_position"]
    if winner_position is None:
        return None

    pot = float(summary["pot"])
    for player in state.players:
        if player.position == winner_position:
            player.stack = round(player.stack + pot, 2)
            break

    state.pot = 0.0
    state.current_bet = 0.0
    return str(winner_position)


def main() -> None:
    rng = random.Random()
    deck = _build_deck()
    rng.shuffle(deck)
    
    state = initialize_hand(starting_stack=100.0, small_blind=0.5, big_blind=1.0)
    hole_cards = _deal_hole_cards([p.position for p in state.players], deck=deck)
    run_preflop_round(state, seed=None)
    preflop_events = [e for e in state.action_history if e["street"] == "preflop"]
    active_positions_after_preflop = [p.position for p in state.players if not p.folded]

    print("Hole cards:")
    for player in state.players:
        c1, c2 = hole_cards[player.position]
        shorthand = _format_starting_hand(c1, c2)
        print(
            f"- {player.position}: "
            f"{c1[0]}-{c1[1]} {c2[0]}-{c2[1]} "
            f"({shorthand})"
        )
    print()

    print("Preflop actions:")
    _print_action_log(preflop_events)
    print()

    summary = summarize_hand(state)
    if summary["winner_position"] is not None:
        winner = _award_pot_to_winner_if_any(state)
        settled = summarize_hand(state)
        won_amount = float(summary["pot"])
        print(f"Hand over: {winner} wins the pot ({won_amount:.2f})")
        print()
        print(json.dumps(settled, indent=2))
        return

    flop_cards = _deal_flop(deck)
    run_flop_round(state, seed=None)
    flop_events = [e for e in state.action_history if e["street"] == "flop"]
    active_positions_after_flop = [p.position for p in state.players if not p.folded]

    print(f"Flop: {_format_cards(flop_cards)}")
    print("Flop hands status (active players):")
    for player in state.players:
        if player.position not in active_positions_after_preflop:
            continue
        hand_type = _classify_flop_hand(hole_cards[player.position], flop_cards)
        print(f"- {player.position}: {hand_type}")
    print()

    print("Flop actions (active players only):")
    _print_action_log(flop_events)
    print()
    summary = summarize_hand(state)
    if summary["winner_position"] is not None:
        winner = _award_pot_to_winner_if_any(state)
        settled = summarize_hand(state)
        won_amount = float(summary["pot"])
        print(f"Hand over: {winner} wins the pot ({won_amount:.2f})")
        print()
        print(json.dumps(settled, indent=2))
        return

    turn_card = _deal_turn_or_river(deck)
    board_turn = flop_cards + [turn_card]
    run_turn_round(state, seed=None)
    turn_events = [e for e in state.action_history if e["street"] == "turn"]
    active_positions_after_turn = [p.position for p in state.players if not p.folded]

    print(f"Board (Flop + Turn): {_format_cards(board_turn)}")
    print("Turn hands status (active players):")
    for player in state.players:
        if player.position not in active_positions_after_flop:
            continue
        hand_type = _classify_flop_hand(hole_cards[player.position], board_turn)
        print(f"- {player.position}: {hand_type}")
    print()

    print("Turn actions (active players only):")
    _print_action_log(turn_events)
    print()
    summary = summarize_hand(state)
    if summary["winner_position"] is not None:
        winner = _award_pot_to_winner_if_any(state)
        settled = summarize_hand(state)
        won_amount = float(summary["pot"])
        print(f"Hand over: {winner} wins the pot ({won_amount:.2f})")
        print()
        print(json.dumps(settled, indent=2))
        return

    river_card = _deal_turn_or_river(deck)
    board_river = board_turn + [river_card]
    run_river_round(state, seed=None)
    river_events = [e for e in state.action_history if e["street"] == "river"]
    active_positions_after_river = [p.position for p in state.players if not p.folded]

    print(f"Board (Flop + Turn + River): {_format_cards(board_river)}")
    print("River hands status (active players):")
    for player in state.players:
        if player.position not in active_positions_after_turn:
            continue
        hand_type = _classify_flop_hand(hole_cards[player.position], board_river)
        print(f"- {player.position}: {hand_type}")
    print()

    print("River actions (active players only):")
    _print_action_log(river_events)
    print()
    summary = summarize_hand(state)
    if summary["winner_position"] is not None:
        winner = _award_pot_to_winner_if_any(state)
        settled = summarize_hand(state)
        won_amount = float(summary["pot"])
        print(f"Hand over: {winner} wins the pot ({won_amount:.2f})")
        print()
        print(json.dumps(settled, indent=2))
        return
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
