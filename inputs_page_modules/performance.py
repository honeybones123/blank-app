from __future__ import annotations

import time

import streamlit as st


def render_inputs_perf_marker_setup_coordinator(*, ss: dict):
    t0 = time.perf_counter()
    if "_perf_log" not in ss:
        ss["_perf_log"] = []
    perf_start = time.perf_counter()
    perf_marks = []
    sub_marks = []

    def mark(label):
        perf_marks.append((label, time.perf_counter()))

    def sub_mark(label):
        sub_marks.append((label, time.perf_counter()))

    return t0, perf_start, perf_marks, sub_marks, mark, sub_mark


def render_inputs_perf_finalization_current_coordinator(
    *,
    perf_start: float,
    perf_marks: list,
    sub_marks: list,
    t0: float,
) -> None:
    perf_end = time.perf_counter()
    section_times = []
    for i in range(1, len(perf_marks)):
        prev_label, prev_time = perf_marks[i - 1]
        curr_label, curr_time = perf_marks[i]
        section_times.append(
            {
                "section": f"{prev_label} \u2192 {curr_label}",
                "ms": round((curr_time - prev_time) * 1000, 2),
            }
        )
    section_times = sorted(section_times, key=lambda x: x["ms"], reverse=True)

    sub_section_times = []
    for i in range(1, len(sub_marks)):
        prev_label, prev_time = sub_marks[i - 1]
        curr_label, curr_time = sub_marks[i]
        sub_section_times.append(
            {
                "section": f"{prev_label} \u2192 {curr_label}",
                "ms": round((curr_time - prev_time) * 1000, 2),
            }
        )
    sub_section_times = sorted(sub_section_times, key=lambda x: x["ms"], reverse=True)

    total_time = round((perf_end - perf_start) * 1000, 2)

    st.session_state["_perf_log"] = {
        "total_ms": total_time,
        "sections": section_times,
        "top_inputs_widgets_sections": sub_section_times,
    }
    try:
        import session_state_final_log as ssl

        ssl.append_session_state_final_log(
            "inputs_render_perf",
            {
                "total_ms": total_time,
                "sections_top5": section_times[:5],
                "top_inputs_widgets_sections_top5": sub_section_times[:5],
            },
        )
    except Exception:
        pass

    if st.session_state.get("_dev_mode", False) and st.sidebar.checkbox(
        "Show performance debug",
        value=False,
    ):
        perf = st.session_state.get("_perf_log", {})
        st.sidebar.metric("Inputs render (ms)", perf.get("total_ms", 0))
        st.sidebar.metric("Compute time (ms)", st.session_state.get("_compute_time_ms", 0))
        if "sections" in perf:
            st.sidebar.dataframe(perf["sections"], width="stretch")
        if "top_inputs_widgets_sections" in perf:
            st.sidebar.caption("Top inputs widgets breakdown")
            st.sidebar.dataframe(perf["top_inputs_widgets_sections"], width="stretch")

    if bool(st.session_state.get("_dev_mode")):
        st.caption(f"Inputs render: {(time.perf_counter() - t0) * 1000:.1f} ms")


__all__ = [
    "render_inputs_perf_finalization_current_coordinator",
    "render_inputs_perf_marker_setup_coordinator",
]
