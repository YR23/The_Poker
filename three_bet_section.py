import streamlit as st

from open_raise_section import normalize_hand


POSITIONS = ["UTG", "MP", "CO", "BTN", "SB"]


def _build_three_bet_defaults() -> dict[str, set[str]]:
    return {
        # Default: AA-KK, AKs
        "UTG": {"AA", "KK", "AKs"},
        # Default: AA-QQ, AKs
        "MP": {"AA", "KK", "QQ", "AKs"},
        # Default: AA-JJ, AQ+, AJs
        "CO": {
            "AA", "KK", "QQ", "JJ",
            "AKs", "AQs", "AJs",
            "AKo", "AQo",
        },
        # Default: AA-JJ, AQ+, AJs
        "BTN": {
            "AA", "KK", "QQ", "JJ",
            "AKs", "AQs", "AJs",
            "AKo", "AQo",
        },
        # Default: AA-TT, AJ+
        "SB": {
            "AA", "KK", "QQ", "JJ", "TT",
            "AKs", "AQs", "AJs",
            "AKo", "AQo", "AJo",
        },
    }


THREE_BET_DEFAULTS = _build_three_bet_defaults()

# Blue bluff candidates from the shared 3-bet chart.
THREE_BET_BLUFFS = {
    # Suited aces
    "A5s", "A4s", "A3s", "A2s",
    # Small pocket pairs
    "55", "44", "33", "22",
    # Suited connectors
    "T9s", "98s", "87s", "76s", "65s",
}


def render_three_bet_expander(hand_input: str) -> None:
    with st.expander("3-bet", expanded=False):
        st.write("Choose villain open-raise position. Returns 3-bet value or 3-bet bluff.")

        row_columns = st.columns(len(POSITIONS))
        for idx, position in enumerate(POSITIONS):
            if row_columns[idx].button(f"vs {position}", key=f"three_bet_vs_{position}", use_container_width=True):
                st.session_state["three_bet_vs_position"] = position

        versus_position = st.session_state.get("three_bet_vs_position", "UTG")
        st.subheader(f"Versus: {versus_position} Open-Raise")

        if not hand_input.strip():
            st.info("Enter a hand above to evaluate 3-bet value/bluff.")
            st.session_state["three_bet_hand"] = ""
            st.session_state["three_bet_is_suited"] = None
            st.session_state["three_bet_decision"] = ""
            return

        try:
            hand, is_suited = normalize_hand(hand_input)
            st.session_state["three_bet_hand"] = hand
            st.session_state["three_bet_is_suited"] = is_suited

            if hand in THREE_BET_DEFAULTS[versus_position]:
                st.session_state["three_bet_decision"] = "value"
                st.success(f"Hand {hand} -> 3-BET VALUE")
            elif hand in THREE_BET_BLUFFS:
                st.session_state["three_bet_decision"] = "bluff"
                st.info(f"Hand {hand} -> 3-BET BLUFF")
            else:
                st.session_state["three_bet_decision"] = "none"
                st.warning(f"Hand {hand} -> Not in 3-bet value/bluff range")
        except ValueError as exc:
            st.session_state["three_bet_hand"] = ""
            st.session_state["three_bet_is_suited"] = None
            st.session_state["three_bet_decision"] = ""
            st.warning(str(exc))
