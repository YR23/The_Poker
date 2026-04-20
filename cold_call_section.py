import streamlit as st

from open_raise_section import normalize_hand


POSITIONS = ["UTG", "MP", "CO"]


def _pair_range(high_pair: str, low_pair: str) -> set[str]:
    ranks = "AKQJT98765432"
    start_idx = ranks.index(high_pair)
    end_idx = ranks.index(low_pair)
    return {ranks[idx] * 2 for idx in range(start_idx, end_idx + 1)}


COLD_CALL_CHARTS: dict[str, dict[str, object]] = {
    "UTG": {
        "title": "UTG Open-Raise 7.69% Cold-Calling Range",
        "range_text": "QQ-44, AQs-AJs, KQs, JTs, T9s, 98s, AQo+",
        "gap_text": "QQ-99, AQs-AJs, KQs, AQo+",
        "weaker_text": "88-44, JTs, T9s, 98s",
        "value_text": "AA-KK, AKs",
        "optional_text": "QQ, AKo",
        "cold_call": _pair_range("Q", "4") | {"AQs", "AJs", "KQs", "JTs", "T9s", "98s", "AQo", "AKo"},
        "gap": _pair_range("Q", "9") | {"AQs", "AJs", "KQs", "AQo", "AKo"},
        "weaker": _pair_range("8", "4") | {"JTs", "T9s", "98s"},
        "value": {"AA", "KK", "AKs"},
        "optional": {"QQ", "AKo"},
    },
    "MP": {
        "title": "MP Open-Raise 9.65% Cold-Calling Range",
        "range_text": "JJ-22, AQs-ATs, KJs+, QJs, JTs, T9s, 98s, 87s, 76s, AQo+",
        "gap_text": "JJ-88, AQs-AJs, KJs+, QJs, AQo+",
        "weaker_text": "77-22, ATs, JTs-76s",
        "value_text": "AA-QQ, AKs",
        "optional_text": "JJ, AQo+",
        "cold_call": _pair_range("J", "2") | {"AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs", "T9s", "98s", "87s", "76s", "AQo", "AKo"},
        "gap": _pair_range("J", "8") | {"AQs", "AJs", "KQs", "KJs", "QJs", "AQo", "AKo"},
        "weaker": _pair_range("7", "2") | {"ATs", "JTs", "T9s", "98s", "87s", "76s"},
        "value": {"AA", "KK", "QQ", "AKs"},
        "optional": {"JJ", "AQo", "AKo"},
    },
    "CO": {
        "title": "CO Open-Raise 11.01% Cold-Calling Range",
        "range_text": "TT-22, ATs, KTs+, QTs+, J9s+, T9s, 98s, 87s, 76s, 65s, 54s, AJo, KJo+",
        "gap_text": "TT-66, ATs, KJs+, QJs, AJo, KJo+",
        "weaker_text": "55-22, KTs, QTs, JTs-54s, J9s",
        "value_text": "AA-JJ, AQ+, AJs",
        "optional_text": "AJo, ATs, KQs",
        "cold_call": _pair_range("T", "2") | {"ATs", "KQs", "KJs", "KTs", "QJs", "QTs", "JTs", "J9s", "T9s", "98s", "87s", "76s", "65s", "54s", "AJo", "KQo", "KJo"},
        "gap": _pair_range("T", "6") | {"ATs", "KQs", "KJs", "QJs", "AJo", "KQo", "KJo"},
        "weaker": _pair_range("5", "2") | {"KTs", "QTs", "JTs", "J9s", "T9s", "98s", "87s", "76s", "65s", "54s"},
        "value": {"AA", "KK", "QQ", "JJ", "AKs", "AQs", "AJs", "AKo", "AQo"},
        "optional": {"AJo", "ATs", "KQs"},
    },
}


def _render_chart_summary(chart: dict[str, object]) -> None:
    st.caption(str(chart["title"]))
    st.write(f"Range: {chart['range_text']}")
    st.write(f"Gap Concept Hands: {chart['gap_text']}")
    st.write(f"Weaker Starting Hands: {chart['weaker_text']}")
    st.write(f"Value 3-Betting Hands: {chart['value_text']}")
    st.write(f"Optional 3-Betting Hands: {chart['optional_text']}")


def _evaluate_cold_call(hand: str, opener_position: str) -> tuple[str, str]:
    chart = COLD_CALL_CHARTS.get(opener_position)
    if chart is None:
        return "unavailable", f"No cold-calling chart added yet for {opener_position} opens."

    cold_call = chart["cold_call"]
    gap = chart["gap"]
    weaker = chart["weaker"]
    value = chart["value"]
    optional = chart["optional"]

    if hand in cold_call and hand in optional:
        return "mix", f"Hand {hand} -> COLD-CALL / OPTIONAL 3-BET"
    if hand in value:
        return "value", f"Hand {hand} -> VALUE 3-BET"
    if hand in cold_call:
        if hand in gap:
            return "call", f"Hand {hand} -> COLD-CALL (gap concept hand)"
        if hand in weaker:
            return "call", f"Hand {hand} -> COLD-CALL (weaker starting hand)"
        return "call", f"Hand {hand} -> COLD-CALL"
    if hand in optional:
        return "optional", f"Hand {hand} -> OPTIONAL 3-BET"
    return "fold", f"Hand {hand} -> Not in cold-calling range"


def render_cold_call_expander(hand_input: str) -> None:
    with st.expander("Cold-calling", expanded=False):
        st.write("Choose the earlier-position opener and evaluate whether your hand is a cold-call.")

        row_columns = st.columns(len(POSITIONS))
        for idx, position in enumerate(POSITIONS):
            if row_columns[idx].button(f"vs {position}", key=f"cold_call_vs_{position}", use_container_width=True):
                st.session_state["cold_call_vs_position"] = position

        opener_position = st.session_state.get("cold_call_vs_position", "UTG")
        st.subheader(f"Versus: {opener_position} Open-Raise")

        chart = COLD_CALL_CHARTS.get(opener_position)
        if chart is None:
            st.info(f"No cold-calling chart added yet for {opener_position} opens.")
            return

        _render_chart_summary(chart)

        if not hand_input.strip():
            st.info("Enter a hand above to evaluate the cold-calling range.")
            st.session_state["cold_call_hand"] = ""
            st.session_state["cold_call_decision"] = ""
            return

        try:
            hand, _ = normalize_hand(hand_input)
            st.session_state["cold_call_hand"] = hand
            decision, message = _evaluate_cold_call(hand, opener_position)
            st.session_state["cold_call_decision"] = decision

            if decision == "value":
                st.success(message)
            elif decision == "call":
                st.success(message)
            elif decision == "mix":
                st.info(message)
            elif decision == "optional":
                st.info(message)
            else:
                st.warning(message)
        except ValueError as exc:
            st.session_state["cold_call_hand"] = ""
            st.session_state["cold_call_decision"] = ""
            st.warning(str(exc))
