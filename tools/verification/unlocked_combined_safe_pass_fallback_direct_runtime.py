"""Prove unlocked combined underdesign continues to a passing repair."""

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
    / "replay_2026-07-28T19-46-39"
    / "failure_browser_state.json"
)
ARTIFACT = (
    ROOT
    / "artifacts"
    / "verification"
    / "unlocked_combined_safe_pass_fallback_direct_runtime.json"
)


def main() -> int:
    if not SOURCE.exists():
        print(f"FAIL: captured state missing: {SOURCE}")
        return 1

    browser_state = json.loads(SOURCE.read_text(encoding="utf-8"))
    state = dict(browser_state.get("browser_shared_probe") or {})
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import streamlit as st

        from inputs_application.guidance_entrypoint import (
            build_guidance_entrypoint_runtime,
            compute_inputs_guidance,
        )

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
    updates = dict(button.get("updates") or item.get("updates") or {})
    debug = dict(payload.get("debug_trace") or {})
    family_result = dict(debug.get("family_ladder_runtime_result") or {})
    specs = [
        dict(row)
        for row in list(family_result.get("specs") or [])
        if isinstance(row, dict)
    ]
    observed_phases = [
        str(row.get("contract_step") or "").strip().upper()
        for row in specs
        if str(row.get("contract_step") or "").strip()
    ]
    phase_rank = {
        "REINFORCEMENT_ONLY": 0,
        "SHEAR_ONLY": 1,
        "COMBINED_ADJUSTMENT": 2,
        "GEOMETRY": 3,
    }
    observed_ranks = [
        phase_rank[phase] for phase in observed_phases if phase in phase_rank
    ]
    ladder_attempts = int(debug.get("direct_target_band_ladder_attempts") or 0)
    target_band_success = (
        debug.get("direct_target_band_ladder_success") is True
        and debug.get("family_ladder_runtime_selected") is True
    )
    safe_fallback_selected = (
        debug.get("family_safe_pass_fallback_selected") is True
        and int(debug.get("family_safe_pass_fallback_candidate_count") or 0) > 0
    )
    update_keys = set(updates)

    checks = {
        "captured_state_is_unlocked": not bool(
            state.get("optimisation_lock_geometry")
        ),
        "one_guidance_item": len(items) == 1,
        "combined_family_dispatched": (
            debug.get("family_ladder_dispatch_selected_family_id")
            == "COMBINED_BENDING_SHEAR_FAIL"
        ),
        "family_ladder_branch_selected": (
            debug.get("guidance_branch") == "critical_family_ladder_first"
        ),
        "ordered_ladder_attempts_are_bounded": (
            bool(specs) and 0 < ladder_attempts <= len(specs)
        ),
        "family_ladder_phase_order": (
            bool(observed_ranks)
            and observed_ranks == sorted(observed_ranks)
            and observed_ranks[-1] == phase_rank["GEOMETRY"]
        ),
        "passing_resolution_selected": (
            target_band_success or safe_fallback_selected
        ),
        "unlocked_failure_not_terminalised": not bool(
            debug.get("unlocked_underdesign_ladder_failed_to_repair")
        ),
        "enabled_executor_action": (
            item.get("action_type") == "apply_resolved_candidate"
            and button.get("enabled") is True
            and button.get("actionable") is True
            and button.get("preview_pass") is True
        ),
        "passing_repair_keeps_action_copy": (
            item.get("guidance_intent") == "required_fix"
            and "no one-click" not in str(item.get("primary_action") or "").lower()
            and (
                not safe_fallback_selected
                or (
                    item.get("family_safe_pass_fallback") is True
                    and item.get("post_repair_cleanup_required") is True
                )
            )
        ),
        "combined_update_covers_all_required_lanes": (
            bool(update_keys & {"b", "bw", "D"})
            and bool(
                update_keys
                & {
                    "bot_row_1_bars",
                    "bot_row_2_bars",
                    "bot_row_1_dia",
                    "bot_row_2_dia",
                }
            )
            and bool(update_keys & {"s_lig", "lig_d", "lig_legs"})
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    artifact = {
        "schema": "unlocked_combined_safe_pass_fallback_direct_runtime.v1",
        "status": "PASS" if not failures else "FAIL",
        "source": str(SOURCE),
        "checks": checks,
        "failures": failures,
        "selected_title": item.get("title_main"),
        "selected_updates": updates,
        "ladder_attempts": ladder_attempts,
        "runtime_spec_count": len(specs),
        "observed_phases": observed_phases,
        "target_band_success": target_band_success,
        "safe_fallback_selected": safe_fallback_selected,
        "safe_pass_fallback_candidate_count": debug.get(
            "family_safe_pass_fallback_candidate_count"
        ),
        "selected_guidance_intent": item.get("guidance_intent"),
        "selected_primary_action": item.get("primary_action"),
        "selected_family_safe_pass_fallback": item.get(
            "family_safe_pass_fallback"
        ),
        "selected_post_repair_cleanup_required": item.get(
            "post_repair_cleanup_required"
        ),
        "button_post_repair_cleanup_required": button.get(
            "post_repair_cleanup_required"
        ),
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PASS: unlocked combined underdesign publishes a full-truth passing "
        "repair"
        if not failures
        else f"FAIL: {failures}"
    )
    print(f"Artifact: {ARTIFACT}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
