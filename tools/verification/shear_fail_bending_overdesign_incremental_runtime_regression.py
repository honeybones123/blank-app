"""Lock incremental mandatory shear repair for the mixed overdesign family."""

from __future__ import annotations

import contextlib
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SOURCE = (
    ROOT
    / "artifacts"
    / "verification"
    / "live_fuzz"
    / "replay_2026-07-29T07-40-22"
    / "failure_browser_state.json"
)
ARTIFACT = (
    ROOT
    / "artifacts"
    / "verification"
    / "shear_fail_bending_overdesign_incremental_runtime_regression.json"
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
    started = time.perf_counter()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        payload = compute_inputs_guidance(
            runtime,
            deepcopy(state),
            guidance_debug_verbose=True,
            debug_enabled=True,
        )
    elapsed_s = time.perf_counter() - started

    debug = dict(payload.get("debug_trace") or {})
    ladder_result = dict(debug.get("family_ladder_runtime_result") or {})
    ordered = dict(ladder_result.get("ordered_mandatory_search") or {})
    selected = dict(ladder_result.get("selected_recommendation") or {})
    evaluation = dict(selected.get("evaluation") or {})
    items = [
        dict(row)
        for row in list(payload.get("guidance_items") or [])
        if isinstance(row, dict)
    ]
    item = dict(items[0] if items else {})
    button = dict(item.get("button_contract") or {})
    updates = dict(button.get("updates") or item.get("updates") or {})

    checks = {
        "captured_geometry_is_unlocked": (
            state.get("optimisation_lock_geometry") is False
        ),
        "mixed_family_dispatched": (
            debug.get("family_ladder_dispatch_selected_family_id")
            == "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"
        ),
        "mandatory_search_is_incremental_not_sampled": (
            ordered.get("policy")
            == "incremental_until_valid_repair_or_canonical_exhaustion"
            and int(ordered.get("attempted_count") or 0) > 0
            and int(ordered.get("attempted_count") or 0)
            < int(ordered.get("candidate_count") or 0)
            and ordered.get("stopped_on_valid_repair") is True
        ),
        "shear_repair_reaches_target_band": (
            evaluation.get("shear_repaired") is True
            and evaluation.get("bending_compliant") is True
            and evaluation.get("shear_inside_target_band") is True
            and 0.85
            <= float(evaluation.get("shear_utilisation_after") or 0.0)
            <= 1.0
        ),
        "repair_is_executor_backed": (
            item.get("action_type") == "apply_resolved_candidate"
            and button.get("enabled") is True
            and button.get("actionable") is True
            and button.get("preview_pass") is True
            and bool(updates)
        ),
        "repair_uses_shear_reinforcement_before_geometry": (
            updates.get("s_lig") == 100.0
            and updates.get("lig_legs") == 6
            and not (set(updates) & {"D", "b", "bw"})
        ),
        "false_unlocked_blocker_is_absent": (
            debug.get("unlocked_underdesign_ladder_failed_to_repair") is not True
            and button.get("disabled_reason") is None
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    artifact = {
        "schema": "shear_fail_bending_overdesign_incremental_runtime_regression.v1",
        "status": "PASS" if not failures else "FAIL",
        "source": str(SOURCE),
        "checks": checks,
        "failures": failures,
        "elapsed_s": elapsed_s,
        "ordered_mandatory_search": ordered,
        "selected_updates": updates,
        "selected_evaluation": evaluation,
        "button_contract": button,
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PASS: mixed shear-underdesign family incrementally reaches an "
        "executor-backed repair before geometry"
        if not failures
        else f"FAIL: {failures}"
    )
    print(f"Artifact: {ARTIFACT}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
