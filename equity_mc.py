"""Monte Carlo flop all-in equity (hero vs villain range) using treys."""

from __future__ import annotations

import itertools
import random
import re
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from treys import Card, Deck, Evaluator

# Same order as app.py matrix (row/col 0 = Ace)
MATRIX_RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]


def matrix_hand_label(row: int, col: int) -> str:
    if row == col:
        return MATRIX_RANKS[row] + MATRIX_RANKS[col]
    if row < col:
        return MATRIX_RANKS[row] + MATRIX_RANKS[col] + "s"
    return MATRIX_RANKS[col] + MATRIX_RANKS[row] + "o"


def parse_cards_compact(s: str, n: int) -> list[int]:
    """Parse n two-character treys cards from a compact string (e.g. 'AhKd')."""
    t = s.strip().replace(" ", "")
    if len(t) != n * 2:
        raise ValueError(f"Expected {n} cards ({n * 2} chars), got {len(t)!r}")
    out: list[int] = []
    seen: set[int] = set()
    for i in range(0, len(t), 2):
        rank_ch = t[i].upper()
        suit_ch = t[i + 1].lower()
        chunk = rank_ch + suit_ch
        if suit_ch not in Card.CHAR_SUIT_TO_INT_SUIT:
            raise ValueError(f"Bad suit in {chunk!r} (use h d c s)")
        try:
            c = Card.new(chunk)
        except (KeyError, IndexError) as e:
            raise ValueError(f"Bad card {chunk!r}") from e
        if c in seen:
            raise ValueError("Duplicate card in input")
        seen.add(c)
        out.append(c)
    return out


def parse_hero(s: str) -> list[int]:
    return parse_cards_compact(s, 2)


def parse_flop(s: str) -> list[int]:
    return parse_cards_compact(s, 3)


def parse_board(s: str) -> list[int]:
    """Parse 3–5 community cards (flop, flop+turn, or full board)."""
    t = s.strip().replace(" ", "")
    n = len(t) // 2
    if n not in (3, 4, 5) or len(t) != n * 2:
        raise ValueError("Board must be 3, 4, or 5 cards (e.g. QdJhTc or QdJhTc2s5d)")
    return parse_cards_compact(s, n)


def _rank_char_to_int(ch: str) -> int:
    ch = ch.upper()
    if ch not in Card.CHAR_RANK_TO_INT_RANK:
        raise ValueError(f"Bad rank {ch!r}")
    return Card.CHAR_RANK_TO_INT_RANK[ch]


def _pair_combos(rank_int: int) -> list[tuple[int, int]]:
    cards = [Card.new(Card.STR_RANKS[rank_int] + s) for s in "shdc"]
    return [(a, b) for a, b in itertools.combinations(cards, 2)]


def _suited_combos(high_r: int, low_r: int) -> list[tuple[int, int]]:
    if high_r == low_r:
        return _pair_combos(high_r)
    out: list[tuple[int, int]] = []
    for s in "shdc":
        out.append(
            (
                Card.new(Card.STR_RANKS[high_r] + s),
                Card.new(Card.STR_RANKS[low_r] + s),
            )
        )
    return out


def _offsuit_combos(high_r: int, low_r: int) -> list[tuple[int, int]]:
    if high_r == low_r:
        return _pair_combos(high_r)
    out: list[tuple[int, int]] = []
    for s1 in "shdc":
        for s2 in "shdc":
            if s1 == s2:
                continue
            out.append(
                (
                    Card.new(Card.STR_RANKS[high_r] + s1),
                    Card.new(Card.STR_RANKS[low_r] + s2),
                )
            )
    return out


def _all_nonpair_combos(high_r: int, low_r: int) -> list[tuple[int, int]]:
    return _suited_combos(high_r, low_r) + _offsuit_combos(high_r, low_r)


def _parse_pair_range(hi_tok: str, lo_tok: str) -> list[tuple[int, int]]:
    if len(hi_tok) != 2 or len(lo_tok) != 2 or hi_tok[0] != hi_tok[1] or lo_tok[0] != lo_tok[1]:
        raise ValueError(f"Invalid pair range {hi_tok}-{lo_tok}")
    hi = _rank_char_to_int(hi_tok[0])
    lo = _rank_char_to_int(lo_tok[0])
    if hi < lo:
        hi, lo = lo, hi
    combos: set[tuple[int, int]] = set()
    for r in range(lo, hi + 1):
        for c in _pair_combos(r):
            combos.add(tuple(sorted(c)))
    return list(combos)


_A_PLUS_RE = re.compile(r"^([2-9TJQKA])([2-9TJQKA])([so])\+$", re.I)


def _expand_ahigh_plus(high_ch: str, low_ch: str, suited: bool) -> list[tuple[int, int]]:
    high_r = _rank_char_to_int(high_ch)
    low_start = _rank_char_to_int(low_ch)
    ace_r = _rank_char_to_int("A")
    if high_r != ace_r:
        raise ValueError("Only A-high plus ranges are supported (e.g. ATs+, ATo+)")
    if low_start >= ace_r:
        raise ValueError("Plus range must start below Ace")
    combos: set[tuple[int, int]] = set()
    for r in range(low_start, ace_r):
        fn = _suited_combos if suited else _offsuit_combos
        for c in fn(ace_r, r):
            combos.add(tuple(sorted(c)))
    return list(combos)


def expand_range_token(token: str) -> list[tuple[int, int]]:
    t = token.strip()
    if not t:
        return []

    if "-" in t:
        left, right = t.split("-", 1)
        left, right = left.strip(), right.strip()
        if len(left) == 2 and len(right) == 2 and left[0] == left[1] and right[0] == right[1]:
            return _parse_pair_range(left, right)
        raise ValueError(f"Unsupported range token: {token!r}")

    m = _A_PLUS_RE.match(t)
    if m:
        return _expand_ahigh_plus(m.group(1), m.group(2), m.group(3).lower() == "s")

    if len(t) == 2 and t[0] == t[1]:
        r = _rank_char_to_int(t[0])
        return _pair_combos(r)

    if len(t) == 3:
        a, b, suf = t[0], t[1], t[2].lower()
        hi = max(_rank_char_to_int(a), _rank_char_to_int(b))
        lo = min(_rank_char_to_int(a), _rank_char_to_int(b))
        if suf == "s":
            return _suited_combos(hi, lo)
        if suf == "o":
            return _offsuit_combos(hi, lo)
        raise ValueError(f"Expected s or o suffix in {token!r}")

    if len(t) == 2:
        hi = max(_rank_char_to_int(t[0]), _rank_char_to_int(t[1]))
        lo = min(_rank_char_to_int(t[0]), _rank_char_to_int(t[1]))
        return _all_nonpair_combos(hi, lo)

    raise ValueError(f"Unsupported range token: {token!r}")


def expand_range_string(range_text: str) -> list[tuple[int, int]]:
    parts = [p.strip() for p in range_text.split(",") if p.strip()]
    if not parts:
        return []
    combos: set[tuple[int, int]] = set()
    for p in parts:
        for c in expand_range_token(p):
            combos.add(tuple(sorted(c)))
    return list(combos)


def combos_from_matrix(state: Sequence[Sequence[int]], idle_state: int = 0) -> list[tuple[int, int]]:
    combos: set[tuple[int, int]] = set()
    n = len(state)
    for i in range(n):
        for j in range(n):
            if int(state[i][j]) == idle_state:
                continue
            label = matrix_hand_label(i, j)
            for c in expand_range_token(label):
                combos.add(tuple(sorted(c)))
    return list(combos)


def filter_combos_dead(combos: Iterable[tuple[int, int]], dead: set[int]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for a, b in combos:
        if a in dead or b in dead:
            continue
        out.append((a, b))
    return out


def filter_combos_dead_weighted(
    combos: Sequence[tuple[int, int]],
    weights: Sequence[float],
    dead: set[int],
) -> tuple[list[tuple[int, int]], list[float]]:
    if len(combos) != len(weights):
        raise ValueError("combos and weights must have the same length")
    out_c: list[tuple[int, int]] = []
    out_w: list[float] = []
    for (a, b), w in zip(combos, weights, strict=True):
        if a in dead or b in dead:
            continue
        out_c.append((a, b))
        out_w.append(w)
    return out_c, out_w


_FULL_DECK: list[int] | None = None


def _full_deck() -> list[int]:
    global _FULL_DECK
    if _FULL_DECK is None:
        _FULL_DECK = Deck.GetFullDeck()
    return _FULL_DECK


@dataclass
class EquityResult:
    trials: int
    wins: int
    losses: int
    ties: int
    equity: float
    margin_of_error_95: float


def _complete_board(board: list[int], rng: random.Random, dead: set[int]) -> list[int]:
    """Fill missing turn/river cards when board has 3 or 4 cards."""
    need = 5 - len(board)
    if need == 0:
        return board
    pool = [c for c in _full_deck() if c not in dead]
    rng.shuffle(pool)
    return board + pool[:need]


def run_monte_carlo(
    hero: list[int],
    board: list[int],
    villain_combos: list[tuple[int, int]],
    n_trials: int,
    rng: random.Random,
    progress_callback: Callable[[int, int], None] | None = None,
    progress_every: int = 500,
    combo_weights: Sequence[float] | None = None,
) -> EquityResult:
    if n_trials < 1:
        raise ValueError("n_trials must be positive")
    if len(board) not in (3, 4, 5):
        raise ValueError("Board must have 3, 4, or 5 cards")
    dead = set(hero) | set(board)
    if combo_weights is not None:
        valid_villain, valid_weights = filter_combos_dead_weighted(
            villain_combos, combo_weights, dead
        )
    else:
        valid_villain = filter_combos_dead(villain_combos, dead)
        valid_weights = []
    if not valid_villain:
        raise ValueError("No villain combos left after removing dead cards (hero + board)")
    if combo_weights is not None and (not valid_weights or sum(valid_weights) <= 0):
        raise ValueError("Villain combo weights sum to zero after dead-card filter")

    evaluator = Evaluator()
    wins = losses = ties = 0
    runout = len(board) < 5
    use_weights = combo_weights is not None

    for k in range(1, n_trials + 1):
        if use_weights:
            v1, v2 = rng.choices(valid_villain, weights=valid_weights, k=1)[0]
        else:
            v1, v2 = rng.choice(valid_villain)
        used = dead | {v1, v2}
        if runout:
            full_board = _complete_board(board, rng, used)
        else:
            full_board = board

        h_score = evaluator.evaluate(hero, full_board)
        v_score = evaluator.evaluate([v1, v2], full_board)

        if h_score < v_score:
            wins += 1
        elif h_score > v_score:
            losses += 1
        else:
            ties += 1

        if progress_callback and (k % progress_every == 0 or k == n_trials):
            progress_callback(k, n_trials)

    equity = (wins + 0.5 * ties) / n_trials
    p = equity
    # Normal approximation for binomial proportion
    moe = 1.96 * (p * (1.0 - p) / n_trials) ** 0.5 if n_trials else 0.0

    return EquityResult(
        trials=n_trials,
        wins=wins,
        losses=losses,
        ties=ties,
        equity=equity,
        margin_of_error_95=moe,
    )
