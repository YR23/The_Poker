import json
from pathlib import Path
from typing import Optional, Tuple

import streamlit as st


POSITION_IMAGES = {
    "UTG": "DCIM/UTG.png",
    "MP": "DCIM/MP.png",
    "CO": "DCIM/CO.png",
    "BTN": "DCIM/BTN.png",
    "SB": "DCIM/SB.png",
}

RANKS = "AKQJT98765432"
SUITS = "DCHS"


@st.cache_data
def load_position_actions() -> dict[str, dict[str, str]]:
    actions: dict[str, dict[str, str]] = {}
    for config_path in sorted(Path("configs/positions").glob("*.json")):
        with config_path.open("r", encoding="ascii") as f:
            data = json.load(f)
        actions[data["position"]] = data["hand_actions"]
    return actions


def normalize_hand(raw_hand: str) -> Tuple[str, Optional[bool]]:
    cleaned = "".join(ch for ch in raw_hand.upper() if ch.isalnum())

    if len(cleaned) != 4:
        raise ValueError("Use format like AhKd, AsKs, or TdTc.")

    r1, s1, r2, s2 = cleaned[0], cleaned[1], cleaned[2], cleaned[3]
    if r1 not in RANKS or r2 not in RANKS:
        raise ValueError("Card ranks must be one of A,K,Q,J,T,9-2.")
    if s1 not in SUITS or s2 not in SUITS:
        raise ValueError("Card suits must be one of d, c, h, s.")
    if r1 == r2 and s1 == s2:
        raise ValueError("Cards must be different, e.g. AhAd instead of AhAh.")

    if r1 == r2:
        return r1 + r2, None

    if RANKS.index(r1) < RANKS.index(r2):
        high, low, high_suit, low_suit = r1, r2, s1, s2
    else:
        high, low, high_suit, low_suit = r2, r1, s2, s1

    is_suited = high_suit == low_suit
    suited_flag = "s" if is_suited else "o"

    return f"{high}{low}{suited_flag}", is_suited


def render_open_raise_expander(hand_input: str) -> None:
    with st.expander("open-raise", expanded=False):
        st.write("Click a position button to display its chart.")

        row_columns = st.columns(len(POSITION_IMAGES))
        for idx, position in enumerate(POSITION_IMAGES):
            if row_columns[idx].button(position, use_container_width=True):
                st.session_state["selected_position"] = position

        selected_position = st.session_state.get("selected_position", "UTG")
        image_path = POSITION_IMAGES[selected_position]
        position_actions = load_position_actions()

        st.subheader(f"Selected Position: {selected_position}")
        st.image(image_path, caption=f"{selected_position} chart", use_container_width=True)

        st.subheader("Action")
        if not hand_input.strip():
            st.info("Enter a hand above to see the action for the selected position.")
            st.session_state["normalized_hand"] = ""
            st.session_state["is_suited"] = None
        else:
            try:
                hand, is_suited = normalize_hand(hand_input)
                st.session_state["normalized_hand"] = hand
                st.session_state["is_suited"] = is_suited
                action = position_actions.get(selected_position, {}).get(hand, "fold")
                st.success(f"Hand {hand} -> {action.upper()}")
            except ValueError as exc:
                st.session_state["normalized_hand"] = ""
                st.session_state["is_suited"] = None
                st.warning(str(exc))
