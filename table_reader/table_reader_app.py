import subprocess
import sys
from pathlib import Path

import streamlit as st

# Add table_reader directory to path so reader_utils can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent))
from reader_utils import (
    assign_table_positions,
    extract_player_sections,
    process_positions_parallel,
)

DCIM_DIR = Path(__file__).resolve().parent / "DCIM"
PLAYERS_DIR = DCIM_DIR / "players"
SCREEN_IMAGE = DCIM_DIR / "screen.png"
MAIN_RIGHT_IMAGE = DCIM_DIR / "main_right.png"
ALL_POSITIONS = [
    "top_left", "top_middle", "top_right",
    "bottom_left", "bottom_middle", "bottom_right",
]

st.set_page_config(page_title="Table Reader", layout="wide")
st.title("Poker Table Reader")

if st.button("📸 Capture & Analyze Table", use_container_width=True):
    with st.spinner("Capturing screenshot..."):
        from reader_utils import capture_screen
        capture_screen(SCREEN_IMAGE, display_index=2)

    with st.spinner("Processing table..."):
        extract_player_sections(DCIM_DIR)
        results = process_positions_parallel(PLAYERS_DIR, ALL_POSITIONS, max_workers=6)

    st.session_state["position_warning"] = assign_table_positions(results)
    st.session_state["results"] = results


if "results" in st.session_state:
    results = st.session_state["results"]

    # ── Hero hand confirmation ────────────────────────────────────────────
    st.subheader("🃏 Your Hand")

    hero = results.get("bottom_middle", {})
    detected_left_rank  = hero.get("hero_card_left", "")
    detected_left_color  = hero.get("hero_card_left_color", "")
    detected_right_rank = hero.get("hero_card_right", "")
    detected_right_color = hero.get("hero_card_right_color", "")
    detected_hand = hero.get("hand_rank", "")

    RANKS  = ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]
    COLORS = ["red", "green", "blue", "black"]

    def _safe_index(lst, val, fallback=0):
        try:
            return lst.index(val)
        except ValueError:
            return fallback

    # Seed session state with detected values so dropdowns reflect the detection.
    # Always update when a fresh capture produces new results.
    last_detected = st.session_state.get("_last_detected_hand", "")
    if detected_hand != last_detected:
        st.session_state["hero_left_rank"]  = detected_left_rank  or RANKS[0]
        st.session_state["hero_left_color"] = detected_left_color or COLORS[0]
        st.session_state["hero_right_rank"] = detected_right_rank or RANKS[0]
        st.session_state["hero_right_color"]= detected_right_color or COLORS[0]
        st.session_state["_last_detected_hand"] = detected_hand

    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 2])
    with col1:
        left_rank = st.selectbox(
            "Left rank",
            options=RANKS,
            index=_safe_index(RANKS, st.session_state["hero_left_rank"]),
            key="hero_left_rank",
        )
    with col2:
        left_color = st.selectbox(
            "Left color",
            options=COLORS,
            index=_safe_index(COLORS, st.session_state["hero_left_color"]),
            key="hero_left_color",
        )
    with col3:
        right_rank = st.selectbox(
            "Right rank",
            options=RANKS,
            index=_safe_index(RANKS, st.session_state["hero_right_rank"]),
            key="hero_right_rank",
        )
    with col4:
        right_color = st.selectbox(
            "Right color",
            options=COLORS,
            index=_safe_index(COLORS, st.session_state["hero_right_color"]),
            key="hero_right_color",
        )
    with col5:
        st.write("&nbsp;", unsafe_allow_html=True)  # vertical spacer to align button
        confirm_clicked = st.button("✅ Confirm Hand", use_container_width=True)

    if confirm_clicked:
        # Rebuild hand notation from the (possibly corrected) dropdowns
        from reader_utils import build_preflop_hand_rank
        confirmed = build_preflop_hand_rank(left_rank, right_rank, left_color, right_color)
        st.session_state["confirmed_hand"] = confirmed
        st.session_state["confirmed_hand_parts"] = {
            "left_rank": left_rank, "left_color": left_color,
            "right_rank": right_rank, "right_color": right_color,
        }
        st.rerun()

    if st.session_state.get("confirmed_hand"):
        st.success(f"Confirmed hand: **{st.session_state['confirmed_hand']}**")

    st.divider()
    st.subheader("Results")

    if st.session_state.get("position_warning"):
        st.warning(st.session_state["position_warning"])

    def player_card(position: str) -> None:
        data = results.get(position, {})
        st.markdown(f"**{position.replace('_', ' ').title()}**")
        st.write(f"📍 `{data.get('table_position', '') or '—'}`")
        if data.get("is_dealer", False):
            st.caption("🟠 Dealer")
        st.write(f"🧑 `{data.get('name', '') or '—'}`")
        st.write(f"💰 `{data.get('pot_size', '') or '—'}`")
        st.write(f"🃏 `{data.get('action', '') or '—'}`")

    # Row 1: top_middle in center
    r1 = st.columns(3)
    with r1[1]:
        player_card("top_middle")

    # Row 2: top_left and top_right on sides
    r2 = st.columns(3)
    with r2[0]:
        player_card("top_left")
    with r2[2]:
        player_card("top_right")

    # Row 3: bottom_left and bottom_right on sides
    r3 = st.columns(3)
    with r3[0]:
        player_card("bottom_left")
    with r3[2]:
        player_card("bottom_right")

    # Row 4: bottom_middle in center
    r4 = st.columns(3)
    with r4[1]:
        player_card("bottom_middle")
