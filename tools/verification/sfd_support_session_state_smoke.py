"""Smoke check that SFD support selections survive page-change hydration."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

import sfd_bmd_page  # noqa: E402
from calculations.deflection import defl_support_type_from_design_selection  # noqa: E402
from state_and_helpers import safe_hydrate  # noqa: E402


def _router_design_support_guard_allows(changed_keys: set[str], selected_slug: str = "design") -> bool:
    design_support_keys = {"design_support_condition"} | {
        f"design_support_type_{idx}" for idx in range(1, 7)
    }
    return selected_slug == "design" and bool(changed_keys) and changed_keys.issubset(design_support_keys)


def main() -> int:
    failures: list[str] = []

    st.session_state.clear()
    st.session_state["design_support_condition"] = "Simply supported"
    st.session_state["sfd_support_condition"] = "Fixed-Pinned"
    sfd_bmd_page._sync_design_shared_value(
        "design_support_condition",
        "Fixed-Pinned",
        source="sfd_support_session_state_smoke",
    )
    safe_hydrate(
        "sfd_support_condition",
        "design_support_condition",
        st.session_state.get("design_support_condition"),
        force=True,
    )
    if st.session_state.get("sfd_support_condition") != "Fixed-Pinned":
        failures.append("single_span_support_condition_reverted_on_hydrate")
    if not _router_design_support_guard_allows({"design_support_condition"}):
        failures.append("design_support_condition_not_allowed_by_router_guard")

    st.session_state["design_support_type_2"] = "Pinned"
    st.session_state["sfd_support_type_2"] = "Roller"
    sfd_bmd_page._sync_design_shared_value(
        "design_support_type_2",
        "Roller",
        source="sfd_support_session_state_smoke",
    )
    safe_hydrate(
        "sfd_support_type_2",
        "design_support_type_2",
        st.session_state.get("design_support_type_2"),
        force=True,
    )
    if st.session_state.get("sfd_support_type_2") != "Roller":
        failures.append("multi_span_support_type_reverted_on_hydrate")
    if not _router_design_support_guard_allows({"design_support_type_2"}):
        failures.append("design_support_type_not_allowed_by_router_guard")
    if _router_design_support_guard_allows({"design_support_type_2", "b"}):
        failures.append("router_guard_allows_unrelated_shared_key")

    support_cases = {
        "Fixed-Pinned": "Fixed",
        "Fixed–Pinned": "Fixed",
        "Fixed�Pinned": "Fixed",
        "Pinned-Fixed": "Pinned",
        "Pinned–Fixed": "Pinned",
        "Pinned�Fixed": "Pinned",
        "Fixed-Free": "Cantilever",
        "Fixed–Free": "Cantilever",
        "Fixed�Free": "Cantilever",
    }
    for raw_label, expected_prefix in support_cases.items():
        resolved = defl_support_type_from_design_selection(
            "Simple beam - UDL over entire span",
            raw_label,
        )
        if not str(resolved).startswith(expected_prefix):
            failures.append(f"support_label_not_resolved:{raw_label}->{resolved}")

    if failures:
        print("SFD_SUPPORT_SESSION_STATE_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("SFD_SUPPORT_SESSION_STATE_SMOKE PASS")
    print("- single-span and multi-span support selections survive forced page-change hydration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
