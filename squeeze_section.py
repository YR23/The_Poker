from pathlib import Path

import streamlit as st

from open_raise_section import normalize_hand


SQUEEZE_IMAGE_PATH = Path("DCIM/squeezing/ranges.png")
POSITIONS = ["UTG", "MP", "CO", "BTN"]


def _build_squeeze_defaults() -> dict[str, dict[str, set[str]]]:
    return {
        "UTG": {
            "default": {"AA", "KK", "AKs"},
            "optional": {"AKo", "QQ"},
        },
        "MP": {
            "default": {"AA", "KK", "QQ", "AKs"},
            "optional": {"JJ", "AKo", "AQs"},
        },
        "CO": {
            "default": {
                "AA", "KK", "QQ", "JJ",
                "AKs", "AQs", "AJs",
                "AKo", "AQo",
            },
            "optional": {"AJo", "ATs", "KQs"},
        },
        "BTN": {
            "default": {
                "AA", "KK", "QQ", "JJ",
                "AKs", "AQs", "AJs",
                "AKo", "AQo",
            },
            "optional": {"AJo", "ATs", "KQs"},
        },
    }


SQUEEZE_RANGES = _build_squeeze_defaults()


def render_squeeze_expander(hand_input: str) -> None:
    with st.expander("Squeezing", expanded=False):
        st.write("Choose the opener position to evaluate whether your hand is in the squeeze value range.")

        row_columns = st.columns(len(POSITIONS))
        for idx, position in enumerate(POSITIONS):
            if row_columns[idx].button(f"vs {position}", key=f"squeeze_vs_{position}", use_container_width=True):
                st.session_state["squeeze_vs_position"] = position

        opener_position = st.session_state.get("squeeze_vs_position", "UTG")
        ranges = SQUEEZE_RANGES[opener_position]

        st.subheader(f"Versus: {opener_position} Open-Raise")

        if not hand_input.strip():
            st.info("Enter a hand above to evaluate the squeeze range.")
            st.session_state["squeeze_hand"] = ""
            st.session_state["squeeze_decision"] = ""
        else:
            try:
                hand, _ = normalize_hand(hand_input)
                st.session_state["squeeze_hand"] = hand

                if hand in ranges["default"]:
                    st.session_state["squeeze_decision"] = "default"
                    st.success(f"Hand {hand} -> SQUEEZE VALUE")
                elif hand in ranges["optional"]:
                    st.session_state["squeeze_decision"] = "optional"
                    st.info(f"Hand {hand} -> OPTIONAL SQUEEZE")
                else:
                    st.session_state["squeeze_decision"] = "none"
                    st.warning(f"Hand {hand} -> Not in squeeze value range")
            except ValueError as exc:
                st.session_state["squeeze_hand"] = ""
                st.session_state["squeeze_decision"] = ""
                st.warning(str(exc))

        if SQUEEZE_IMAGE_PATH.exists():
            st.image(str(SQUEEZE_IMAGE_PATH), caption="Squeezing chart", use_container_width=True)
        else:
            st.info("Add DCIM/squeezing/ranges.png to display the squeezing chart image here.")

        st.subheader("Range Summary")
        if opener_position == "UTG":
            st.write("Default: AA-KK, AKs")
            st.write("Optional: AKo, QQ")
        elif opener_position == "MP":
            st.write("Default: AA-QQ, AKs")
            st.write("Optional: JJ, AKo, AQs")
        else:
            st.write("Default: AA-JJ, AQ+, AJs")
            st.write("Optional: AJo, ATs, KQs")

        st.subheader("Sizing")
        st.write("Out of Position: 3.5x open-raise sizing + 3bb per caller")
        st.write("In Position: 3x open-raise sizing + 3bb per caller")
