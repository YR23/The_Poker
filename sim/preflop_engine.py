from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Dict, List, Optional


POSITIONS = ["UTG", "MP", "CO", "BTN", "SB", "BB"]


@dataclass
class Player:
    position: str
    stack: float = 100.0
    contribution: float = 0.0
    folded: bool = False
    all_in: bool = False
    has_acted_since_last_raise: bool = False


@dataclass
class Action:
    kind: str
    amount: Optional[float] = None


@dataclass
class HandState:
    players: List[Player]
    pot: float = 0.0
    current_bet: float = 0.0
    last_full_raise_size: float = 1.0
    last_aggressor: Optional[str] = None
    button_index: int = 3
    action_history: List[Dict[str, float | str]] = None  # type: ignore[assignment]

    @property
    def active_players(self) -> List[Player]:
        return [p for p in self.players if not p.folded]

    def __post_init__(self) -> None:
        if self.action_history is None:
            self.action_history = []


def _round_money(value: float) -> float:
    return round(value + 1e-9, 2)


def _seat_players(starting_stack: float) -> List[Player]:
    return [Player(position=pos, stack=starting_stack) for pos in POSITIONS]


def initialize_hand(
    starting_stack: float = 100.0,
    small_blind: float = 0.5,
    big_blind: float = 1.0,
) -> HandState:
    players = _seat_players(starting_stack=starting_stack)
    state = HandState(players=players, current_bet=big_blind, last_full_raise_size=big_blind)

    sb = players[4]
    bb = players[5]
    _post_blind(sb, small_blind, state)
    _post_blind(bb, big_blind, state)
    return state


def _post_blind(player: Player, amount: float, state: HandState) -> None:
    posted = min(player.stack, amount)
    player.stack = _round_money(player.stack - posted)
    player.contribution = _round_money(player.contribution + posted)
    state.pot = _round_money(state.pot + posted)
    if player.stack == 0:
        player.all_in = True
    state.action_history.append(
        {
            "position": player.position,
            "action": "post_blind",
            "amount": _round_money(posted),
            "pot_after": _round_money(state.pot),
        }
    )


def amount_to_call(player: Player, state: HandState) -> float:
    return _round_money(max(0.0, state.current_bet - player.contribution))


def min_raise_to(player: Player, state: HandState) -> float:
    return _round_money(state.current_bet + state.last_full_raise_size)


def max_raise_to(player: Player) -> float:
    return _round_money(player.contribution + player.stack)


def get_legal_actions(player: Player, state: HandState) -> List[Action]:
    if player.folded or player.all_in:
        return []

    actions: List[Action] = []
    to_call = amount_to_call(player, state)
    can_cover_call = player.stack >= to_call
    max_to = max_raise_to(player)

    if to_call == 0:
        actions.append(Action("check"))
        min_to = min_raise_to(player, state)
        if max_to >= min_to:
            actions.append(Action("raise", min_to))
    else:
        actions.append(Action("fold"))
        if can_cover_call:
            actions.append(Action("call"))
        else:
            actions.append(Action("call"))

        min_to = min_raise_to(player, state)
        if max_to >= min_to and player.stack > to_call:
            actions.append(Action("raise", min_to))

    return actions


def apply_action(player: Player, action: Action, state: HandState, rng: random.Random) -> None:
    if action.kind == "fold":
        player.folded = True
        player.has_acted_since_last_raise = True
        state.action_history.append(
            {
                "position": player.position,
                "action": "fold",
                "amount": 0.0,
                "pot_after": _round_money(state.pot),
            }
        )
        return

    if action.kind == "check":
        player.has_acted_since_last_raise = True
        state.action_history.append(
            {
                "position": player.position,
                "action": "check",
                "amount": 0.0,
                "pot_after": _round_money(state.pot),
            }
        )
        return

    if action.kind == "call":
        to_call = amount_to_call(player, state)
        paid = min(player.stack, to_call)
        player.stack = _round_money(player.stack - paid)
        player.contribution = _round_money(player.contribution + paid)
        state.pot = _round_money(state.pot + paid)
        if player.stack == 0:
            player.all_in = True
        player.has_acted_since_last_raise = True
        state.action_history.append(
            {
                "position": player.position,
                "action": "call",
                "amount": _round_money(paid),
                "pot_after": _round_money(state.pot),
            }
        )
        return

    if action.kind == "raise":
        min_to = min_raise_to(player, state)
        max_to = max_raise_to(player)
        raise_to = _round_money(rng.uniform(min_to, max_to))
        raise_to = max(min_to, min(max_to, raise_to))
        raise_to = _round_money(raise_to)

        to_put = _round_money(raise_to - player.contribution)
        to_put = min(to_put, player.stack)

        player.stack = _round_money(player.stack - to_put)
        player.contribution = _round_money(player.contribution + to_put)
        state.pot = _round_money(state.pot + to_put)

        previous_bet = state.current_bet
        state.current_bet = max(state.current_bet, player.contribution)
        full_raise_size = _round_money(state.current_bet - previous_bet)
        if full_raise_size > 0:
            state.last_full_raise_size = full_raise_size

        state.last_aggressor = player.position
        if player.stack == 0:
            player.all_in = True

        for p in state.players:
            if not p.folded and not p.all_in:
                p.has_acted_since_last_raise = False
        player.has_acted_since_last_raise = True
        state.action_history.append(
            {
                "position": player.position,
                "action": "raise_to",
                "amount": _round_money(state.current_bet),
                "pot_after": _round_money(state.pot),
            }
        )
        return

    raise ValueError(f"Unknown action kind: {action.kind}")


def choose_random_action(player: Player, state: HandState, rng: random.Random) -> Action:
    legal = get_legal_actions(player, state)
    if not legal:
        raise ValueError(f"No legal actions for player {player.position}")
    return rng.choice(legal)


def _all_non_folded_matched_or_all_in(state: HandState) -> bool:
    for p in state.players:
        if p.folded or p.all_in:
            continue
        if p.contribution < state.current_bet:
            return False
    return True


def _all_non_folded_acted_since_last_raise(state: HandState) -> bool:
    for p in state.players:
        if p.folded or p.all_in:
            continue
        if not p.has_acted_since_last_raise:
            return False
    return True


def _single_player_remaining(state: HandState) -> bool:
    return len([p for p in state.players if not p.folded]) == 1


def _preflop_action_order() -> List[int]:
    return [0, 1, 2, 3, 4, 5]


def run_preflop_round(
    state: HandState,
    seed: Optional[int] = None,
) -> HandState:
    rng = random.Random(seed)
    order = _preflop_action_order()
    i = 0

    while True:
        if _single_player_remaining(state):
            break
        if _all_non_folded_matched_or_all_in(state) and _all_non_folded_acted_since_last_raise(state):
            break

        idx = order[i % len(order)]
        i += 1
        player = state.players[idx]
        if player.folded or player.all_in:
            continue

        action = choose_random_action(player, state, rng)
        apply_action(player, action, state, rng)

    return state


def summarize_hand(state: HandState) -> dict:
    live_players = [p for p in state.players if not p.folded]
    ended_by_folds = len(live_players) == 1
    return {
        "pot": _round_money(state.pot),
        "current_bet": _round_money(state.current_bet),
        "last_aggressor": state.last_aggressor,
        "ended_by_folds": ended_by_folds,
        "players": [
            {
                "position": p.position,
                "stack": _round_money(p.stack),
                "contribution": _round_money(p.contribution),
                "status": "folded" if p.folded else ("all-in" if p.all_in else "active"),
            }
            for p in state.players
        ],
    }
