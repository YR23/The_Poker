import streamlit as st

from detector.ranges import get_action, VALID_POSITIONS


RANK_OPTIONS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]
RANK_ORDER = "23456789TJQKA"


def _sorted_ranks(rank1: str, rank2: str) -> tuple[str, str]:
    if RANK_ORDER.index(rank1) >= RANK_ORDER.index(rank2):
        return rank1, rank2
    return rank2, rank1


def build_hand_notation(rank1: str, rank2: str, hand_type: str) -> str:
    r1, r2 = _sorted_ranks(rank1, rank2)

    if r1 == r2:
        return f"{r1}{r2}"

    if hand_type == "Suited":
        return f"{r1}{r2}s"

    return f"{r1}{r2}o"


def main() -> None:
    st.set_page_config(page_title="Poker Preflop Advisor", layout="centered")
    st.title("Poker Preflop Advisor")
    st.write("Choose your two hole-card ranks, suited or offsuit, and your position.")

    c1, c2 = st.columns(2)
    with c1:
        rank1 = st.selectbox("Card 1 rank", options=RANK_OPTIONS, index=0)
    with c2:
        rank2 = st.selectbox("Card 2 rank", options=RANK_OPTIONS, index=1)

    if rank1 == rank2:
        st.info("Pocket pair selected. Suited or offsuit is ignored.")
        hand_type = "Pair"
    else:
        hand_type = st.radio("Hand type", options=["Suited", "Offsuit"], horizontal=True)

    position = st.selectbox("Position", options=VALID_POSITIONS, index=VALID_POSITIONS.index("SB"))

    hand = build_hand_notation(rank1, rank2, hand_type)
    action = get_action(position, hand)

    st.subheader("Result")
    st.write(f"Hand: {hand}")
    st.write(f"Position: {position}")
    st.success(f"Action: {action}")


if __name__ == "__main__":
    main()
