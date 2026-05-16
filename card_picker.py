"""Popup card picker: 13 ranks × 4 suit colors (red, black, green, blue)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
import customtkinter as ctk

from equity_mc import parse_cards_compact

RANKS = ("A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2")

# UI label, display color, treys suit letter
SUIT_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("♥", "#ef4444", "h"),
    ("♠", "#9ca3af", "s"),
    ("♣", "#22c55e", "c"),
    ("♦", "#3b82f6", "d"),
)

SUIT_LABELS = ("Red", "Black", "Green", "Blue")


def codes_to_compact(codes: list[str]) -> str:
    return "".join(codes)


def compact_from_entry(text: str, n: int) -> list[str]:
    t = text.strip().replace(" ", "")
    if not t:
        return []
    cards = parse_cards_compact(t, n)
    from treys import Card

    return [Card.int_to_str(c) for c in cards]


class CardPickerDialog(ctk.CTkToplevel):
    """Modal grid to pick exactly ``pick_count`` distinct cards."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        title: str,
        pick_count: int,
        blocked: set[str] | None = None,
        initial: list[str] | None = None,
        on_confirm: Callable[[list[str]], None],
    ) -> None:
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.pick_count = pick_count
        self.blocked = {c.lower() for c in (blocked or set())}
        self.on_confirm = on_confirm
        self.selected: list[str] = list(initial or [])

        self._buttons: dict[str, ctk.CTkButton] = {}
        self._status_var = tk.StringVar(value=self._status_text())

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkLabel(
            header,
            text=f"Select {pick_count} card{'s' if pick_count != 1 else ''}",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Red ♥ · Black ♠ · Green ♣ · Blue ♦  ·  click a picked card again to deselect",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60"),
        ).pack(anchor="w", pady=(2, 0))

        self._sel_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(family="Consolas", size=13),
            anchor="w",
        )
        self._sel_label.pack(anchor="w", pady=(6, 0))

        grid_wrap = ctk.CTkFrame(self, corner_radius=10)
        grid_wrap.pack(padx=16, pady=8)

        for col, (sym, color, _) in enumerate(SUIT_COLUMNS):
            ctk.CTkLabel(
                grid_wrap,
                text=SUIT_LABELS[col],
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=color,
                width=52,
            ).grid(row=0, column=col + 1, padx=2, pady=(6, 2))

        for row, rank in enumerate(RANKS, start=1):
            ctk.CTkLabel(
                grid_wrap,
                text=rank,
                font=ctk.CTkFont(size=12, weight="bold"),
                width=28,
            ).grid(row=row, column=0, padx=(6, 2), pady=2)
            for col, (sym, color, suit_ch) in enumerate(SUIT_COLUMNS):
                code = (rank + suit_ch).lower()
                label = f"{rank}{sym}"
                btn = ctk.CTkButton(
                    grid_wrap,
                    text=label,
                    width=52,
                    height=34,
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=color,
                    command=lambda c=code: self._toggle(c),
                )
                btn.grid(row=row, column=col + 1, padx=2, pady=2)
                self._buttons[code] = btn

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=16, pady=(4, 14))

        ctk.CTkLabel(foot, textvariable=self._status_var, font=ctk.CTkFont(size=11)).pack(
            anchor="w", pady=(0, 8)
        )

        btn_row = ctk.CTkFrame(foot, fg_color="transparent")
        btn_row.pack(fill="x")
        ctk.CTkButton(btn_row, text="Clear", width=80, fg_color="#4b5563", command=self._clear).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(btn_row, text="Cancel", width=80, fg_color="#4b5563", command=self.destroy).pack(
            side="right", padx=(8, 0)
        )
        ctk.CTkButton(btn_row, text="OK", width=80, command=self._ok).pack(side="right")

        self._refresh_buttons()
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.after(50, self._center_on_master)

    def _center_on_master(self) -> None:
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        px = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, px)}+{max(0, py)}")

    def _status_text(self) -> str:
        n = len(self.selected)
        return f"{n} / {self.pick_count} selected"

    def _selection_display(self) -> str:
        if not self.selected:
            return "—"
        parts: list[str] = []
        for code in self.selected:
            rank, suit = code[0].upper(), code[1].lower()
            sym = next(s[0] for s in SUIT_COLUMNS if s[2] == suit)
            parts.append(f"{rank}{sym}")
        return "  ".join(parts)

    def _toggle(self, code: str) -> None:
        code = code.lower()
        if code in self.blocked:
            return
        if code in self.selected:
            self.selected.remove(code)
        elif len(self.selected) < self.pick_count:
            self.selected.append(code)
        self._refresh_buttons()

    def _clear(self) -> None:
        self.selected.clear()
        self._refresh_buttons()

    def _refresh_buttons(self) -> None:
        sel = {c.lower() for c in self.selected}
        for code, btn in self._buttons.items():
            sym_color = next(c[1] for c in SUIT_COLUMNS if c[2] == code[1])
            if code in self.blocked:
                btn.configure(
                    state="disabled",
                    fg_color="#1a1a1a",
                    border_width=0,
                    text_color="#4b5563",
                )
            elif code in sel:
                btn.configure(
                    state="normal",
                    fg_color="#374151",
                    border_width=2,
                    border_color="#fbbf24",
                    text_color=sym_color,
                )
            else:
                btn.configure(
                    state="normal",
                    fg_color="#2b2b2b",
                    border_width=0,
                    text_color=sym_color,
                )
        self._status_var.set(self._status_text())
        self._sel_label.configure(text=f"Picked: {self._selection_display()}")

    def _ok(self) -> None:
        if len(self.selected) != self.pick_count:
            self._status_var.set(f"Pick exactly {self.pick_count} cards")
            return
        self.on_confirm([c[0].upper() + c[1].lower() for c in self.selected])
        self.grab_release()
        self.destroy()


def open_card_picker(
    master: tk.Misc,
    *,
    title: str,
    pick_count: int,
    blocked: set[str] | None = None,
    initial_text: str = "",
    on_confirm: Callable[[str], None],
) -> None:
    """Open picker; ``on_confirm`` receives compact string (e.g. ``AsKh``)."""

    initial: list[str] = []
    if initial_text.strip():
        try:
            initial = compact_from_entry(initial_text, pick_count)
        except ValueError:
            initial = []

    def done(codes: list[str]) -> None:
        on_confirm(codes_to_compact(codes))

    CardPickerDialog(
        master,
        title=title,
        pick_count=pick_count,
        blocked=blocked,
        initial=initial,
        on_confirm=done,
    )
