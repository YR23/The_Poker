"""
Plot a 13x13 preflop strategy matrix from chart JSON (hand:weight CSV strings), using Plotly.

Usage:
  python chart/plot_strategy_matrix.py "chart/100bb/BB/vs UTG RFI.json"
  python chart/plot_strategy_matrix.py path/to/file.json -o out.html
  python chart/plot_strategy_matrix.py path/to/file.json -o out.png   # needs kaleido
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import plotly.graph_objects as go

RANKS = tuple("AKQJT98765432")

ACTION_ORDER = ("fold", "call", "raise 2.5bb", "raise 12.5bb", "all-in")

COLORS = {
    "fold": "#3B7CC9",
    "call": "#4FAE5A",
    "raise 2.5bb": "#D4A017",
    "raise 12.5bb": "#E07050",
    "all-in": "#4E342E",
}

_RANK = set(RANKS)


def hand_combos(hand: str) -> int:
    if len(hand) == 2 and hand[0] == hand[1] and hand[0] in _RANK:
        return 6
    if len(hand) == 3 and hand[2] == "s" and hand[0] in _RANK and hand[1] in _RANK:
        return 4
    if len(hand) == 3 and hand[2] == "o" and hand[0] in _RANK and hand[1] in _RANK:
        return 12
    return 1


def cell_hand(ri: int, ci: int) -> str:
    r1, r2 = RANKS[ri], RANKS[ci]
    if ri == ci:
        return f"{r1}{r2}"
    if ri < ci:
        return f"{r1}{r2}s"
    return f"{r2}{r1}o"


def cell_y_span(ri: int, n: int = 13) -> tuple[float, float]:
    """Row ri=0 (A) at top of chart (high y in default Plotly coords)."""
    y1 = float(n - ri)
    y0 = float(n - 1 - ri)
    return y0, y1


def parse_weights_blob(blob: str) -> dict[str, float]:
    if not blob or not blob.strip():
        return {}
    out: dict[str, float] = {}
    for part in blob.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            continue
        hand, _, rest = part.partition(":")
        hand = hand.strip()
        try:
            out[hand] = float(rest)
        except ValueError:
            continue
    return out


def load_strategy(path: Path) -> dict[str, dict[str, float]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    strat: dict[str, dict[str, float]] = {}
    for action in ACTION_ORDER:
        blob = raw.get(action, "")
        if isinstance(blob, str):
            strat[action] = parse_weights_blob(blob)
        elif isinstance(blob, dict):
            strat[action] = {k: float(v) for k, v in blob.items()}
        else:
            strat[action] = {}
    return strat


def weights_for_hand(strat: dict[str, dict[str, float]], hand: str) -> list[float]:
    return [float(strat[a].get(hand, 0.0)) for a in ACTION_ORDER]


def overall_action_pct(strat: dict[str, dict[str, float]]) -> dict[str, float]:
    hands: set[str] = set()
    for d in strat.values():
        hands.update(d.keys())
    mass = {a: 0.0 for a in ACTION_ORDER}
    denom = 0.0
    for h in hands:
        c = hand_combos(h)
        denom += c
        ws = weights_for_hand(strat, h)
        s = sum(ws)
        if s <= 0:
            continue
        for a, w in zip(ACTION_ORDER, ws, strict=True):
            mass[a] += (w / s) * c
    if denom <= 0:
        return {a: 0.0 for a in ACTION_ORDER}
    return {a: mass[a] / denom * 100.0 for a in ACTION_ORDER}


def _legend_label(action: str, pct: float) -> str:
    if action == "call":
        name = "Call 1.5bb"
    elif action == "raise 2.5bb":
        name = "Raise 2.5bb"
    elif action == "raise 12.5bb":
        name = "Raise 12.5bb"
    elif action == "all-in":
        name = "All-in"
    else:
        name = "Fold"
    return f"{name} ({pct:.1f}%)"


def plot_matrix(strat: dict[str, dict[str, float]], title: str, out_path: Path | None) -> None:
    n = 13
    shapes: list[dict] = []
    annotations: list[dict] = []

    for ri in range(n):
        for ci in range(n):
            hand = cell_hand(ri, ci)
            y0, y1 = cell_y_span(ri, n)
            ws = weights_for_hand(strat, hand)
            total = sum(ws)
            x0 = float(ci)

            if total <= 0:
                shapes.append(
                    dict(
                        type="rect",
                        xref="x",
                        yref="y",
                        x0=x0,
                        x1=x0 + 1,
                        y0=y0,
                        y1=y1,
                        fillcolor="#E8E8E8",
                        line=dict(color="#BBBBBB", width=1),
                        layer="below",
                    )
                )
            else:
                scale = 1.0 / total
                x_cursor = x0
                for w, action in zip(ws, ACTION_ORDER, strict=True):
                    frac = max(0.0, w) * scale
                    if frac <= 0:
                        continue
                    shapes.append(
                        dict(
                            type="rect",
                            xref="x",
                            yref="y",
                            x0=x_cursor,
                            x1=x_cursor + frac,
                            y0=y0,
                            y1=y1,
                            fillcolor=COLORS[action],
                            line=dict(color="#1a1a1a", width=0.5),
                            layer="below",
                        )
                    )
                    x_cursor += frac

            annotations.append(
                dict(
                    x=ci + 0.5,
                    y=(y0 + y1) / 2,
                    text=hand,
                    showarrow=False,
                    font=dict(size=10, color="white", family="Arial Black, Arial, sans-serif"),
                    xref="x",
                    yref="y",
                    bgcolor="rgba(0,0,0,0.42)",
                    borderpad=3,
                    bordercolor="rgba(255,255,255,0.25)",
                    borderwidth=1,
                )
            )

    pct = overall_action_pct(strat)
    legend_traces: list[go.Scatter] = []
    for a in ACTION_ORDER:
        legend_traces.append(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=12, color=COLORS[a], symbol="square", line=dict(width=0)),
                name=_legend_label(a, pct[a]),
                showlegend=True,
            )
        )

    fig = go.Figure(data=legend_traces)

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center"),
        shapes=shapes,
        annotations=annotations,
        xaxis=dict(
            range=[0, n],
            tickmode="array",
            tickvals=[i + 0.5 for i in range(n)],
            ticktext=list(RANKS),
            constrain="domain",
            side="bottom",
            showgrid=False,
            zeroline=False,
        ),
        yaxis=dict(
            range=[0, n],
            scaleanchor="x",
            scaleratio=1,
            tickmode="array",
            tickvals=[n - 1 - i + 0.5 for i in range(n)],
            ticktext=list(RANKS),
            showgrid=False,
            zeroline=False,
        ),
        plot_bgcolor="white",
        width=900,
        height=880,
        margin=dict(l=50, r=30, t=70, b=100),
        legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="center", x=0.5),
        dragmode=False,
    )

    if out_path:
        suf = out_path.suffix.lower()
        if suf == ".html":
            fig.write_html(str(out_path), include_plotlyjs="cdn", config={"displayModeBar": True})
        elif suf in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".pdf"):
            try:
                fig.write_image(str(out_path), scale=2)
            except ValueError as e:
                if "kaleido" in str(e).lower():
                    raise SystemExit(
                        "Static image export needs kaleido. Run: pip install kaleido"
                    ) from e
                raise
        else:
            raise SystemExit(f"Unsupported output suffix {suf!r}; use .html or .png (etc.)")
    else:
        fig.show(config={"displayModeBar": True})


def main() -> None:
    p = argparse.ArgumentParser(description="Plot 13x13 strategy matrix from chart JSON (Plotly).")
    p.add_argument("json_path", type=Path, help="Path to strategy JSON")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Save file (.html recommended; .png needs kaleido)",
    )
    p.add_argument("--title", type=str, default=None, help="Chart title (default: stem of JSON)")
    args = p.parse_args()

    path = args.json_path.expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"Not a file: {path}")

    strat = load_strategy(path)
    title = args.title if args.title else path.stem.replace("_", " ")
    plot_matrix(strat, title, args.output)


if __name__ == "__main__":
    main()
