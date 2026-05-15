"""CLI: Monte Carlo equity vs villain range (default 10,000 trials)."""

from __future__ import annotations

import argparse
import random
import sys

from chart_range import (
    chart_path,
    list_chart_actions,
    list_positions,
    list_spots,
    load_strategy,
    suggest_villain_action,
    villain_range_from_chart,
)
from equity_mc import expand_range_string, parse_board, parse_hero, run_monte_carlo


def _normalize_stack(s: str) -> str:
    t = s.strip().lower().replace(" ", "")
    if t in ("100bb", "40bb", "20bb"):
        return t
    if t == "100":
        return "100bb"
    if t == "40":
        return "40bb"
    if t == "20":
        return "20bb"
    raise ValueError(f"Invalid --chart-stack {s!r}; use 100bb, 40bb, or 20bb")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Simulate hero vs villain range (HU all-in to river). "
        "Reports wins, ties (draws), and losses."
    )
    p.add_argument("--hero", help="Your hole cards, e.g. AsKh")
    p.add_argument("--board", help="Flop or full board, e.g. QdJhTc or QdJhTc2s5d")
    p.add_argument(
        "--range",
        default="",
        help="Villain range text (comma-separated): TT-99, AKs, QQ, ATo+",
    )
    p.add_argument(
        "--chart-position",
        metavar="POS",
        help="Chart seat folder (UTG…BB for 100bb; MP…BB for 40bb/20bb). Use with --chart-spot.",
    )
    p.add_argument(
        "--chart-spot",
        metavar="SPOT",
        help='Chart name without .json (e.g. "vs LJ RFI").',
    )
    p.add_argument(
        "--chart-action",
        action="append",
        default=[],
        metavar="ACTION",
        help='Action line(s): call, "raise 12.5bb", etc. Repeat to combine.',
    )
    p.add_argument(
        "--chart-stack",
        default="100bb",
        metavar="Nbb",
        help="Which chart tree: 100bb, 40bb, or 20bb (default 100bb)",
    )
    p.add_argument("--seed", type=int, default=None, help="RNG seed for reproducibility")
    p.add_argument("--trials", type=int, default=10_000, help="Monte Carlo trials (default 10000)")
    p.add_argument(
        "--list-charts",
        action="store_true",
        help="List positions and spots for --chart-stack, then exit",
    )
    args = p.parse_args(argv)

    try:
        stack_bb = _normalize_stack(args.chart_stack)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.list_charts:
        print(f"chart/{stack_bb}/")
        for pos in list_positions(stack_bb):
            print(f"{pos}/")
            for spot in list_spots(pos, stack_bb):
                acts = list_chart_actions(pos, spot, stack_bb)
                act_hint = f"  [{', '.join(acts)}]" if acts else ""
                print(f"  {spot}{act_hint}")
        return 0

    try:
        if not args.hero or not args.board:
            raise ValueError("--hero and --board are required (unless using --list-charts)")
        hero = parse_hero(args.hero)
        board = parse_board(args.board)
        overlap = set(hero) & set(board)
        if overlap:
            raise ValueError("Hero cards overlap with board")

        combo_weights: list[float] | None = None
        use_chart = bool(args.chart_position or args.chart_spot)
        if use_chart:
            if not args.chart_position or not args.chart_spot:
                raise ValueError("Both --chart-position and --chart-spot are required")
            actions = args.chart_action
            if not actions:
                avail = list_chart_actions(args.chart_position, args.chart_spot, stack_bb)
                if not avail:
                    raise ValueError("Chart has no weighted actions; pass --chart-action")
                suggested = suggest_villain_action(
                    load_strategy(chart_path(args.chart_position, args.chart_spot, stack_bb=stack_bb))
                )
                actions = [suggested or avail[0]]
            villain, combo_weights = villain_range_from_chart(
                args.chart_position, args.chart_spot, actions, stack_bb=stack_bb
            )
        else:
            if not args.range.strip():
                raise ValueError("Provide --range or --chart-position/--chart-spot")
            villain = expand_range_string(args.range)
            if not villain:
                raise ValueError("Villain range is empty")

        rng = random.Random(args.seed)

        def prog(done: int, total: int) -> None:
            if done == total or done % max(1, total // 20) == 0:
                pct = 100.0 * done / total
                print(f"\r  {done}/{total} ({pct:.0f}%)", end="", file=sys.stderr, flush=True)

        result = run_monte_carlo(
            hero,
            board,
            villain,
            args.trials,
            rng,
            progress_callback=prog,
            progress_every=max(1, args.trials // 100),
            combo_weights=combo_weights,
        )
        print(file=sys.stderr)

        if use_chart:
            print(f"Chart:      {stack_bb} / {args.chart_position} / {args.chart_spot}")
            print(f"Action(s):  {', '.join(args.chart_action) if args.chart_action else '(default)'}")
            print(f"Combos:     {len(villain):,} (weighted)")
            print()

        win_pct = 100.0 * result.wins / result.trials
        tie_pct = 100.0 * result.ties / result.trials
        loss_pct = 100.0 * result.losses / result.trials

        print(f"Trials:     {result.trials:,}")
        print(f"Wins:       {result.wins:,}  ({win_pct:.2f}%)")
        print(f"Ties:       {result.ties:,}  ({tie_pct:.2f}%)  [split pot]")
        print(f"Losses:     {result.losses:,}  ({loss_pct:.2f}%)")
        print(f"Equity:     {100 * result.equity:.2f}%  (±95% ~ {100 * result.margin_of_error_95:.2f}%)")
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
