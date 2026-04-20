from pathlib import Path

import streamlit as st

from open_raise_section import normalize_hand


OVER_CALL_IMAGE_PATH = Path("DCIM/over_calling/ranges.png")

# Dark cells in the chart.
OVER_CALL_HANDS = {
    "A5s", "A4s", "A3s", "A2s",
    "KJs", "KTs",
    "QJs", "QTs",
    "JTs", "J9s",
    "T9s", "T8s",
    "98s", "87s", "76s",
    "99", "88", "77", "66", "55",
}


def render_over_call_expander(hand_input: str) -> None:
    with st.expander("Over-calling", expanded=False):
        st.write("Evaluate your hand against the over-calling range.")

        if not hand_input.strip():
            st.info("Enter a hand above to evaluate over-calling.")
            st.session_state["over_call_hand"] = ""
            st.session_state["over_call_decision"] = ""
        else:
            try:
                hand, _ = normalize_hand(hand_input)
                st.session_state["over_call_hand"] = hand

                if hand in OVER_CALL_HANDS:
                    st.session_state["over_call_decision"] = "over_call"
                    st.success("OVER-CALL")
                else:
                    st.session_state["over_call_decision"] = "fold"
                    st.warning("NOT AN OVER-CALL")
            except ValueError as exc:
                st.session_state["over_call_hand"] = ""
                st.session_state["over_call_decision"] = ""
                st.warning(str(exc))

        if OVER_CALL_IMAGE_PATH.exists():
            st.image(str(OVER_CALL_IMAGE_PATH), caption="Over-calling chart", use_container_width=True)
        else:
            st.info("Add DCIM/over_calling/ranges.png to display the over-calling chart image here.")
