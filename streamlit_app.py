import streamlit as st
from open_raise_section import render_open_raise_expander
from three_bet_section import render_three_bet_expander


def main() -> None:
    st.set_page_config(page_title="Poker Positions", layout="centered")
    st.title("Poker Position Charts")

    hand_input = st.text_input(
        "",
        value=st.session_state.get("hand_input", ""),
        placeholder="AhKd / AsKs / TdTc",
        label_visibility="collapsed",
    )
    st.session_state["hand_input"] = hand_input

    render_open_raise_expander(hand_input)
    render_three_bet_expander(hand_input)


if __name__ == "__main__":
    main()
