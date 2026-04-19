import streamlit as st
import json
from pathlib import Path


POSITION_IMAGES = {
    "UTG": "DCIM/UTG.png",
    "MP": "DCIM/MP.png",
    "CO": "DCIM/CO.png",
    "BTN": "DCIM/BTN.png",
    "SB": "DCIM/SB.png",
}

RANKS = "AKQJT98765432"


@st.cache_data
def load_position_actions() -> dict[str, dict[str, str]]:
    actions: dict[str, dict[str, str]] = {}
    for config_path in sorted(Path("configs/positions").glob("*.json")):
        with config_path.open("r", encoding="ascii") as f:
            data = json.load(f)
        actions[data["position"]] = data["hand_actions"]
    return actions


def normalize_hand(raw_hand: str) -> str:
    cleaned = "".join(ch for ch in raw_hand.upper() if ch.isalnum())

    if len(cleaned) not in (2, 3):
        raise ValueError("Use format like AKs, AKo, or 99.")

    r1, r2 = cleaned[0], cleaned[1]
    if r1 not in RANKS or r2 not in RANKS:
        raise ValueError("Card ranks must be one of A,K,Q,J,T,9-2.")

    if r1 == r2:
        if len(cleaned) == 3:
            raise ValueError("Pocket pairs should be entered without s/o, e.g. 99.")
        return r1 + r2

    high, low = (r1, r2) if RANKS.index(r1) < RANKS.index(r2) else (r2, r1)

    if len(cleaned) != 3:
        raise ValueError("Non-pairs must end with s or o, e.g. AKs or AKo.")

    suited_flag = cleaned[2]
    if suited_flag not in ("S", "O"):
        raise ValueError("Use s for suited or o for offsuit.")

    return f"{high}{low}{suited_flag.lower()}"


def main() -> None:
    st.set_page_config(page_title="Poker Positions", layout="centered")
    st.title("Poker Position Charts")
    st.write("Click a position button to display its chart, then enter your hand.")

    row_columns = st.columns([1, 1, 1, 1, 1, 2])
    for idx, position in enumerate(POSITION_IMAGES):
        if row_columns[idx].button(position, use_container_width=True):
            st.session_state["selected_position"] = position

    with row_columns[-1]:
        hand_input = st.text_input(
            "",
            value=st.session_state.get("hand_input", ""),
            placeholder="AKs / AKo / 99",
            label_visibility="collapsed",
        )
    st.session_state["hand_input"] = hand_input

    selected_position = st.session_state.get("selected_position", "UTG")
    image_path = POSITION_IMAGES[selected_position]
    position_actions = load_position_actions()

    st.subheader(f"Selected Position: {selected_position}")
    st.image(image_path, caption=f"{selected_position} chart", use_container_width=True)

    st.subheader("Action")
    if not hand_input.strip():
        st.info("Enter a hand to see the action for the selected position.")
    else:
        try:
            hand = normalize_hand(hand_input)
            action = position_actions.get(selected_position, {}).get(hand, "fold")
            st.success(f"Hand {hand} -> {action.upper()}")
        except ValueError as exc:
            st.warning(str(exc))


if __name__ == "__main__":
    main()
