from sim.preflop_engine import (
    initialize_hand,
    get_legal_actions,
    min_raise_to,
    run_preflop_round,
    summarize_hand,
)


def _kinds(actions):
    return {a.kind for a in actions}


def test_blinds_are_posted_correctly():
    state = initialize_hand(starting_stack=100.0, small_blind=0.5, big_blind=1.0)
    sb = state.players[4]
    bb = state.players[5]

    assert state.pot == 1.5
    assert state.current_bet == 1.0
    assert sb.contribution == 0.5
    assert bb.contribution == 1.0
    assert sb.stack == 99.5
    assert bb.stack == 99.0


def test_utg_facing_bb_has_fold_call_raise():
    state = initialize_hand(starting_stack=100.0, small_blind=0.5, big_blind=1.0)
    utg = state.players[0]
    legal = get_legal_actions(utg, state)

    assert _kinds(legal) == {"fold", "call", "raise"}
    assert min_raise_to(utg, state) == 2.0


def test_bb_can_check_when_unopened():
    state = initialize_hand(starting_stack=100.0, small_blind=0.5, big_blind=1.0)
    for idx in [0, 1, 2, 3]:
        p = state.players[idx]
        p.folded = True
    sb = state.players[4]
    sb.contribution = 1.0
    sb.stack = 99.0
    state.pot = 2.0

    bb = state.players[5]
    legal = get_legal_actions(bb, state)
    assert "check" in _kinds(legal)


def test_short_stack_can_call_all_in_only():
    state = initialize_hand(starting_stack=100.0, small_blind=0.5, big_blind=1.0)
    utg = state.players[0]
    utg.stack = 0.6
    legal = get_legal_actions(utg, state)
    assert _kinds(legal) == {"fold", "call"}


def test_round_terminates_and_summary_shapes():
    state = initialize_hand(starting_stack=100.0, small_blind=0.5, big_blind=1.0)
    run_preflop_round(state, seed=7)
    summary = summarize_hand(state)

    assert "pot" in summary
    assert "players" in summary
    assert len(summary["players"]) == 6
    assert summary["pot"] >= 1.5
