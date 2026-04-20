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


def _row_picker(row_id: int, names: list[str]) -> None:
    cols = st.columns(len(names), gap="small")
    selected_name = st.session_state["selected_by_row"].get(row_id)

    for idx, name in enumerate(names):
        with cols[idx]:
            button_type = "primary" if name == selected_name else "secondary"
            if st.button(
                name,
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


_init_state()


st.title("My hand")

st.header("First card")

_row_picker(1, CARD_ORDER)
_row_picker(2, COLOR_ORDER)

st.header("Second card")

_row_picker(3, CARD_ORDER)
_row_picker(4, COLOR_ORDER)

st.divider()
_position_picker()

st.divider()
st.subheader("Hand")
hand_notation = _build_hand_notation()
selected_position = st.session_state.get("selected_position", "")
if hand_notation is None or not selected_position:
    st.write("Select all 4 rows and one position to build your hand.")
else:
    st.success(hand_notation)

st.divider()
st.subheader("The Pre Flop Session")
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
