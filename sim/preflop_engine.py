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
    total_contribution: float = 0.0
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
    last_aggressor: Optional[str] = None
    current_street: str = "preflop"
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


def _seat_players(
    starting_stack: float, starting_stacks_by_position: Optional[Dict[str, float]] = None
) -> List[Player]:
    players: List[Player] = []
    for pos in POSITIONS:
        stack = (
            starting_stacks_by_position[pos]
            if starting_stacks_by_position and pos in starting_stacks_by_position
            else starting_stack
        )
        players.append(Player(position=pos, stack=stack))
    return players


def initialize_hand(
    starting_stack: float = 100.0,
    small_blind: float = 0.5,
    big_blind: float = 1.0,
    starting_stacks_by_position: Optional[Dict[str, float]] = None,
) -> HandState:
    players = _seat_players(
        starting_stack=starting_stack,
        starting_stacks_by_position=starting_stacks_by_position,
    )
    state = HandState(players=players, current_bet=big_blind)

    for p in players:
        if p.stack <= 0:
            p.stack = 0.0
            p.folded = True
            p.all_in = True

    sb = players[4]
    bb = players[5]
    _post_blind(sb, small_blind, state)
    _post_blind(bb, big_blind, state)
    return state


def _post_blind(player: Player, amount: float, state: HandState) -> None:
    if player.folded or player.all_in or player.stack <= 0:
        return
    posted = min(player.stack, amount)
    player.stack = _round_money(player.stack - posted)
    player.contribution = _round_money(player.contribution + posted)
    player.total_contribution = _round_money(player.total_contribution + posted)
    state.pot = _round_money(state.pot + posted)
    if player.stack == 0:
        player.all_in = True
    state.action_history.append(
        {
            "street": state.current_street,
            "position": player.position,
            "action": "post_blind",
            "amount": _round_money(posted),
            "pot_after": _round_money(state.pot),
        }
    )


def amount_to_call(player: Player, state: HandState) -> float:
    return _round_money(max(0.0, state.current_bet - player.contribution))


def min_raise_to(player: Player, state: HandState) -> float:
    del player
    # Fixed geometric raise sizing: each legal raise is exactly 3x the current bet.
    # Example: 1 -> 3 -> 9 -> 27
    return _round_money(state.current_bet * 3)


def max_raise_to(player: Player) -> float:
    return _round_money(player.contribution + player.stack)


def _flop_raise_targets(player: Player, state: HandState) -> List[float]:
    max_to = max_raise_to(player)
    to_call = amount_to_call(player, state)
    targets: List[float] = []

    if to_call == 0:
        # Flop open-size options: 50% pot or 75% pot.
        for pct in (0.5, 0.75):
            target = _round_money(state.pot * pct)
            if target > player.contribution and target <= max_to and target > state.current_bet:
                targets.append(target)
    else:
        # Facing a flop bet/raise: only 2x from the current bet size.
        target = _round_money(state.current_bet * 2)
        if target > player.contribution and target <= max_to:
            targets.append(target)

    return sorted(set(targets))


def _is_postflop(street: str) -> bool:
    return street in {"flop", "turn", "river"}


def can_players_bet(state: HandState) -> bool:
    # If fewer than 2 non-folded/non-all-in players remain, no further betting is possible.
    not_all_in = [p for p in state.players if not p.folded and not p.all_in]
    return len(not_all_in) >= 2


def get_legal_actions(player: Player, state: HandState) -> List[Action]:
    if player.folded or player.all_in:
        return []

    actions: List[Action] = []
    to_call = amount_to_call(player, state)
    can_cover_call = player.stack >= to_call
    max_to = max_raise_to(player)

    if to_call == 0:
        actions.append(Action("fold"))
        actions.append(Action("check"))
        if _is_postflop(state.current_street):
            for target in _flop_raise_targets(player, state):
                actions.append(Action("raise", target))
        else:
            min_to = min_raise_to(player, state)
            if max_to >= min_to:
                actions.append(Action("raise", min_to))
    else:
        actions.append(Action("fold"))
        if can_cover_call:
            actions.append(Action("call"))
        else:
            actions.append(Action("call"))

        if _is_postflop(state.current_street):
            for target in _flop_raise_targets(player, state):
                if player.stack > to_call:
                    actions.append(Action("raise", target))
        else:
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
                "street": state.current_street,
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
                "street": state.current_street,
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
        player.total_contribution = _round_money(player.total_contribution + paid)
        state.pot = _round_money(state.pot + paid)
        if player.stack == 0:
            player.all_in = True
        player.has_acted_since_last_raise = True
        state.action_history.append(
            {
                "street": state.current_street,
                "position": player.position,
                "action": "call",
                "amount": _round_money(paid),
                "pot_after": _round_money(state.pot),
            }
        )
        return

    if action.kind == "raise":
        if action.amount is None:
            raise_to = min_raise_to(player, state)
        else:
            raise_to = _round_money(action.amount)
        max_to = max_raise_to(player)
        raise_to = max(player.contribution, min(raise_to, max_to))
        raise_to = _round_money(raise_to)

        to_put = _round_money(raise_to - player.contribution)
        to_put = min(to_put, player.stack)

        player.stack = _round_money(player.stack - to_put)
        player.contribution = _round_money(player.contribution + to_put)
        player.total_contribution = _round_money(player.total_contribution + to_put)
        state.pot = _round_money(state.pot + to_put)

        state.current_bet = max(state.current_bet, player.contribution)

        state.last_aggressor = player.position
        if player.stack == 0:
            player.all_in = True

        for p in state.players:
            if not p.folded and not p.all_in:
                p.has_acted_since_last_raise = False
        player.has_acted_since_last_raise = True
        state.action_history.append(
            {
                "street": state.current_street,
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


def _flop_action_order() -> List[int]:
    return [4, 5, 0, 1, 2, 3]


def prepare_new_street(state: HandState, street: str) -> None:
    state.current_street = street
    state.current_bet = 0.0
    for p in state.players:
        p.contribution = 0.0
        if not p.folded and not p.all_in:
            p.has_acted_since_last_raise = False


def run_betting_round(
    state: HandState,
    order: List[int],
    seed: Optional[int] = None,
) -> HandState:
    rng = random.Random(seed)
    for p in state.players:
        if not p.folded and not p.all_in:
            p.has_acted_since_last_raise = False
    i = 0

    while True:
        if _single_player_remaining(state):
            break
        if not can_players_bet(state):
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


def run_preflop_round(
    state: HandState,
    seed: Optional[int] = None,
) -> HandState:
    state.current_street = "preflop"
    return run_betting_round(state, order=_preflop_action_order(), seed=seed)


def run_flop_round(
    state: HandState,
    seed: Optional[int] = None,
) -> HandState:
    prepare_new_street(state, street="flop")
    return run_betting_round(state, order=_flop_action_order(), seed=seed)


def run_turn_round(
    state: HandState,
    seed: Optional[int] = None,
) -> HandState:
    prepare_new_street(state, street="turn")
    return run_betting_round(state, order=_flop_action_order(), seed=seed)


def run_river_round(
    state: HandState,
    seed: Optional[int] = None,
) -> HandState:
    prepare_new_street(state, street="river")
    return run_betting_round(state, order=_flop_action_order(), seed=seed)


def summarize_hand(state: HandState) -> dict:
    live_players = [p for p in state.players if not p.folded]
    ended_by_folds = len(live_players) == 1
    winner_position = live_players[0].position if ended_by_folds else None
    return {
        "pot": _round_money(state.pot),
        "current_bet": _round_money(state.current_bet),
        "last_aggressor": state.last_aggressor,
        "ended_by_folds": ended_by_folds,
        "winner_position": winner_position,
        "players": [
            {
                "position": p.position,
                "stack": _round_money(p.stack),
                "street_contribution": _round_money(p.contribution),
                "hand_contribution": _round_money(p.total_contribution),
                "status": "folded" if p.folded else ("all-in" if p.all_in else "active"),
            }
            for p in state.players
        ],
    }
