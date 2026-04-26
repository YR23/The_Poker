from sim.poker_env import ACTION_DIM, PokerEnv
from sim.preflop_engine import POSITIONS


def _default_seating():
    return {position: f"P{i + 1}" for i, position in enumerate(POSITIONS)}


def _default_stacks():
    return {f"P{i + 1}": 100.0 for i in range(6)}


def _first_legal_action(mask):
    for idx, allowed in enumerate(mask):
        if allowed == 1:
            return idx
    return 0


def test_env_reset_returns_mask_and_obs_shape():
    env = PokerEnv(seed=7)
    obs, info = env.reset(starting_stacks_by_player_id=_default_stacks(), seating=_default_seating())

    assert obs is not None
    assert "player_id" in obs
    assert len(obs["legal_actions_mask"]) == ACTION_DIM
    assert "stacks_by_player" in info
    assert len(obs["hole_cards_encoded"]) == 2
    assert len(obs["board_encoded"]) == 5


def test_env_rollout_finishes_and_rewards_are_stack_delta():
    env = PokerEnv(seed=9)
    seating = _default_seating()
    stacks = _default_stacks()

    obs, _ = env.reset(starting_stacks_by_player_id=stacks, seating=seating)
    done = False
    rewards = {pid: 0.0 for pid in stacks}
    info = {}
    while not done and obs is not None:
        action = _first_legal_action(obs["legal_actions_mask"])
        obs, rewards, done, info = env.step(action)

    assert done is True
    final_stacks = info["stacks_by_player"]
    for pid, start_stack in stacks.items():
        expected = round(final_stacks[pid] - start_stack, 2)
        assert rewards[pid] == expected
