import streamlit as st
from cold_call_section import render_cold_call_expander
from iso_raise_section import render_iso_raise_expander
from open_raise_section import render_open_raise_expander
from over_call_section import render_over_call_expander
from defend_three_bet_section import render_defend_three_bet_expander
from squeeze_section import render_squeeze_expander
from three_bet_section import render_three_bet_expander


PLAYER_FIELDS = ["name", "vpip", "pfr", "cbet", "fold_to_cbet", "three_bet", "fold_to_three_bet"]


def _init_player_state() -> None:
    if "players" not in st.session_state:
        st.session_state["players"] = []

    if st.session_state.get("reset_player_draft", False):
        for field in PLAYER_FIELDS:
            st.session_state[f"player_draft_{field}"] = ""
        st.session_state["reset_player_draft"] = False

    for field in PLAYER_FIELDS:
        key = f"player_draft_{field}"
        if key not in st.session_state:
            st.session_state[key] = ""


def render_players_section() -> None:
    _init_player_state()

    st.subheader("Players")

    headers = ["Name", "VPIP", "PFR", "CBET", "FoldToCbet", "3BET", "Foldto3bet", ""]
    header_cols = st.columns([2.2, 1, 1, 1, 1.2, 1, 1.2, 1])
    for idx, title in enumerate(headers):
        with header_cols[idx]:
            if title:
                st.caption(title)

    input_cols = st.columns([2.2, 1, 1, 1, 1.2, 1, 1.2, 1])
    field_keys = [
        "player_draft_name",
        "player_draft_vpip",
        "player_draft_pfr",
        "player_draft_cbet",
        "player_draft_fold_to_cbet",
        "player_draft_three_bet",
        "player_draft_fold_to_three_bet",
    ]

    for idx, key in enumerate(field_keys):
        with input_cols[idx]:
            st.text_input("", key=key, label_visibility="collapsed")

    with input_cols[7]:
        if st.button("Add", key="add_player_button", use_container_width=True):
            new_player = {
                "name": st.session_state["player_draft_name"].strip(),
                "vpip": st.session_state["player_draft_vpip"].strip(),
                "pfr": st.session_state["player_draft_pfr"].strip(),
                "cbet": st.session_state["player_draft_cbet"].strip(),
                "fold_to_cbet": st.session_state["player_draft_fold_to_cbet"].strip(),
                "three_bet": st.session_state["player_draft_three_bet"].strip(),
                "fold_to_three_bet": st.session_state["player_draft_fold_to_three_bet"].strip(),
            }

            if not new_player["name"]:
                st.warning("Player name is required.")
            else:
                st.session_state["players"].append(new_player)
                st.session_state["reset_player_draft"] = True
                st.rerun()

    for idx, player in enumerate(st.session_state["players"]):
        row_cols = st.columns([2.2, 1, 1, 1, 1.2, 1, 1.2, 1])
        values = [
            player["name"],
            player["vpip"],
            player["pfr"],
            player["cbet"],
            player["fold_to_cbet"],
            player["three_bet"],
            player["fold_to_three_bet"],
        ]
        for col_idx, value in enumerate(values):
            with row_cols[col_idx]:
                st.write(value)
        with row_cols[7]:
            if st.button("Remove", key=f"remove_player_{idx}", use_container_width=True):
                st.session_state["players"].pop(idx)
                st.rerun()

    st.divider()


def main() -> None:
    st.set_page_config(page_title="Poker Positions", layout="centered")
    st.title("Poker Position Charts")

    render_players_section()

    if "selected_hand_input" not in st.session_state:
        st.session_state["selected_hand_input"] = st.session_state.get("hand_input", "")
    if "hand_input_draft" not in st.session_state:
        st.session_state["hand_input_draft"] = st.session_state["selected_hand_input"]

    hand_col, select_col = st.columns([5, 1])
    with hand_col:
        st.text_input(
            "",
            key="hand_input_draft",
            placeholder="AhKd / AsKs / TdTc",
            label_visibility="collapsed",
        )
    with select_col:
        if st.button("Select hand", use_container_width=True):
            st.session_state["selected_hand_input"] = st.session_state["hand_input_draft"]
            st.session_state["hand_input"] = st.session_state["selected_hand_input"]

    selected_hand_input = st.session_state["selected_hand_input"]
    if selected_hand_input.strip():
        st.caption(f"Selected hand: {selected_hand_input}")
    else:
        st.caption("Selected hand: none")

    st.subheader("Pre-flop")

    render_open_raise_expander(selected_hand_input)
    render_three_bet_expander(selected_hand_input)
    render_squeeze_expander(selected_hand_input)
    render_over_call_expander(selected_hand_input)
    render_cold_call_expander(selected_hand_input)
    render_iso_raise_expander(selected_hand_input)
    render_defend_three_bet_expander()


if __name__ == "__main__":
    main()
