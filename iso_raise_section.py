from pathlib import Path

import streamlit as st

from open_raise_section import normalize_hand


ISO_RAISE_IMAGE_PATH = Path("DCIM/iso_raising/ranges.png")


def _pair_range(high_pair: str, low_pair: str) -> set[str]:
    ranks = "AKQJT98765432"
    start_idx = ranks.index(high_pair)
    end_idx = ranks.index(low_pair)
    return {ranks[idx] * 2 for idx in range(start_idx, end_idx + 1)}


DEFAULT_ISO_RAISE_HANDS = (
    _pair_range("A", "8")
    | {"AKs", "AQs", "AJs", "KQs", "KJs", "QJs", "AKo", "AQo", "AJo", "KQo", "KJo"}
)


def render_iso_raise_expander(hand_input: str) -> None:
    with st.expander("Iso-raising", expanded=False):
        st.write("Use this when facing limpers and deciding whether to isolate-raise.")

        if not hand_input.strip():
            st.info("Enter a hand above to evaluate whether it is in the default iso-raising range.")
            st.session_state["iso_raise_hand"] = ""
            st.session_state["iso_raise_decision"] = ""
        else:
            try:
                hand, _ = normalize_hand(hand_input)
                st.session_state["iso_raise_hand"] = hand

                if hand in DEFAULT_ISO_RAISE_HANDS:
                    st.session_state["iso_raise_decision"] = "raise"
                    st.success(f"Hand {hand} -> ISO-RAISE")
                else:
                    st.session_state["iso_raise_decision"] = "no_raise"
                    st.warning(f"Hand {hand} -> Not in default iso-raising range")
            except ValueError as exc:
                st.session_state["iso_raise_hand"] = ""
                st.session_state["iso_raise_decision"] = ""
                st.warning(str(exc))

        if ISO_RAISE_IMAGE_PATH.exists():
            st.image(str(ISO_RAISE_IMAGE_PATH), caption="Iso-raising chart", use_container_width=True)
        else:
            st.info("Add DCIM/iso_raising/ranges.png to display the iso-raising chart image here.")

        st.subheader("Range")
        st.write("Default iso-raising range: 88+, AJs+, KJs+, QJs, AJo+, KJo+.")
        st.write("Optional/over-limp hands are the light cells on the chart and are not used in the raise/fold decision below.")

        st.subheader("Player Type Notes")
        st.write("Weak tight: VPIP / PFR about 15/6.")
        st.write("Weak loose: VPIP / PFR about 40/5.")

        st.subheader("Sizing")
        st.write("In Position: 3bb + 1bb per limper")
        st.write("Out of position: 3bb + 1bb + 1bb per limper")
