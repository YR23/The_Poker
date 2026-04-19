import streamlit as st


def _classify_three_bet_range(three_bet_percent: float) -> tuple[str, str]:
    if three_bet_percent <= 5.0:
        return (
            "DEPOLARIZED",
            "5% or less is most likely a depolarized 3-betting range.",
        )
    if three_bet_percent < 8.0:
        return (
            "UNCLEAR",
            "6-7% can be polarized, but may still be depolarized.",
        )
    return (
        "POLARIZED",
        "8%+ is most likely a polarized 3-betting range.",
    )


def render_defend_three_bet_expander() -> None:
    with st.expander("Defending a 3-bet", expanded=False):
        st.write("Enter villain 3-bet percentage to evaluate polarization.")

        default_value = st.session_state.get("villain_three_bet_percent", 3.0)
        three_bet_percent = st.number_input(
            "Villain 3-bet %",
            min_value=0.0,
            max_value=100.0,
            value=float(default_value),
            step=0.1,
            format="%.1f",
            key="villain_three_bet_percent",
        )

        classification, explanation = _classify_three_bet_range(three_bet_percent)

        if classification == "DEPOLARIZED":
            st.success(f"{three_bet_percent:.1f}% -> {classification}")
            st.image(
                "DCIM/depolarized.png",
                caption="Most likely depolarized 3-bet range",
                use_container_width=True,
            )
        elif classification == "POLARIZED":
            st.warning(f"{three_bet_percent:.1f}% -> {classification}")
            st.image(
                "DCIM/polarized.png",
                caption="Most likely polarized 3-bet range",
                use_container_width=True,
            )
        else:
            st.info(f"{three_bet_percent:.1f}% -> {classification}")
            comparison_col1, comparison_col2 = st.columns(2)
            with comparison_col1:
                st.image(
                    "DCIM/depolarized.png",
                    caption="Depolarized reference",
                    use_container_width=True,
                )
            with comparison_col2:
                st.image(
                    "DCIM/polarized.png",
                    caption="Polarized reference",
                    use_container_width=True,
                )

        st.caption(explanation)
