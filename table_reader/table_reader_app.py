import subprocess
import sys
from pathlib import Path

import streamlit as st

# Add table_reader directory to path so reader_utils can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent))
from reader_utils import (
    assign_table_positions,
    extract_player_sections,
    extract_player_text,
    organize_player_sections,
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
        organize_player_sections(PLAYERS_DIR, positions=ALL_POSITIONS)

    results = {}
    for position in ALL_POSITIONS:
        result = extract_player_text(PLAYERS_DIR, position)
        results[position] = result

    st.session_state["position_warning"] = assign_table_positions(results)
    st.session_state["results"] = results

if MAIN_RIGHT_IMAGE.exists():
    st.subheader("Captured Main Right")
    st.image(str(MAIN_RIGHT_IMAGE), use_container_width=True)

if "results" in st.session_state:
    results = st.session_state["results"]

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
        action_img = PLAYERS_DIR / position / "action.png"
        if action_img.exists():
            st.image(str(action_img), width=120)

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
