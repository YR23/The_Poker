import streamlit as st
from typing import Optional
from pathlib import Path
import json
from typing import Any, Dict, List, Tuple
import streamlit.components.v1 as components

from cold_call_section import COLD_CALL_CHARTS
from iso_raise_section import DEFAULT_ISO_RAISE_HANDS
from over_call_section import OVER_CALL_HANDS
from squeeze_section import SQUEEZE_RANGES
from three_bet_section import THREE_BET_BLUFFS, THREE_BET_DEFAULTS


st.set_page_config(page_title="YR Poker", page_icon="♦️", layout="wide")


CARD_ORDER = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
COLOR_ORDER = ["black", "red", "blue", "green"]
COLOR_BUTTON_EMOJI = {
    "black": "⚫",
    "red": "🔴",
    "blue": "🔵",
    "green": "🟢",
}
POSITIONS = ["UTG", "MP", "CO", "BTN", "SB", "BB"]
POSITION_DISTANCE_FROM_BUTTON = {
    "UTG": -3,
    "MP": -2,
    "CO": -1,
    "BTN": 0,
    "SB": 1,
    "BB": 2,
}
CARD_STRENGTH = {rank: idx for idx, rank in enumerate(CARD_ORDER)}
CM_PLOTS_DIR = Path("cm_plots")
PLAYS_JSON_PATH = Path("plays/plays.json")
RFI_CONFIGS_DIR = Path("configs/positions")

SET_MINING_HANDS = {"22", "33", "44", "55", "66", "77", "88", "99"}
STEAL_POSITIONS = {"CO", "BTN", "SB"}

# Maps play name -> PNG path (None = no chart, or uses position for RFI)
PLAY_PNG_MAP: Dict[str, Optional[Path]] = {
    "Raising First In": None,  # position-specific: DCIM/open-raise/{position}.png
    "3-Bet": Path("DCIM/3-bet/ranges.png"),
    "4-Bet": Path("DCIM/3-bet/ranges.png"),
    "Cold Call": None,
    "Set Mining": None,
    "Isolation Raise": Path("DCIM/iso_raising/ranges.png"),
    "Overcall": Path("DCIM/over_calling/ranges.png"),
    "Squeeze": Path("DCIM/squeezing/ranges.png"),
    "Steal": None,
    "Defending the Blinds": Path("DCIM/defence_steal/defence.png"),
}


def _init_state() -> None:
    if "selected_by_row" not in st.session_state:
        st.session_state["selected_by_row"] = {}
    if "selected_position" not in st.session_state:
        st.session_state["selected_position"] = ""
    if "players" not in st.session_state:
        st.session_state["players"] = []
    # Keep Pyrex present as a default player profile.
    if not any(str(player.get("Name", "")).strip().lower() == "pyrex" for player in st.session_state["players"]):
        st.session_state["players"].append(
            {
                "Name": "Pyrex",
                "VPIP": 0,
                "PFR": 0,
                "3-BET": 0,
                "Fold to 3-Bet": 0,
                "C-BET": 0,
                "Fold to C-Bet": 0,
                "Steal": 0,
                "Check/Raise": 0,
                "Pre Flop Action": "",
                "Position": POSITIONS[0],
            }
        )
    if "editing_player_index" not in st.session_state:
        st.session_state["editing_player_index"] = None
    if "pending_edit_player_index" not in st.session_state:
        st.session_state["pending_edit_player_index"] = None
    if "player_name_input" not in st.session_state:
        st.session_state["player_name_input"] = ""
    if "player_vpip_input" not in st.session_state:
        st.session_state["player_vpip_input"] = 0
    if "player_pfr_input" not in st.session_state:
        st.session_state["player_pfr_input"] = 0
    if "player_three_bet_input" not in st.session_state:
        st.session_state["player_three_bet_input"] = 0
    if "player_fold_to_three_bet_input" not in st.session_state:
        st.session_state["player_fold_to_three_bet_input"] = 0
    if "player_cbet_input" not in st.session_state:
        st.session_state["player_cbet_input"] = 0
    if "player_fold_to_cbet_input" not in st.session_state:
        st.session_state["player_fold_to_cbet_input"] = 0
    if "player_steal_input" not in st.session_state:
        st.session_state["player_steal_input"] = 0
    if "player_check_raise_input" not in st.session_state:
        st.session_state["player_check_raise_input"] = 0
    if "pending_player_form_reset" not in st.session_state:
        st.session_state["pending_player_form_reset"] = False
    if "player_flash_message" not in st.session_state:
        st.session_state["player_flash_message"] = ""


@st.cache_data
def _load_plays() -> List[Dict[str, Any]]:
    with PLAYS_JSON_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def _load_rfi_actions() -> Dict[str, Dict[str, str]]:
    actions: Dict[str, Dict[str, str]] = {}
    for config_path in sorted(RFI_CONFIGS_DIR.glob("*.json")):
        with config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        actions[data["position"]] = data["hand_actions"]
    return actions


def _evaluate_play(play_name: str, hand: str, position: str) -> Tuple[Optional[bool], str]:
    rfi_actions = _load_rfi_actions()

    if play_name == "Raising First In":
        if position not in rfi_actions:
            return None, f"No RFI chart configured for {position}."
        is_possible = rfi_actions[position].get(hand) == "raise"
        return is_possible, "In RFI raise range." if is_possible else "Not in RFI raise range."

    if play_name == "3-Bet":
        if position not in THREE_BET_DEFAULTS:
            return None, f"No 3-bet chart configured for {position}."
        is_possible = hand in THREE_BET_DEFAULTS[position] or hand in THREE_BET_BLUFFS
        return is_possible, "In 3-bet value/bluff range." if is_possible else "Not in 3-bet value/bluff range."

    if play_name == "4-Bet":
        if position not in THREE_BET_DEFAULTS:
            return None, f"No 4-bet chart configured for {position}."
        is_possible = hand in THREE_BET_DEFAULTS[position] or hand in THREE_BET_BLUFFS
        return is_possible, "In 4-bet value/bluff range." if is_possible else "Not in 4-bet value/bluff range."

    if play_name == "Cold Call":
        if position not in COLD_CALL_CHARTS:
            return None, f"No cold-call chart configured for {position}."
        cold_call = COLD_CALL_CHARTS[position]["cold_call"]
        is_possible = hand in cold_call
        return is_possible, "In cold-call range." if is_possible else "Not in cold-call range."

    if play_name == "Set Mining":
        is_possible = hand in SET_MINING_HANDS
        return is_possible, "Small pocket pair for set mining." if is_possible else "Not a set-mining pocket pair."

    if play_name == "Isolation Raise":
        is_possible = hand in DEFAULT_ISO_RAISE_HANDS
        return is_possible, "In iso-raise range." if is_possible else "Not in iso-raise range."

    if play_name == "Overcall":
        is_possible = hand in OVER_CALL_HANDS
        return is_possible, "In overcall range." if is_possible else "Not in overcall range."

    if play_name == "Squeeze":
        if position not in SQUEEZE_RANGES:
            return None, f"No squeeze chart configured for {position}."
        ranges = SQUEEZE_RANGES[position]
        is_possible = hand in ranges["default"] or hand in ranges["optional"]
        return is_possible, "In squeeze range (default/optional)." if is_possible else "Not in squeeze range."

    if play_name == "Steal":
        if position not in rfi_actions:
            return None, f"No RFI chart configured for {position}."
        if position not in STEAL_POSITIONS:
            return False, "Steal considered only from CO/BTN/SB."
        is_possible = rfi_actions[position].get(hand) == "raise"
        return is_possible, "In steal/open range from late position." if is_possible else "Not in late-position steal range."

    if play_name == "Defending the Blinds":
        return None, "Range not defined in current project."

    return None, "Unknown play mapping."


def _status_rank(possible: Optional[bool]) -> int:
    if possible is True:
        return 0
    if possible is None:
        return 1
    return 2


def _status_meta(possible: Optional[bool]) -> Tuple[str, str]:
    if possible is True:
        return "Possible", "check_circle"
    if possible is None:
        return "No range", "help"
    return "Not possible", "cancel"


def _status_color_marker(possible: Optional[bool]) -> str:
    if possible is True:
        return "🟢"
    if possible is None:
        return "🟡"
    return "🔴"


def _render_plays_matrix(hand: Optional[str], position: str) -> None:
    st.subheader("Plays")

    st.markdown(
        """
<style>
.material-symbols-rounded {
  font-family: 'Material Symbols Rounded';
  font-variation-settings:
  'FILL' 0,
  'wght' 400,
  'GRAD' 0,
  'opsz' 24
}
</style>
        """,
        unsafe_allow_html=True,
    )

    plays = _load_plays()
    evaluated: List[Tuple[Dict[str, Any], Optional[bool], str]] = []
    for play in plays:
        if hand is None or not position:
            possible, reason = (None, "Select full hand and position to evaluate this play.")
        else:
            possible, reason = _evaluate_play(play["name"], hand, position)
        evaluated.append((play, possible, reason))

    evaluated.sort(key=lambda item: _status_rank(item[1]))

    play_idx = 0
    for _ in range(3):
        cols = st.columns(4, gap="small")
        for col in cols:
            if play_idx >= len(evaluated):
                continue

            play, possible, reason = evaluated[play_idx]
            play_idx += 1

            with col:
                other_names = play.get("other_names", [])
                if other_names:
                    title = f"{play['name']} ({', '.join(other_names)})"
                else:
                    title = play["name"]

                color_marker = _status_color_marker(possible)
                expander_title = f"{color_marker} {title}"

                with st.expander(expander_title, expanded=False):
                    st.write(play["description"])
                    st.caption(reason)


def _render_pre_flop_players_actions() -> None:
    players = st.session_state["players"]

    if not players:
        st.caption("Add a player below to manage pre-flop actions here.")
        return

    position_rank = {pos: i for i, pos in enumerate(POSITIONS)}
    ordered_indices = sorted(
        range(len(players)),
        key=lambda i: (
            position_rank.get(players[i].get("Position", POSITIONS[0]), len(POSITIONS)),
            str(players[i].get("Name", "")).lower(),
        ),
    )

    # Keep dropdown widget state aligned with each player's true saved position.
    for idx, player in enumerate(players):
        key = f"preflop_player_position_{idx}"
        true_position = player.get("Position", POSITIONS[0])
        if true_position not in POSITIONS:
            true_position = POSITIONS[0]
            players[idx]["Position"] = true_position
        if st.session_state.get(key) != true_position:
            st.session_state[key] = true_position

    player_cols = st.columns(len(players), gap="small")
    for col_idx, idx in enumerate(ordered_indices):
        player = players[idx]
        with player_cols[col_idx]:
            current_action = player.get("Pre Flop Action", "")
            st.markdown(f"<p style='text-align:center; font-weight:600;'>{player['Name']}</p>", unsafe_allow_html=True)

            if st.button(
                "🔴 Fold",
                key=f"preflop_action_fold_{idx}",
                use_container_width=True,
                type="primary" if current_action == "Fold" else "secondary",
            ):
                players[idx]["Pre Flop Action"] = "Fold"
                st.rerun()

            if st.button(
                "🔵 Call",
                key=f"preflop_action_call_{idx}",
                use_container_width=True,
                type="primary" if current_action == "Call" else "secondary",
            ):
                players[idx]["Pre Flop Action"] = "Call"
                st.rerun()

            if st.button(
                "🟢 Raise",
                key=f"preflop_action_raise_{idx}",
                use_container_width=True,
                type="primary" if current_action == "Raise" else "secondary",
            ):
                players[idx]["Pre Flop Action"] = "Raise"
                st.rerun()

            current_position = player.get("Position", POSITIONS[0])
            if current_position not in POSITIONS:
                current_position = POSITIONS[0]
            selected_position = st.selectbox(
                "Position",
                POSITIONS,
                index=POSITIONS.index(current_position),
                key=f"preflop_player_position_{idx}",
            )
            if selected_position != current_position:
                players[idx]["Position"] = selected_position
                st.rerun()


def _build_hand_notation() -> Optional[str]:
    selected = st.session_state.get("selected_by_row", {})
    card_1 = selected.get(1)
    suit_1 = selected.get(2)
    card_2 = selected.get(3)
    suit_2 = selected.get(4)

    if not all([card_1, suit_1, card_2, suit_2]):
        return None

    if card_1 == card_2:
        return f"{card_1}{card_2}"

    if CARD_STRENGTH[card_1] > CARD_STRENGTH[card_2]:
        high_card, low_card = card_1, card_2
    else:
        high_card, low_card = card_2, card_1

    suited_flag = "s" if suit_1 == suit_2 else "o"
    return f"{high_card}{low_card}{suited_flag}"


def _rotate_players_positions_next_hand() -> None:
    players = st.session_state["players"]
    if not players:
        return

    next_position = {
        "UTG": "MP",
        "MP": "CO",
        "CO": "BTN",
        "BTN": "SB",
        "SB": "BB",
        "BB": "UTG",
    }

    for player in players:
        current = player.get("Position", "UTG")
        player["Position"] = next_position.get(current, "UTG")


def _get_pyrex_position() -> str:
    for player in st.session_state["players"]:
        if str(player.get("Name", "")).strip().lower() == "pyrex":
            position = player.get("Position", POSITIONS[0])
            return position if position in POSITIONS else POSITIONS[0]
    return POSITIONS[0]


def _row_picker(row_id: int, names: list[str]) -> None:
    cols = st.columns(len(names), gap="small")
    selected_name = st.session_state["selected_by_row"].get(row_id)

    for idx, name in enumerate(names):
        with cols[idx]:
            button_type = "primary" if name == selected_name else "secondary"
            label = f"{COLOR_BUTTON_EMOJI[name]} {name.title()}" if name in COLOR_BUTTON_EMOJI else name
            if st.button(
                label,
                key=f"row_{row_id}_item_{name}",
                use_container_width=True,
                type=button_type,
            ):
                st.session_state["selected_by_row"][row_id] = name
                st.rerun()


def _position_picker() -> None:
    st.subheader("Position")
    cols = st.columns(len(POSITIONS), gap="small")
    selected_position = st.session_state.get("selected_position", "")

    for idx, position in enumerate(POSITIONS):
        with cols[idx]:
            button_type = "primary" if position == selected_position else "secondary"
            offset = POSITION_DISTANCE_FROM_BUTTON[position]
            label = f"{position} ({offset:+d})" if offset != 0 else f"{position} (0)"
            if st.button(
                label,
                key=f"position_{position}",
                use_container_width=True,
                type=button_type,
            ):
                st.session_state["selected_position"] = position
                st.rerun()


def _render_players_section() -> None:
    def _reset_player_form() -> None:
        st.session_state["editing_player_index"] = None
        st.session_state["pending_edit_player_index"] = None
        st.session_state["pending_player_form_reset"] = False
        st.session_state["player_name_input"] = ""
        st.session_state["player_vpip_input"] = 0
        st.session_state["player_pfr_input"] = 0
        st.session_state["player_three_bet_input"] = 0
        st.session_state["player_fold_to_three_bet_input"] = 0
        st.session_state["player_cbet_input"] = 0
        st.session_state["player_fold_to_cbet_input"] = 0
        st.session_state["player_steal_input"] = 0
        st.session_state["player_check_raise_input"] = 0

    players = st.session_state["players"]

    if st.session_state.get("pending_player_form_reset"):
        _reset_player_form()

    flash_message = st.session_state.get("player_flash_message", "")
    if flash_message:
        st.success(flash_message)
        st.session_state["player_flash_message"] = ""

    pending_idx = st.session_state.get("pending_edit_player_index")
    if isinstance(pending_idx, int) and 0 <= pending_idx < len(players):
        player = players[pending_idx]
        st.session_state["editing_player_index"] = pending_idx
        st.session_state["player_name_input"] = player["Name"]
        st.session_state["player_vpip_input"] = int(player["VPIP"])
        st.session_state["player_pfr_input"] = int(player["PFR"])
        st.session_state["player_three_bet_input"] = int(player["3-BET"])
        st.session_state["player_fold_to_three_bet_input"] = int(player["Fold to 3-Bet"])
        st.session_state["player_cbet_input"] = int(player["C-BET"])
        st.session_state["player_fold_to_cbet_input"] = int(player["Fold to C-Bet"])
        st.session_state["player_steal_input"] = int(player["Steal"])
        st.session_state["player_check_raise_input"] = int(player["Check/Raise"])
        st.session_state["pending_edit_player_index"] = None

    editing_index = st.session_state["editing_player_index"]
    is_editing = isinstance(editing_index, int) and 0 <= editing_index < len(players)

    st.subheader("Edit Player" if is_editing else "Add Player")

    with st.form("add_player_form", clear_on_submit=False):
        name = st.text_input("Player Name", key="player_name_input")

        cols_row_1 = st.columns(4, gap="small")
        with cols_row_1[0]:
            vpip = st.number_input("VPIP (%)", min_value=0, max_value=100, step=1, format="%d", key="player_vpip_input")
        with cols_row_1[1]:
            pfr = st.number_input("PFR (%)", min_value=0, max_value=100, step=1, format="%d", key="player_pfr_input")
        with cols_row_1[2]:
            three_bet = st.number_input("3-BET (%)", min_value=0, max_value=100, step=1, format="%d", key="player_three_bet_input")
        with cols_row_1[3]:
            fold_to_three_bet = st.number_input("Fold to 3-Bet (%)", min_value=0, max_value=100, step=1, format="%d", key="player_fold_to_three_bet_input")

        cols_row_2 = st.columns(4, gap="small")
        with cols_row_2[0]:
            cbet = st.number_input("C-BET (%)", min_value=0, max_value=100, step=1, format="%d", key="player_cbet_input")
        with cols_row_2[1]:
            fold_to_cbet = st.number_input("Fold to C-Bet (%)", min_value=0, max_value=100, step=1, format="%d", key="player_fold_to_cbet_input")
        with cols_row_2[2]:
            steal = st.number_input("Steal (%)", min_value=0, max_value=100, step=1, format="%d", key="player_steal_input")
        with cols_row_2[3]:
            check_raise = st.number_input("Check/Raise (%)", min_value=0, max_value=100, step=1, format="%d", key="player_check_raise_input")

        action_col, cancel_col = st.columns(2, gap="small")
        with action_col:
            submitted = st.form_submit_button("Update Player" if is_editing else "Add Player", use_container_width=True)
        with cancel_col:
            canceled = st.form_submit_button("Cancel Edit", use_container_width=True, disabled=not is_editing)

    if canceled:
        st.session_state["pending_player_form_reset"] = True
        st.rerun()

    if submitted:
        clean_name = name.strip()
        if not clean_name:
            st.warning("Enter a player name before saving.")
        else:
            payload = {
                "Name": clean_name,
                "VPIP": int(vpip),
                "PFR": int(pfr),
                "3-BET": int(three_bet),
                "Fold to 3-Bet": int(fold_to_three_bet),
                "C-BET": int(cbet),
                "Fold to C-Bet": int(fold_to_cbet),
                "Steal": int(steal),
                "Check/Raise": int(check_raise),
            }

            if is_editing:
                payload["Pre Flop Action"] = players[editing_index].get("Pre Flop Action", "")
                payload["Position"] = players[editing_index].get("Position", POSITIONS[0])
                players[editing_index] = payload
                st.session_state["player_flash_message"] = f"Updated {clean_name}."
            else:
                payload["Pre Flop Action"] = ""
                payload["Position"] = POSITIONS[0]
                players.append(payload)
                st.session_state["player_flash_message"] = f"Added {clean_name}."

            st.session_state["pending_player_form_reset"] = True
            st.rerun()

    if players:
        st.markdown("Saved Players")
        for idx, player in enumerate(players):
            player_cols = st.columns([5, 1, 1], gap="small")
            summary = (
                f"{player['Name']} | VPIP {player['VPIP']}% | PFR {player['PFR']}% | "
                f"3-BET {player['3-BET']}% | Fold to 3-Bet {player['Fold to 3-Bet']}% | "
                f"C-BET {player['C-BET']}% | Fold to C-Bet {player['Fold to C-Bet']}% | "
                f"Steal {player['Steal']}% | Check/Raise {player['Check/Raise']}% | "
                f"Position {player.get('Position', '-') or '-'} | Action {player.get('Pre Flop Action', '-') or '-'}"
            )
            with player_cols[0]:
                st.write(summary)
            with player_cols[1]:
                if st.button("Edit", key=f"edit_player_{idx}", use_container_width=True):
                    st.session_state["pending_edit_player_index"] = idx
                    st.rerun()
            with player_cols[2]:
                if st.button("Delete", key=f"delete_player_{idx}", use_container_width=True):
                    players.pop(idx)
                    if st.session_state["editing_player_index"] == idx:
                        st.session_state["pending_player_form_reset"] = True
                    elif isinstance(st.session_state["editing_player_index"], int) and st.session_state["editing_player_index"] > idx:
                        st.session_state["editing_player_index"] -= 1
                    st.rerun()


_init_state()


if st.button("Next Hand", key="next_hand_btn", use_container_width=False):
    _rotate_players_positions_next_hand()
    st.rerun()


st.title("My hand")

st.header("First card")

_row_picker(1, CARD_ORDER)
_row_picker(2, COLOR_ORDER)

st.header("Second card")

_row_picker(3, CARD_ORDER)
_row_picker(4, COLOR_ORDER)

st.divider()
selected_position = _get_pyrex_position()
st.subheader("Hand")
hand_notation = _build_hand_notation()
if hand_notation is None:
    st.write("Select all 4 rows to build your hand.")
else:
    st.success(f"{hand_notation}, {selected_position}")

st.divider()
st.subheader("The Pre Flop Session")
_render_pre_flop_players_actions()
st.divider()
_render_plays_matrix(hand_notation, selected_position)

if hand_notation is not None and selected_position:
    st.divider()
    plot_path = CM_PLOTS_DIR / f"{hand_notation}.html"
    if plot_path.exists():
        plot_html = plot_path.read_text(encoding="utf-8")
        components.html(plot_html, height=700, scrolling=True)
    else:
        st.info(f"Plot file not found for {hand_notation}.")

st.divider()
_render_players_section()
