from __future__ import annotations

import argparse
import json
import os
import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple

from sim.poker_env import ACTION_DIM, PokerEnv
from sim.preflop_engine import POSITIONS


FIXED_EPSILONS = {
    "P1": 0.05,
    "P2": 0.10,
    "P3": 0.20,
    "P4": 0.30,
    "P5": 0.50,
    "P6": 0.80,
}


def _format_cards(cards: List[tuple[str, str]]) -> str:
    return " ".join([f"{rank}-{color}" for rank, color in cards])


def _print_stacks_by_position(seating: Dict[str, str], stacks_by_player: Dict[str, float]) -> None:
    print("Stacks by position:")
    for position in POSITIONS:
        player_id = seating[position]
        print(f"- {position} ({player_id}): {stacks_by_player[player_id]:.2f}")
    print()


def _print_hole_cards_by_position(seating: Dict[str, str], hole_cards: Dict[str, List[tuple[str, str]]]) -> None:
    print("Hole cards:")
    for position in POSITIONS:
        cards = hole_cards.get(position, [])
        if not cards:
            continue
        player_id = seating[position]
        print(f"- {position} ({player_id}): {_format_cards(cards)}")
    print()


def rotate_positions_forward(seating: Dict[str, str]) -> Dict[str, str]:
    rotated: Dict[str, str] = {}
    for idx, position in enumerate(POSITIONS):
        target_position = POSITIONS[idx - 1]
        rotated[target_position] = seating[position]
    return rotated


def bucket(value: float, size: float) -> int:
    if size <= 0:
        return int(value)
    return int(value // size)


def state_key_from_obs(obs: dict) -> Tuple:
    hole = tuple(sorted(card[0] for card in obs["hole_cards_encoded"] if card[0] >= 0))
    suited = (
        len([c for c in obs["hole_cards_encoded"] if c[1] >= 0]) == 2
        and obs["hole_cards_encoded"][0][1] == obs["hole_cards_encoded"][1][1]
    )
    return (
        obs["position"],
        obs["street"],
        bucket(obs["stack"], 5.0),
        bucket(obs["pot"], 5.0),
        bucket(obs["to_call"], 2.0),
        hole,
        int(suited),
        tuple(obs["legal_actions_mask"]),
    )


@dataclass
class EpsilonGreedyAgent:
    player_id: str
    epsilon: float
    alpha: float = 0.1
    q_table: Dict[Tuple, List[float]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.q_table is None:
            self.q_table = defaultdict(lambda: [0.0] * ACTION_DIM)

    def select_action(self, obs: dict, rng: random.Random) -> tuple[int, bool]:
        key = state_key_from_obs(obs)
        mask = obs["legal_actions_mask"]
        legal_indices = [i for i, allowed in enumerate(mask) if allowed == 1]
        if not legal_indices:
            return 0, True
        if rng.random() < self.epsilon:
            return rng.choice(legal_indices), True
        q_values = self.q_table[key]
        best_action = max(legal_indices, key=lambda i: q_values[i])
        return int(best_action), False

    def update_terminal(self, transitions: List[Tuple[Tuple, int]], reward: float) -> None:
        for key, action in transitions:
            current = self.q_table[key][action]
            self.q_table[key][action] = current + self.alpha * (reward - current)


def _parse_trace_hands(raw: str) -> set[int]:
    if not raw.strip():
        return set()
    out: set[int] = set()
    for token in raw.split(","):
        value = token.strip()
        if not value:
            continue
        out.add(int(value))
    return out


def _print_q_tables(agents: Dict[str, EpsilonGreedyAgent], title: str) -> None:
    print(f"=== {title} ===")
    for pid in sorted(agents):
        agent = agents[pid]
        print(f"{pid} (epsilon={agent.epsilon:.2f})")
        if not agent.q_table:
            print("  <empty q-table>")
            continue
        for state_key, q_values in sorted(agent.q_table.items(), key=lambda item: str(item[0])):
            formatted = ", ".join([f"{value:.3f}" for value in q_values])
            print(f"  state={state_key}")
            print(f"  q=[{formatted}]")
    print()


def _save_q_tables(agents: Dict[str, EpsilonGreedyAgent], output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    for pid in sorted(agents):
        agent = agents[pid]
        rows = []
        for state_key, q_values in sorted(agent.q_table.items(), key=lambda item: str(item[0])):
            rows.append({"state": repr(state_key), "q_values": [round(value, 6) for value in q_values]})
        payload = {
            "player_id": pid,
            "epsilon": agent.epsilon,
            "num_states": len(rows),
            "rows": rows,
        }
        target_path = os.path.join(output_dir, f"{pid}_q_table.json")
        with open(target_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)


def run_training(
    hands: int,
    seed: int,
    starting_stack: float,
    log_every: int,
    trace_hands: set[int],
    print_q_tables: bool,
    save_q_dir: str | None,
    quiet: bool,
) -> None:
    rng = random.Random(seed)
    env = PokerEnv(seed=seed)
    seating = {position: f"P{i + 1}" for i, position in enumerate(POSITIONS)}
    stacks_by_player = {f"P{i + 1}": starting_stack for i in range(6)}

    agents = {
        pid: EpsilonGreedyAgent(player_id=pid, epsilon=FIXED_EPSILONS[pid])
        for pid in sorted(FIXED_EPSILONS.keys())
    }
    cumulative_rewards = {pid: 0.0 for pid in agents}
    if print_q_tables and not quiet:
        _print_q_tables(agents, title="Q TABLES BEFORE TRAINING")

    for hand_no in range(1, hands + 1):
        obs, reset_info = env.reset(starting_stacks_by_player_id=stacks_by_player, seating=seating)
        transitions = {pid: [] for pid in agents}
        should_trace = hand_no in trace_hands
        if should_trace:
            print(f"=== TRACE HAND {hand_no} ===")
            eps_line = ", ".join([f"{pid}={agents[pid].epsilon:.2f}" for pid in sorted(agents)])
            print(f"epsilons: {eps_line}")
            _print_stacks_by_position(seating, stacks_by_player)
            _print_hole_cards_by_position(seating, reset_info.get("hole_cards", {}))

        done = False
        rewards = {pid: 0.0 for pid in agents}
        last_info = reset_info
        while not done and obs is not None:
            player_id = obs["player_id"]
            action, explored = agents[player_id].select_action(obs, rng)
            transitions[player_id].append((state_key_from_obs(obs), action))
            if should_trace:
                mode = "explore" if explored else "exploit"
                action_name = obs["action_meanings"][action]
                print(
                    f"[hand {hand_no}] {player_id} ({obs['position']}) "
                    f"street={obs['street']} to_call={obs['to_call']:.2f} "
                    f"action={action_name} mode={mode} epsilon={agents[player_id].epsilon:.2f}"
                )
            obs, rewards, done, info = env.step(action)
            last_info = info

        for pid, agent in agents.items():
            reward = rewards.get(pid, 0.0)
            agent.update_terminal(transitions[pid], reward)
            cumulative_rewards[pid] += reward
        if should_trace:
            board_cards = last_info.get("board", [])
            if board_cards:
                print(f"Board: {_format_cards(board_cards)}")
            else:
                print("Board: (no board shown; hand ended preflop)")
            reward_line = ", ".join([f"{pid}={rewards.get(pid, 0.0):.2f}" for pid in sorted(rewards)])
            print(f"[hand {hand_no}] terminal_rewards: {reward_line}")
            print("Ending stacks by position:")
            ending_stacks = last_info.get("stacks_by_player", {})
            for position in POSITIONS:
                player_id = last_info.get("seating", {}).get(position, seating[position])
                if player_id in ending_stacks:
                    print(f"- {position} ({player_id}): {ending_stacks[player_id]:.2f}")
            print()

        stacks_by_player = dict(last_info["stacks_by_player"])
        seating = rotate_positions_forward(seating)

        if (not quiet) and hand_no % log_every == 0:
            bankrolls = ", ".join([f"{pid}={stacks_by_player[pid]:.2f}" for pid in sorted(stacks_by_player)])
            avg_rewards = ", ".join(
                [f"{pid}={cumulative_rewards[pid] / hand_no:.3f}" for pid in sorted(cumulative_rewards)]
            )
            eps_line = ", ".join([f"{pid}={agents[pid].epsilon:.2f}" for pid in sorted(agents)])
            print(f"[hand {hand_no}] bankrolls: {bankrolls}")
            print(f"[hand {hand_no}] avg_reward_per_hand: {avg_rewards}")
            print(f"[hand {hand_no}] epsilons: {eps_line}")

    if print_q_tables and not quiet:
        _print_q_tables(agents, title="Q TABLES AFTER TRAINING")
    if save_q_dir:
        _save_q_tables(agents, save_q_dir)
        if not quiet:
            print(f"Saved Q tables to: {save_q_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train six fixed-epsilon poker agents.")
    parser.add_argument("--hands", type=int, default=200, help="Number of hands to simulate.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed.")
    parser.add_argument("--starting-stack", type=float, default=100.0, help="Starting chips per player.")
    parser.add_argument("--log-every", type=int, default=20, help="Log frequency in hands.")
    parser.add_argument(
        "--trace-hands",
        type=str,
        default="",
        help="Comma-separated hand numbers to print full action traces (example: 1,101).",
    )
    parser.add_argument(
        "--print-q-tables",
        action="store_true",
        help="Print each player's Q-table before and after training.",
    )
    parser.add_argument(
        "--save-q-dir",
        type=str,
        default=None,
        help="Directory to save per-player Q-table JSON files.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all training prints (except crashes).",
    )
    args = parser.parse_args()
    run_training(
        hands=args.hands,
        seed=args.seed,
        starting_stack=args.starting_stack,
        log_every=max(1, args.log_every),
        trace_hands=_parse_trace_hands(args.trace_hands),
        print_q_tables=args.print_q_tables,
        save_q_dir=args.save_q_dir,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    main()
