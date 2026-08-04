"""Lock full ordered shear repair search for an unlocked underdesign case."""

from __future__ import annotations

import contextlib
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SOURCE = (
    ROOT
    / "artifacts"
    / "verification"
    / "live_fuzz"
    / "replay_2026-07-28T21-48-27"
    / "failure_browser_state.json"
)
ARTIFACT = (
    ROOT
    / "artifacts"
    / "verification"
    / "shear_fail_unlocked_full_ladder_direct_runtime.json"
)


def main() -> int:
    if not SOURCE.exists():
        print(f"FAIL: captured state missing: {SOURCE}")
        return 1

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import streamlit as st

        from inputs_application.guidance_entrypoint import (
            build_guidance_entrypoint_runtime,
            compute_inputs_guidance,
        )

    browser_state = json.loads(SOURCE.read_text(encoding="utf-8"))
    state = dict(browser_state.get("summary_state_probe") or {})
    try:
        st.session_state.clear()
    except Exception:
        pass
    for key, value in state.items():
        st.session_state[key] = deepcopy(value)

    runtime = build_guidance_entrypoint_runtime(
        st_module=st,
        os_module=os,
        sys_module=sys,
    )
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        payload = compute_inputs_guidance(
            runtime,
            deepcopy(state),
            guidance_debug_verbose=True,
            debug_enabled=True,
        )

    items = [
        dict(row)
        for row in list(payload.get("guidance_items") or [])
        if isinstance(row, dict)
    ]
    item = dict(items[0] if items else {})
    button = dict(item.get("button_contract") or {})
    evidence = dict(item.get("candidate_search_evidence") or {})
    debug = dict(payload.get("debug_trace") or {})
    updates = dict(
        button.get("updates")
        or item.get("updates")
        or dict(item.get("action_payload") or {}).get("updates")
        or {}
    )

    checks = {
        "captured_case_geometry_is_unlocked": (
            state.get("optimisation_lock_geometry") is False
        ),
        "shear_fail_family_dispatched": (
            debug.get("family_ladder_dispatch_selected_family_id")
            == "SHEAR_FAIL_GOVERNS"
        ),
        "full_ladder_reaches_later_restart_step": (
            int(evidence.get("ladder_attempts") or 0) > 12
            and int(evidence.get("total_candidates_considered") or 0) > 12
        ),
        "passing_target_band_candidate_found": (
            evidence.get("ladder_success") is True
            and 0.88
            <= float(evidence.get("selected_candidate_util") or 0.0)
            <= 0.95
        ),
        "repair_is_executor_backed": (
            item.get("action_type") == "apply_resolved_candidate"
            and button.get("enabled") is True
            and button.get("actionable") is True
            and button.get("preview_pass") is True
            and bool(updates)
        ),
        "repair_advances_geometry_and_shear_ladder": (
            float(updates.get("D") or 0.0) > float(state.get("D") or 0.0)
            and float(updates.get("s_lig") or 9999.0)
            < float(state.get("s_lig") or 0.0)
            and int(updates.get("lig_legs") or 0)
            > int(state.get("lig_legs") or 0)
        ),
        "unlocked_case_is_not_published_as_exhausted": (
            debug.get("unlocked_underdesign_ladder_failed_to_repair") is not True
            and button.get("disabled_reason") is None
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    artifact = {
        "schema": "shear_fail_unlocked_full_ladder_direct_runtime.v1",
        "status": "PASS" if not failures else "FAIL",
        "source": str(SOURCE),
        "checks": checks,
        "failures": failures,
        "selected_updates": updates,
        "selected_candidate_util": evidence.get("selected_candidate_util"),
        "ladder_attempts": evidence.get("ladder_attempts"),
        "button_contract": button,
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PASS: unlocked shear underdesign continues through the ordered "
        "family ladder to an executable target-band repair"
        if not failures
        else f"FAIL: {failures}"
    )
    print(f"Artifact: {ARTIFACT}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
