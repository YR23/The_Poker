from __future__ import annotations

import argparse
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

    def select_action(self, obs: dict, rng: random.Random) -> int:
        key = state_key_from_obs(obs)
        mask = obs["legal_actions_mask"]
        legal_indices = [i for i, allowed in enumerate(mask) if allowed == 1]
        if not legal_indices:
            return 0
        if rng.random() < self.epsilon:
            return rng.choice(legal_indices)
        q_values = self.q_table[key]
        best_action = max(legal_indices, key=lambda i: q_values[i])
        return int(best_action)

    def update_terminal(self, transitions: List[Tuple[Tuple, int]], reward: float) -> None:
        for key, action in transitions:
            current = self.q_table[key][action]
            self.q_table[key][action] = current + self.alpha * (reward - current)


def run_training(hands: int, seed: int, starting_stack: float, log_every: int) -> None:
    rng = random.Random(seed)
    env = PokerEnv(seed=seed)
    seating = {position: f"P{i + 1}" for i, position in enumerate(POSITIONS)}
    stacks_by_player = {f"P{i + 1}": starting_stack for i in range(6)}

    agents = {
        pid: EpsilonGreedyAgent(player_id=pid, epsilon=FIXED_EPSILONS[pid])
        for pid in sorted(FIXED_EPSILONS.keys())
    }
    cumulative_rewards = {pid: 0.0 for pid in agents}

    for hand_no in range(1, hands + 1):
        obs, _ = env.reset(starting_stacks_by_player_id=stacks_by_player, seating=seating)
        transitions = {pid: [] for pid in agents}

        done = False
        rewards = {pid: 0.0 for pid in agents}
        while not done and obs is not None:
            player_id = obs["player_id"]
            action = agents[player_id].select_action(obs, rng)
            transitions[player_id].append((state_key_from_obs(obs), action))
            obs, rewards, done, info = env.step(action)

        for pid, agent in agents.items():
            reward = rewards.get(pid, 0.0)
            agent.update_terminal(transitions[pid], reward)
            cumulative_rewards[pid] += reward
        stacks_by_player = dict(info["stacks_by_player"])
        seating = rotate_positions_forward(seating)

        if hand_no % log_every == 0:
            bankrolls = ", ".join([f"{pid}={stacks_by_player[pid]:.2f}" for pid in sorted(stacks_by_player)])
            avg_rewards = ", ".join(
                [f"{pid}={cumulative_rewards[pid] / hand_no:.3f}" for pid in sorted(cumulative_rewards)]
            )
            print(f"[hand {hand_no}] bankrolls: {bankrolls}")
            print(f"[hand {hand_no}] avg_reward_per_hand: {avg_rewards}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train six fixed-epsilon poker agents.")
    parser.add_argument("--hands", type=int, default=200, help="Number of hands to simulate.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed.")
    parser.add_argument("--starting-stack", type=float, default=100.0, help="Starting chips per player.")
    parser.add_argument("--log-every", type=int, default=20, help="Log frequency in hands.")
    args = parser.parse_args()
    run_training(
        hands=args.hands,
        seed=args.seed,
        starting_stack=args.starting_stack,
        log_every=max(1, args.log_every),
    )


if __name__ == "__main__":
    main()
