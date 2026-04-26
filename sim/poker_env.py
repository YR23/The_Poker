from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sim.preflop_engine import (
    Action,
    HandState,
    POSITIONS,
    amount_to_call,
    apply_action,
    can_players_bet,
    get_legal_actions,
    initialize_hand,
    min_raise_to,
    prepare_new_street,
    summarize_hand,
)
from sim.run_one_hand import (
    COLORS,
    RANKS,
    _award_pot_to_winner_if_any,
    _build_deck,
    _deal_flop,
    _deal_hole_cards,
    _deal_turn_or_river,
    _settle_showdown,
)

ACTION_MEANINGS = [
    "fold",
    "call",
    "check",
    "raise_preflop_3x",
    "raise_postflop_pot_50",
    "raise_postflop_pot_75",
    "raise_postflop_2x_facing",
    "all_in",
]
ACTION_DIM = len(ACTION_MEANINGS)

STREETS = ["preflop", "flop", "turn", "river"]
PRE_FLOP_ORDER = [0, 1, 2, 3, 4, 5]
POST_FLOP_ORDER = [4, 5, 0, 1, 2, 3]
RANK_TO_INT = {rank: i for i, rank in enumerate(RANKS)}
COLOR_TO_INT = {color: i for i, color in enumerate(COLORS)}


@dataclass
class StepResult:
    obs: Optional[dict]
    rewards: Dict[str, float]
    done: bool
    info: dict


class PokerEnv:
    def __init__(self, small_blind: float = 0.5, big_blind: float = 1.0, seed: Optional[int] = None):
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.rng = random.Random(seed)
        self.seating: Dict[str, str] = {}
        self.stacks_by_player: Dict[str, float] = {}
        self.stack_start_of_hand: Dict[str, float] = {}

        self.state: Optional[HandState] = None
        self.deck: List[Tuple[str, str]] = []
        self.hole_cards: Dict[str, List[Tuple[str, str]]] = {}
        self.board_cards: List[Tuple[str, str]] = []
        self.current_actor_index: Optional[int] = None
        self.done = False

    def reset(
        self,
        starting_stacks_by_player_id: Optional[Dict[str, float]] = None,
        seating: Optional[Dict[str, str]] = None,
    ) -> tuple[Optional[dict], dict]:
        if seating is None:
            self.seating = {pos: f"P{i + 1}" for i, pos in enumerate(POSITIONS)}
        else:
            self.seating = dict(seating)

        if starting_stacks_by_player_id is None:
            self.stacks_by_player = {player_id: 100.0 for player_id in self.seating.values()}
        else:
            self.stacks_by_player = {player_id: round(float(stack), 2) for player_id, stack in starting_stacks_by_player_id.items()}

        self.stack_start_of_hand = dict(self.stacks_by_player)
        starting_stacks_by_position = {
            position: self.stacks_by_player[self.seating[position]]
            for position in POSITIONS
        }

        self.state = initialize_hand(
            starting_stack=100.0,
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            starting_stacks_by_position=starting_stacks_by_position,
        )
        self.done = False
        self.board_cards = []
        self.current_actor_index = None
        self.deck = _build_deck()
        self.rng.shuffle(self.deck)

        active_positions = [
            p.position for p in self.state.players if not p.folded and p.stack > 0
        ]
        self.hole_cards = _deal_hole_cards(active_positions, self.deck)

        self._sync_stacks_from_state()
        self._advance_until_decision_or_terminal()
        obs = self._build_obs() if not self.done else None
        return obs, self._build_info()

    def step(self, action_index: int) -> tuple[Optional[dict], Dict[str, float], bool, dict]:
        if self.done:
            raise RuntimeError("Cannot call step on a finished hand. Call reset first.")
        if self.state is None or self.current_actor_index is None:
            raise RuntimeError("Environment is not ready. Call reset first.")

        player = self.state.players[self.current_actor_index]
        action = self._action_from_index(player, action_index)
        apply_action(player, action, self.state, self.rng)

        self._advance_until_decision_or_terminal()
        obs = self._build_obs() if not self.done else None
        rewards = self._compute_rewards()
        return obs, rewards, self.done, self._build_info()

    def _compute_rewards(self) -> Dict[str, float]:
        if not self.done:
            return {pid: 0.0 for pid in self.stacks_by_player}
        return {
            pid: round(self.stacks_by_player.get(pid, 0.0) - self.stack_start_of_hand.get(pid, 0.0), 2)
            for pid in self.stacks_by_player
        }

    def _build_info(self) -> dict:
        return {
            "seating": dict(self.seating),
            "stacks_by_player": dict(self.stacks_by_player),
            "board": list(self.board_cards),
            "summary": summarize_hand(self.state) if self.state is not None else {},
        }

    def _build_obs(self) -> dict:
        if self.state is None or self.current_actor_index is None:
            raise RuntimeError("No current actor available.")
        player = self.state.players[self.current_actor_index]
        mask = self._legal_action_mask(player)
        return {
            "player_id": self.seating[player.position],
            "position": player.position,
            "street": self.state.current_street,
            "stack": round(player.stack, 2),
            "pot": round(self.state.pot, 2),
            "to_call": amount_to_call(player, self.state),
            "hole_cards": list(self.hole_cards.get(player.position, [])),
            "hole_cards_encoded": self._encode_cards(self.hole_cards.get(player.position, []), pad_to=2),
            "board": list(self.board_cards),
            "board_encoded": self._encode_cards(self.board_cards, pad_to=5),
            "legal_actions_mask": mask,
            "action_meanings": list(ACTION_MEANINGS),
        }

    def _encode_cards(self, cards: List[Tuple[str, str]], pad_to: int) -> List[Tuple[int, int]]:
        encoded = [(RANK_TO_INT[rank], COLOR_TO_INT[color]) for rank, color in cards]
        while len(encoded) < pad_to:
            encoded.append((-1, -1))
        return encoded[:pad_to]

    def _street_order(self) -> List[int]:
        if self.state is None:
            return PRE_FLOP_ORDER
        return PRE_FLOP_ORDER if self.state.current_street == "preflop" else POST_FLOP_ORDER

    def _find_next_actor_index(self) -> Optional[int]:
        if self.state is None:
            return None
        order = self._street_order()
        if not order:
            return None
        start = 0 if self.current_actor_index is None else (order.index(self.current_actor_index) + 1) % len(order)
        for offset in range(len(order)):
            idx = order[(start + offset) % len(order)]
            player = self.state.players[idx]
            if player.folded or player.all_in:
                continue
            if get_legal_actions(player, self.state):
                return idx
        return None

    def _advance_until_decision_or_terminal(self) -> None:
        if self.state is None:
            return
        while True:
            if self._single_player_remaining():
                _award_pot_to_winner_if_any(self.state)
                self._sync_stacks_from_state()
                self.done = True
                self.current_actor_index = None
                return

            if self._round_complete():
                if not self._advance_street_or_settle():
                    self._sync_stacks_from_state()
                    self.done = True
                    self.current_actor_index = None
                    return
                self.current_actor_index = None
                continue

            next_actor = self._find_next_actor_index()
            if next_actor is None:
                if not self._advance_street_or_settle():
                    self._sync_stacks_from_state()
                    self.done = True
                    self.current_actor_index = None
                    return
                self.current_actor_index = None
                continue
            self.current_actor_index = next_actor
            return

    def _single_player_remaining(self) -> bool:
        if self.state is None:
            return True
        return len([p for p in self.state.players if not p.folded]) == 1

    def _round_complete(self) -> bool:
        if self.state is None:
            return True
        if not can_players_bet(self.state):
            return True
        for p in self.state.players:
            if p.folded or p.all_in:
                continue
            if p.contribution < self.state.current_bet:
                return False
            if not p.has_acted_since_last_raise:
                return False
        return True

    def _advance_street_or_settle(self) -> bool:
        if self.state is None:
            return False
        street = self.state.current_street
        if street == "preflop":
            self.board_cards = _deal_flop(self.deck)
            prepare_new_street(self.state, street="flop")
            return True
        if street == "flop":
            self.board_cards.append(_deal_turn_or_river(self.deck))
            prepare_new_street(self.state, street="turn")
            return True
        if street == "turn":
            self.board_cards.append(_deal_turn_or_river(self.deck))
            prepare_new_street(self.state, street="river")
            return True

        _settle_showdown(
            state=self.state,
            seating=self.seating,
            hole_by_position=self.hole_cards,
            board_cards=self.board_cards,
        )
        return False

    def _legal_action_mask(self, player) -> List[int]:
        if self.state is None:
            return [0] * ACTION_DIM
        legal = get_legal_actions(player, self.state)
        mask = [0] * ACTION_DIM
        to_call = amount_to_call(player, self.state)
        for action in legal:
            idx = self._index_for_action(action, to_call=to_call, player=player)
            if idx is not None:
                mask[idx] = 1
        if player.stack > 0:
            mask[7] = 1
        return mask

    def _index_for_action(self, action: Action, to_call: float, player) -> Optional[int]:
        if self.state is None:
            return None
        if action.kind == "fold":
            return 0
        if action.kind == "call":
            return 1
        if action.kind == "check":
            return 2
        if action.kind != "raise":
            return None

        amount = action.amount if action.amount is not None else min_raise_to(player, self.state)
        amount = round(float(amount), 2)
        if self.state.current_street == "preflop":
            return 3

        if to_call == 0:
            target_50 = round(self.state.pot * 0.5, 2)
            target_75 = round(self.state.pot * 0.75, 2)
            if abs(amount - target_50) <= 0.01:
                return 4
            if abs(amount - target_75) <= 0.01:
                return 5
            return 4 if abs(amount - target_50) < abs(amount - target_75) else 5
        return 6

    def _action_from_index(self, player, action_index: int) -> Action:
        if self.state is None:
            raise RuntimeError("State is missing.")
        legal = get_legal_actions(player, self.state)
        if not legal:
            raise RuntimeError(f"No legal actions for {player.position}.")

        if action_index == 7:
            return Action("raise", amount=round(player.contribution + player.stack, 2))

        target = None
        to_call = amount_to_call(player, self.state)
        for candidate in legal:
            if self._index_for_action(candidate, to_call=to_call, player=player) == action_index:
                target = candidate
                break

        if target is None:
            # Defensive fallback: choose any legal action to keep environment stepping.
            target = legal[0]
        return target

    def _sync_stacks_from_state(self) -> None:
        if self.state is None:
            return
        for p in self.state.players:
            self.stacks_by_player[self.seating[p.position]] = round(p.stack, 2)
