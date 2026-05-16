"""Monte Carlo flop equity vs chart range — CustomTkinter."""

from __future__ import annotations

import random
from dataclasses import dataclass
import threading
import tkinter as tk

import customtkinter as ctk

from board_secondary_risk import SecondaryRiskInfo, secondary_risk_from_flop_text
from board_straight_risk import StraightRiskInfo, straight_risk_from_flop_text
from board_texture import FlopHighInfo, classify_flop_text
from card_picker import open_card_picker
from chart_range import list_positions
from equity_mc import parse_board, parse_hero, run_monte_carlo
from spot_resolve import VILLAIN_PREFLOP_ACTIONS, hero_action_for_villain, villain_range_for_spot

DEFAULT_CHART_STACK = "20bb"
METRIC_PANEL_BG = "#14532d"
METRIC_ACCENT = "#86efac"
METRIC_CARD_WIDTH = 300
METRIC_CARD_HEIGHT = 104
SECONDARY_METRIC_CARD_HEIGHT = 132
METRIC_TEXT_WRAP = METRIC_CARD_WIDTH - 70
POSITIONS_100 = ("UTG", "MP", "LJ", "HJ", "CO", "BU", "SB", "BB")
POSITIONS_SHORT = ("MP", "LJ", "HJ", "CO", "BU", "SB", "BB")


@dataclass(frozen=True)
class _MetricCardUi:
    wrap: ctk.CTkFrame
    card: ctk.CTkFrame
    emoji: ctk.CTkLabel
    title: ctk.CTkLabel
    value: ctk.CTkLabel
    sub: ctk.CTkLabel


class EquityApp:
    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root = ctk.CTk()
        self.root.title("The Poker — equity")
        self.root.minsize(980, 640)

        self._eq_thread: threading.Thread | None = None
        self._eq_busy = False
        self._hero_card_codes: set[str] = set()
        self._auto_run_after_id: str | None = None

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self.root, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        ctk.CTkLabel(
            header,
            text="The Poker",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Set seats & villain action, then pick hand + flop — simulation runs automatically",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=("gray30", "gray65"),
        ).pack(anchor="w", pady=(4, 0))

        body = ctk.CTkFrame(self.root, fg_color="transparent")
        body.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)  # gap between stats and bottom controls

        self._build_equity_form(body)

    def _seat_values(self) -> tuple[str, ...]:
        if self._chart_stack_bb() == "100bb":
            return POSITIONS_100
        return POSITIONS_SHORT

    def _build_equity_form(self, parent: ctk.CTkFrame) -> None:
        form = ctk.CTkFrame(parent, corner_radius=12, fg_color=("gray92", "gray17"))
        form.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        form.grid_columnconfigure(0, weight=1)

        self._chart_stack_var = tk.StringVar(value=DEFAULT_CHART_STACK)

        top = ctk.CTkFrame(form, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        for c in range(8):
            top.grid_columnconfigure(c, weight=1 if c % 2 == 1 else 0)

        seats = self._seat_values()
        col = 0

        ctk.CTkLabel(top, text="Hero seat", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=col, padx=(0, 6), pady=4, sticky="w"
        )
        col += 1
        self._hero_pos_var = tk.StringVar(value="BB")
        self._hero_pos_menu = ctk.CTkOptionMenu(
            top,
            variable=self._hero_pos_var,
            values=seats,
            command=lambda _: self._on_setup_changed(),
            width=72,
        )
        self._hero_pos_menu.grid(row=0, column=col, padx=(0, 12), pady=4, sticky="ew")
        col += 1

        ctk.CTkLabel(top, text="Villain seat", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=col, padx=(0, 6), pady=4, sticky="w"
        )
        col += 1
        self._villain_pos_var = tk.StringVar(value="MP")
        self._villain_pos_menu = ctk.CTkOptionMenu(
            top,
            variable=self._villain_pos_var,
            values=seats,
            command=lambda _: self._on_setup_changed(),
            width=72,
        )
        self._villain_pos_menu.grid(row=0, column=col, padx=(0, 12), pady=4, sticky="ew")
        col += 1

        ctk.CTkLabel(top, text="Villain action", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=col, padx=(0, 6), pady=4, sticky="w"
        )
        col += 1
        self._villain_action_var = tk.StringVar(value="RFI")
        self._villain_action_menu = ctk.CTkOptionMenu(
            top,
            variable=self._villain_action_var,
            values=VILLAIN_PREFLOP_ACTIONS,
            command=lambda _: self._on_setup_changed(),
            width=88,
        )
        self._villain_action_menu.grid(row=0, column=col, padx=(0, 12), pady=4, sticky="ew")
        col += 1

        ctk.CTkLabel(top, text="Stack", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=col, padx=(0, 6), pady=4, sticky="w"
        )
        col += 1
        self._chart_stack_menu = ctk.CTkOptionMenu(
            top,
            variable=self._chart_stack_var,
            values=("20bb", "40bb", "100bb"),
            command=self._on_stack_changed,
            width=80,
        )
        self._chart_stack_menu.grid(row=0, column=col, pady=4, sticky="ew")

        self._hero_action_label = ctk.CTkLabel(
            form,
            text="",
            font=ctk.CTkFont(family="Consolas", size=12),
            anchor="w",
        )
        self._hero_action_label.grid(row=1, column=0, padx=12, pady=(0, 4), sticky="ew")

        self._spot_label = ctk.CTkLabel(
            form,
            text="",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=("gray30", "gray60"),
            anchor="w",
        )
        self._spot_label.grid(row=2, column=0, padx=12, pady=(0, 8), sticky="ew")

        cards = ctk.CTkFrame(form, fg_color="transparent")
        cards.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))
        cards.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(cards, text="Your hand (2)").grid(row=0, column=0, padx=(0, 8), pady=6, sticky="w")
        hero_row = ctk.CTkFrame(cards, fg_color="transparent")
        hero_row.grid(row=0, column=1, pady=6, sticky="ew")
        hero_row.grid_columnconfigure(0, weight=1)
        self._hero_entry = ctk.CTkEntry(hero_row, placeholder_text="AsKh")
        self._hero_entry.grid(row=0, column=0, sticky="ew")
        self._hero_entry.bind("<KeyRelease>", lambda _e: self._schedule_auto_run())
        ctk.CTkButton(
            hero_row,
            text="Pick cards",
            width=100,
            command=self._pick_hero_cards,
        ).grid(row=0, column=1, padx=(8, 0))

        ctk.CTkLabel(cards, text="Flop (3)").grid(row=1, column=0, padx=(0, 8), pady=6, sticky="w")
        board_row = ctk.CTkFrame(cards, fg_color="transparent")
        board_row.grid(row=1, column=1, pady=6, sticky="ew")
        board_row.grid_columnconfigure(0, weight=1)
        self._flop_entry = ctk.CTkEntry(board_row, placeholder_text="QdJhTc")
        self._flop_entry.grid(row=0, column=0, sticky="ew")
        self._flop_entry.bind("<KeyRelease>", self._on_flop_entry_changed)
        ctk.CTkButton(
            board_row,
            text="Pick cards",
            width=100,
            command=self._pick_board_cards,
        ).grid(row=0, column=1, padx=(8, 0))

        out = ctk.CTkFrame(parent, corner_radius=12, fg_color=("gray92", "gray17"))
        out.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        out.grid_columnconfigure(0, weight=1)

        self._eq_progress = ctk.CTkLabel(out, text="", font=ctk.CTkFont(family="Consolas", size=12), anchor="w")
        self._eq_progress.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")

        self._eq_results = ctk.CTkLabel(
            out,
            text="Choose seats, villain action, stack, then hand and flop.",
            font=ctk.CTkFont(family="Consolas", size=12),
            anchor="w",
            justify="left",
        )
        self._eq_results.grid(row=1, column=0, padx=12, pady=(4, 8), sticky="ew")

        metric_slot = ctk.CTkFrame(parent, fg_color="transparent")
        metric_slot.grid(row=2, column=0, sticky="nsew")
        metric_slot.grid_columnconfigure(0, weight=1)
        metric_slot.grid_rowconfigure(0, weight=1)
        metric_slot.grid_rowconfigure(2, weight=1)

        self._metrics_frame = ctk.CTkFrame(metric_slot, fg_color="transparent")
        self._metrics_frame.grid(row=1, column=0, sticky="w", padx=12)
        board_ui = self._build_metric_card(self._metrics_frame, "Board texture")
        self._board_metric_wrap = board_ui.wrap
        self._board_metric_card = board_ui.card
        self._board_metric_emoji = board_ui.emoji
        self._board_metric_title = board_ui.title
        self._board_metric_value = board_ui.value
        self._board_metric_sub = board_ui.sub

        straight_ui = self._build_metric_card(self._metrics_frame, "Primary risk")
        self._straight_metric_wrap = straight_ui.wrap
        self._straight_metric_card = straight_ui.card
        self._straight_metric_emoji = straight_ui.emoji
        self._straight_metric_title = straight_ui.title
        self._straight_metric_value = straight_ui.value
        self._straight_metric_sub = straight_ui.sub

        secondary_ui = self._build_metric_card(
            self._metrics_frame,
            "Secondary risk",
            height=SECONDARY_METRIC_CARD_HEIGHT,
        )
        self._secondary_metric_wrap = secondary_ui.wrap
        self._secondary_metric_card = secondary_ui.card
        self._secondary_metric_emoji = secondary_ui.emoji
        self._secondary_metric_title = secondary_ui.title
        self._secondary_metric_value = secondary_ui.value
        self._secondary_metric_sub = secondary_ui.sub

        self._board_metric_wrap.grid(row=0, column=0, sticky="nsew")
        self._straight_metric_wrap.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        self._secondary_metric_wrap.grid(row=0, column=2, sticky="nsew", padx=(12, 0))

        row_opts = ctk.CTkFrame(parent, fg_color="transparent")
        row_opts.grid(row=3, column=0, sticky="sw", pady=(0, 8))
        ctk.CTkLabel(row_opts, text="Trials").pack(side="left", padx=(0, 8))
        self._trials_entry = ctk.CTkEntry(row_opts, width=100)
        self._trials_entry.insert(0, "10000")
        self._trials_entry.pack(side="left", padx=(0, 16))
        self._run_btn = ctk.CTkButton(row_opts, text="Run again", width=120, command=self._on_run_equity)
        self._run_btn.pack(side="left")

        self._on_setup_changed()
        self._update_board_metrics()

    def _build_metric_card(
        self,
        parent: ctk.CTkFrame,
        title: str,
        *,
        height: int = METRIC_CARD_HEIGHT,
    ) -> _MetricCardUi:
        wrap = ctk.CTkFrame(
            parent,
            width=METRIC_CARD_WIDTH,
            height=height,
            fg_color="transparent",
        )
        wrap.pack_propagate(False)

        card = ctk.CTkFrame(
            wrap,
            corner_radius=12,
            fg_color=METRIC_PANEL_BG,
            border_width=1,
            border_color="#166534",
        )
        card.pack(fill="both", expand=True)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=12)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(anchor="nw", fill="x")

        emoji = ctk.CTkLabel(top, text="—", font=ctk.CTkFont(size=22), width=28)
        emoji.pack(side="left", padx=(0, 10))

        text_col = ctk.CTkFrame(top, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)

        title_lbl = ctk.CTkLabel(
            text_col,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=METRIC_ACCENT,
            anchor="w",
            wraplength=METRIC_TEXT_WRAP,
            justify="left",
        )
        title_lbl.pack(anchor="w", fill="x")

        value_lbl = ctk.CTkLabel(
            text_col,
            text="—",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#ecfdf5",
            anchor="w",
            wraplength=METRIC_TEXT_WRAP,
            justify="left",
        )
        value_lbl.pack(anchor="w", fill="x", pady=(2, 0))

        sub_lbl = ctk.CTkLabel(
            text_col,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=METRIC_ACCENT,
            anchor="w",
            wraplength=METRIC_TEXT_WRAP,
            justify="left",
        )
        sub_lbl.pack(anchor="w", fill="x", pady=(2, 0))

        card.pack_forget()
        return _MetricCardUi(wrap=wrap, card=card, emoji=emoji, title=title_lbl, value=value_lbl, sub=sub_lbl)

    def _on_flop_entry_changed(self, _event: tk.Event | None = None) -> None:
        self._update_board_metrics()
        self._schedule_auto_run()

    def _update_board_metrics(self) -> None:
        flop_s = self._flop_entry.get().strip().replace(" ", "")
        if len(flop_s) != 6:
            self._hide_metric_card(self._board_metric_wrap, self._board_metric_card)
            self._hide_metric_card(self._straight_metric_wrap, self._straight_metric_card)
            self._hide_metric_card(self._secondary_metric_wrap, self._secondary_metric_card)
            return
        try:
            board_info = classify_flop_text(flop_s)
            straight_info = straight_risk_from_flop_text(flop_s)
            secondary_info = secondary_risk_from_flop_text(flop_s)
        except ValueError:
            self._hide_metric_card(self._board_metric_wrap, self._board_metric_card)
            self._hide_metric_card(self._straight_metric_wrap, self._straight_metric_card)
            self._hide_metric_card(self._secondary_metric_wrap, self._secondary_metric_card)
            return
        self._apply_board_metric(board_info)
        self._apply_straight_metric(straight_info)
        self._apply_secondary_metric(secondary_info)

    def _show_metric_card(self, wrap: ctk.CTkFrame, card: ctk.CTkFrame) -> None:
        wrap.grid()
        if not card.winfo_ismapped():
            card.pack(fill="both", expand=True)

    def _hide_metric_card(self, wrap: ctk.CTkFrame, card: ctk.CTkFrame) -> None:
        card.pack_forget()
        wrap.grid_remove()

    def _apply_board_metric(self, info: FlopHighInfo) -> None:
        self._board_metric_emoji.configure(text=info.emoji)
        self._board_metric_value.configure(text=info.label)
        self._board_metric_sub.configure(text=f"Highest flop card · {info.high_rank}")
        self._show_metric_card(self._board_metric_wrap, self._board_metric_card)

    def _apply_straight_metric(self, info: StraightRiskInfo) -> None:
        self._straight_metric_emoji.configure(text=info.emoji)
        self._straight_metric_value.configure(text=info.label)
        if info.completions:
            self._straight_metric_sub.configure(text=info.completions_text)
        else:
            self._straight_metric_sub.configure(text="Possible straight")
        self._show_metric_card(self._straight_metric_wrap, self._straight_metric_card)

    def _apply_secondary_metric(self, info: SecondaryRiskInfo) -> None:
        if not info.matched:
            self._hide_metric_card(self._secondary_metric_wrap, self._secondary_metric_card)
            return
        self._secondary_metric_emoji.configure(text=info.emoji)
        self._secondary_metric_value.configure(
            text=info.label,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=13 if len(info.matches) > 1 else 15,
                weight="bold",
            ),
        )
        self._secondary_metric_sub.configure(text=info.subtitle)
        self._show_metric_card(self._secondary_metric_wrap, self._secondary_metric_card)

    def _chart_stack_bb(self) -> str:
        return self._chart_stack_var.get()

    def _on_stack_changed(self, _value: str) -> None:
        seats = self._seat_values()
        for menu, var in (
            (self._hero_pos_menu, self._hero_pos_var),
            (self._villain_pos_menu, self._villain_pos_var),
        ):
            menu.configure(values=seats)
            if var.get() not in seats:
                var.set(seats[0])
        self._on_setup_changed()

    def _on_setup_changed(self) -> None:
        va = self._villain_action_var.get()
        ha = hero_action_for_villain(va)
        self._hero_action_label.configure(
            text=f"Hero action (auto): {ha}   ·   Villain action: {va}  (RFI ↔ Call)"
        )
        try:
            from spot_resolve import resolve_chart

            chart_seat, spot = resolve_chart(
                self._hero_pos_var.get(),
                self._villain_pos_var.get(),
                va,
                self._chart_stack_bb(),
            )
            self._spot_label.configure(
                text=f"Chart: {self._chart_stack_bb()} / {chart_seat} / {spot}.json"
            )
        except ValueError as e:
            self._spot_label.configure(text=str(e))
        self._schedule_auto_run()

    def _schedule_auto_run(self) -> None:
        if self._auto_run_after_id is not None:
            self.root.after_cancel(self._auto_run_after_id)
        self._auto_run_after_id = self.root.after(400, self._try_auto_run)

    def _inputs_ready(self) -> bool:
        hero_s = self._hero_entry.get().strip().replace(" ", "")
        flop_s = self._flop_entry.get().strip().replace(" ", "")
        if len(hero_s) != 4 or len(flop_s) != 6:
            return False
        if self._hero_pos_var.get() == self._villain_pos_var.get():
            return False
        return True

    def _try_auto_run(self) -> None:
        self._auto_run_after_id = None
        if self._inputs_ready() and not self._eq_busy:
            self._on_run_equity()

    def _pick_hero_cards(self) -> None:
        open_card_picker(
            self.root,
            title="Your hand — pick 2 cards",
            pick_count=2,
            blocked=set(),
            initial_text=self._hero_entry.get(),
            on_confirm=self._on_hero_picked,
        )

    def _on_hero_picked(self, compact: str) -> None:
        self._hero_entry.delete(0, "end")
        self._hero_entry.insert(0, compact)
        self._hero_card_codes = {compact[i : i + 2].lower() for i in range(0, len(compact), 2)}
        self._schedule_auto_run()

    def _hero_blocked_codes(self) -> set[str]:
        text = self._hero_entry.get().strip()
        if not text:
            return set(self._hero_card_codes)
        try:
            from card_picker import compact_from_entry

            return {c.lower() for c in compact_from_entry(text, 2)}
        except ValueError:
            return set(self._hero_card_codes)

    def _pick_board_cards(self) -> None:
        open_card_picker(
            self.root,
            title="Flop — pick 3 cards",
            pick_count=3,
            blocked=self._hero_blocked_codes(),
            initial_text=self._flop_entry.get(),
            on_confirm=self._on_board_picked,
        )

    def _on_board_picked(self, compact: str) -> None:
        self._flop_entry.delete(0, "end")
        self._flop_entry.insert(0, compact)
        self._update_board_metrics()
        self._schedule_auto_run()

    def _on_run_equity(self) -> None:
        if self._eq_busy:
            return
        if not self._inputs_ready():
            return

        self._eq_busy = True
        self._run_btn.configure(state="disabled")
        self._eq_progress.configure(text="Running…")
        self._eq_results.configure(text="")

        hero_s = self._hero_entry.get().strip()
        flop_s = self._flop_entry.get().strip()
        hero_pos = self._hero_pos_var.get()
        villain_pos = self._villain_pos_var.get()
        villain_action = self._villain_action_var.get()
        chart_stack_bb = self._chart_stack_bb()

        try:
            n_trials = int(self._trials_entry.get().strip())
        except ValueError:
            self._eq_finish_error("Trials must be an integer")
            return

        def task() -> None:
            try:
                hero = parse_hero(hero_s)
                board = parse_board(flop_s)
                if set(hero) & set(board):
                    raise ValueError("Hero cards overlap with board")

                chart_seat, spot, hero_act, villain_combos, combo_weights = villain_range_for_spot(
                    hero_pos,
                    villain_pos,
                    villain_action,
                    chart_stack_bb,
                )
                chart_note = (
                    f"{chart_stack_bb} / {chart_seat} / {spot}  ·  "
                    f"Villain {villain_action}  ·  Hero {hero_act}\n"
                )

                def prog(done: int, total: int) -> None:
                    pct = 100.0 * done / total
                    self.root.after(
                        0,
                        lambda d=done, t=total, p=pct: self._eq_progress.configure(
                            text=f"Progress: {d}/{t} ({p:.0f}%)"
                        ),
                    )

                result = run_monte_carlo(
                    hero,
                    board,
                    villain_combos,
                    n_trials,
                    random.Random(),
                    progress_callback=prog,
                    progress_every=max(1, n_trials // 100),
                    combo_weights=combo_weights,
                )
                lines = (
                    f"{chart_note}"
                    f"Equity: {100 * result.equity:.2f}%  (±95% ~ {100 * result.margin_of_error_95:.2f}%)\n"
                    f"Wins {result.wins:,}  Ties {result.ties:,}  Losses {result.losses:,}  (n={result.trials:,})"
                )
                self.root.after(0, lambda: self._eq_progress.configure(text="Done."))
                self.root.after(0, lambda t=lines: self._eq_results.configure(text=t))
                self.root.after(0, self._update_board_metrics)
            except Exception as e:
                self.root.after(0, lambda msg=str(e): self._eq_finish_error(msg))
            finally:
                self.root.after(0, self._eq_release)

        self._eq_thread = threading.Thread(target=task, daemon=True)
        self._eq_thread.start()

    def _eq_finish_error(self, msg: str) -> None:
        self._eq_progress.configure(text="Error")
        self._eq_results.configure(text=msg)

    def _eq_release(self) -> None:
        self._eq_busy = False
        self._run_btn.configure(state="normal")

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    EquityApp().run()
