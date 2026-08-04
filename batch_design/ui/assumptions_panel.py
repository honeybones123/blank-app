"""Project assumptions UI boundary."""

from __future__ import annotations


def render_assumptions_panel(st) -> None:
    st.text_input("Assumption set", value="Project defaults", key="batch_design_assumption_set")
