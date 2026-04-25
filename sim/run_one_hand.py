from __future__ import annotations

import json

from sim.preflop_engine import initialize_hand, run_preflop_round, summarize_hand


def main() -> None:
    state = initialize_hand(starting_stack=100.0, small_blind=0.5, big_blind=1.0)
    run_preflop_round(state, seed=42)
    print("Preflop action log:")
    for idx, event in enumerate(state.action_history, start=1):
        position = event["position"]
        action = event["action"]
        amount = event["amount"]
        pot_after = event["pot_after"]
        print(f"{idx:02d}. {position}: {action} {amount:.2f} (pot={pot_after:.2f})")
    print()
    summary = summarize_hand(state)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
