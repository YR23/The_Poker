"""Monte Carlo flop equity vs chart/text range — CustomTkinter."""

from __future__ import annotations

import random
import threading
import tkinter as tk

import customtkinter as ctk

from chart_range import (
    chart_path,
    list_chart_actions,
    list_positions,
    list_spots,
    load_strategy,
    suggest_villain_action,
    villain_range_from_chart,
)
from card_picker import open_card_picker
from equity_mc import expand_range_string, parse_board, parse_hero, run_monte_carlo

DEFAULT_CHART_STACK = "20bb"


class EquityApp:
    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root = ctk.CTk()
        self.root.title("The Poker — equity")
        self.root.minsize(720, 640)

        self._eq_thread: threading.Thread | None = None
        self._eq_busy = False
        self._hero_card_codes: set[str] = set()

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
            text="Flop all-in to river vs chart range (20bb / 40bb / 100bb)",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=("gray30", "gray65"),
        ).pack(anchor="w", pady=(4, 0))

        body = ctk.CTkFrame(self.root, fg_color="transparent")
        body.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)

        self._build_equity_form(body)

    def _build_equity_form(self, parent: ctk.CTkFrame) -> None:
        form = ctk.CTkFrame(parent, corner_radius=12, fg_color=("gray92", "gray17"))
        form.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        form.grid_columnconfigure(1, weight=1)

        r = 0
        ctk.CTkLabel(form, text="Your hand (2)").grid(row=r, column=0, padx=12, pady=8, sticky="w")
        hero_row = ctk.CTkFrame(form, fg_color="transparent")
        hero_row.grid(row=r, column=1, padx=12, pady=8, sticky="ew")
        hero_row.grid_columnconfigure(0, weight=1)
        self._hero_entry = ctk.CTkEntry(hero_row, placeholder_text="AsKh")
        self._hero_entry.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            hero_row,
            text="Pick cards",
            width=100,
            command=self._pick_hero_cards,
        ).grid(row=0, column=1, padx=(8, 0))
        r += 1

        ctk.CTkLabel(form, text="Flop (3)").grid(row=r, column=0, padx=12, pady=8, sticky="w")
        board_row = ctk.CTkFrame(form, fg_color="transparent")
        board_row.grid(row=r, column=1, padx=12, pady=8, sticky="ew")
        board_row.grid_columnconfigure(0, weight=1)
        self._flop_entry = ctk.CTkEntry(board_row, placeholder_text="QdJhTc")
        self._flop_entry.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            board_row,
            text="Pick cards",
            width=100,
            command=self._pick_board_cards,
        ).grid(row=0, column=1, padx=(8, 0))
        r += 1

        ctk.CTkLabel(form, text="Villain range").grid(row=r, column=0, padx=12, pady=8, sticky="nw")
        self._range_entry = ctk.CTkEntry(form, placeholder_text="TT-99, AKs, ATo+ (optional if chart)")
        self._range_entry.grid(row=r, column=1, padx=12, pady=8, sticky="ew")
        r += 1

        self._use_chart_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            form,
            text="Use preflop chart range",
            variable=self._use_chart_var,
            command=self._on_chart_toggle,
        ).grid(row=r, column=0, columnspan=2, padx=12, pady=(4, 0), sticky="w")
        r += 1

        chart_stack_row = ctk.CTkFrame(form, fg_color="transparent")
        chart_stack_row.grid(row=r, column=0, columnspan=2, padx=12, pady=(2, 0), sticky="w")
        ctk.CTkLabel(chart_stack_row, text="Stack depth").pack(side="left", padx=(0, 8))
        self._chart_stack_var = tk.StringVar(value=DEFAULT_CHART_STACK)
        self._chart_stack_menu = ctk.CTkOptionMenu(
            chart_stack_row,
            variable=self._chart_stack_var,
            values=("20bb", "40bb", "100bb"),
            command=self._on_chart_stack_changed,
            width=90,
        )
        self._chart_stack_menu.pack(side="left")
        r += 1

        chart_row = ctk.CTkFrame(form, fg_color="transparent")
        chart_row.grid(row=r, column=0, columnspan=2, padx=12, pady=4, sticky="ew")
        chart_row.grid_columnconfigure(1, weight=1)
        chart_row.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(chart_row, text="Position").grid(row=0, column=0, padx=(0, 8), pady=4, sticky="w")
        positions = list_positions(self._chart_stack_var.get()) or ["BB"]
        self._chart_pos_var = tk.StringVar(value=positions[0])
        self._chart_pos_menu = ctk.CTkOptionMenu(
            chart_row,
            variable=self._chart_pos_var,
            values=positions,
            command=self._on_chart_position_changed,
            width=80,
        )
        self._chart_pos_menu.grid(row=0, column=1, padx=(0, 12), pady=4, sticky="ew")

        ctk.CTkLabel(chart_row, text="Spot").grid(row=0, column=2, padx=(0, 8), pady=4, sticky="w")
        self._chart_spot_var = tk.StringVar(value="")
        self._chart_spot_menu = ctk.CTkOptionMenu(
            chart_row,
            variable=self._chart_spot_var,
            values=[""],
            command=self._on_chart_spot_changed,
            width=300,
        )
        self._chart_spot_menu.grid(row=0, column=3, pady=4, sticky="ew")

        ctk.CTkLabel(chart_row, text="Action").grid(row=1, column=0, padx=(0, 8), pady=4, sticky="w")
        self._chart_action_var = tk.StringVar(value="")
        self._chart_action_menu = ctk.CTkOptionMenu(
            chart_row,
            variable=self._chart_action_var,
            values=[""],
        )
        self._chart_action_menu.grid(row=1, column=1, columnspan=3, pady=4, sticky="ew")
        r += 1

        row_opts = ctk.CTkFrame(form, fg_color="transparent")
        row_opts.grid(row=r, column=0, columnspan=2, padx=12, pady=8, sticky="w")
        ctk.CTkLabel(row_opts, text="Trials").pack(side="left", padx=(0, 8))
        self._trials_entry = ctk.CTkEntry(row_opts, width=100, placeholder_text="10000")
        self._trials_entry.insert(0, "10000")
        self._trials_entry.pack(side="left", padx=(0, 16))
        self._run_btn = ctk.CTkButton(row_opts, text="Run simulation", width=160, command=self._on_run_equity)
        self._run_btn.pack(side="left")

        help_txt = (
            "HU all-in to river. Board: 3 cards = random turn/river; 5 cards = fixed. "
            "Chart: stack 100bb / 40bb / 20bb (default 20bb), then seat, spot, and action. "
            "20bb favors jam ranges; 40bb/20bb have no UTG. "
            "Hand weights from the chart are used when sampling villain combos."
        )
        ctk.CTkLabel(
            parent,
            text=help_txt,
            font=ctk.CTkFont(size=11),
            text_color=("gray30", "gray65"),
            wraplength=560,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(0, 8))

        out = ctk.CTkFrame(parent, corner_radius=12, fg_color=("gray92", "gray17"))
        out.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        out.grid_columnconfigure(0, weight=1)

        self._eq_progress = ctk.CTkLabel(out, text="", font=ctk.CTkFont(family="Consolas", size=12), anchor="w")
        self._eq_progress.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")

        self._eq_results = ctk.CTkLabel(
            out,
            text="Results appear here.",
            font=ctk.CTkFont(family="Consolas", size=12),
            anchor="w",
            justify="left",
        )
        self._eq_results.grid(row=1, column=0, padx=12, pady=(4, 12), sticky="ew")

        self._on_chart_position_changed(positions[0])

    def _chart_stack_bb(self) -> str:
        return self._chart_stack_var.get()

    def _on_chart_stack_changed(self, _value: str) -> None:
        positions = list_positions(self._chart_stack_bb()) or ["BB"]
        self._chart_pos_menu.configure(values=positions)
        if self._chart_pos_var.get() not in positions:
            self._chart_pos_var.set(positions[0])
        self._on_chart_position_changed(self._chart_pos_var.get())

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

    def _on_chart_toggle(self) -> None:
        state = "normal" if self._use_chart_var.get() else "disabled"
        for w in (
            self._chart_stack_menu,
            self._chart_pos_menu,
            self._chart_spot_menu,
            self._chart_action_menu,
        ):
            w.configure(state=state)

    def _on_chart_position_changed(self, position: str) -> None:
        spots = list_spots(position, self._chart_stack_bb())
        if not spots:
            spots = [""]
        self._chart_spot_menu.configure(values=spots)
        self._chart_spot_var.set(spots[0])
        self._on_chart_spot_changed(spots[0])

    def _on_chart_spot_changed(self, spot: str) -> None:
        if not spot:
            self._chart_action_menu.configure(values=[""])
            self._chart_action_var.set("")
            return
        position = self._chart_pos_var.get()
        acts = list_chart_actions(position, spot, self._chart_stack_bb())
        if not acts:
            self._chart_action_menu.configure(values=[""])
            self._chart_action_var.set("")
            return
        suggested = suggest_villain_action(
            load_strategy(chart_path(position, spot, stack_bb=self._chart_stack_bb())),
            stack_bb=self._chart_stack_bb(),
        )
        default = suggested if suggested in acts else acts[0]
        self._chart_action_menu.configure(values=acts)
        self._chart_action_var.set(default)

    def _on_run_equity(self) -> None:
        if self._eq_busy:
            return
        self._eq_busy = True
        self._run_btn.configure(state="disabled")
        self._eq_progress.configure(text="Running…")
        self._eq_results.configure(text="")

        hero_s = self._hero_entry.get().strip()
        flop_s = self._flop_entry.get().strip()
        range_s = self._range_entry.get().strip()
        use_chart = self._use_chart_var.get()
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
                overlap = set(hero) & set(board)
                if overlap:
                    raise ValueError("Hero cards overlap with board")

                combo_weights: list[float] | None = None
                chart_note = ""

                if use_chart:
                    pos = self._chart_pos_var.get()
                    spot = self._chart_spot_var.get()
                    action = self._chart_action_var.get()
                    if not spot or not action:
                        raise ValueError("Select chart position, spot, and action")
                    villain_combos, combo_weights = villain_range_from_chart(
                        pos, spot, [action], stack_bb=chart_stack_bb
                    )
                    chart_note = f"Chart ({chart_stack_bb}) {pos} / {spot} / {action}\n"
                    if range_s:
                        extra = expand_range_string(range_s)
                        villain_combos = list(set(villain_combos) | set(extra))
                        combo_weights = None
                else:
                    if not range_s:
                        raise ValueError("Enter villain range text or enable chart range")
                    villain_combos = expand_range_string(range_s)

                if not villain_combos:
                    raise ValueError("Villain range is empty")

                def prog(done: int, total: int) -> None:
                    pct = 100.0 * done / total
                    self.root.after(
                        0,
                        lambda d=done, t=total, p=pct: self._eq_progress.configure(
                            text=f"Progress: {d}/{t} ({p:.0f}%)"
                        ),
                    )

                rng = random.Random()
                result = run_monte_carlo(
                    hero,
                    board,
                    villain_combos,
                    n_trials,
                    rng,
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
