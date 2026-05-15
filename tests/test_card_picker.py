"""Tests for card_picker helpers."""

from __future__ import annotations

from card_picker import codes_to_compact, compact_from_entry


def test_codes_to_compact() -> None:
    assert codes_to_compact(["As", "Kh"]) == "AsKh"


def test_compact_from_entry_roundtrip() -> None:
    codes = compact_from_entry("AsKh", 2)
    assert codes_to_compact(codes) == "AsKh"
