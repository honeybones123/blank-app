"""Focused replay of the captured unlocked combined-failure engineering state."""

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
    / "replay_2026-07-28T18-46-14"
    / "failure_browser_state.json"
)
ARTIFACT = (
    ROOT
    / "artifacts"
    / "verification"
    / "unlocked_combined_captured_state_direct_runtime.json"
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
    resolved = dict(item.get("resolved_candidate") or {})
    button = dict(item.get("button_contract") or {})
    updates = dict(
        item.get("updates")
        or resolved.get("updates")
        or button.get("updates")
        or {}
    )
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
    runtime_depths = [
        float(dict(row.get("updates") or {}).get("D") or 0.0)
        for row in specs
        if dict(row.get("updates") or {}).get("D") is not None
    ]
    runtime_widths = [
        float(
            dict(row.get("updates") or {}).get("b")
            or dict(row.get("updates") or {}).get("bw")
            or 0.0
        )
        for row in specs
        if (
            dict(row.get("updates") or {}).get("b") is not None
            or dict(row.get("updates") or {}).get("bw") is not None
        )
    ]
    ladder_attempts = int(debug.get("direct_target_band_ladder_attempts") or 0)
    utilisation = item.get("candidate_post_util")
    if utilisation is None:
        utilisation = resolved.get("candidate_post_util")
    try:
        utilisation_value = float(utilisation)
    except (TypeError, ValueError):
        utilisation_value = None
    base_b = float(state.get("b") or state.get("bw") or 0.0)
    base_depth = float(state.get("D") or 0.0)
    selected_b = float(updates.get("b") or updates.get("bw") or base_b)
    selected_depth = float(updates.get("D") or base_depth)
    width_increase = selected_b - base_b
    depth_increase = selected_depth - base_depth
    selected_row_1_bars = int(
        updates.get("bot_row_1_bars")
        or state.get("bot_row_1_bars")
        or 0
    )
    selected_row_2_bars = int(
        updates.get("bot_row_2_bars")
        or state.get("bot_row_2_bars")
        or 0
    )
    selected_row_1_dia = float(
        updates.get("bot_row_1_dia")
        or state.get("bot_row_1_dia")
        or 0.0
    )
    selected_row_2_dia = float(
        updates.get("bot_row_2_dia")
        or state.get("bot_row_2_dia")
        or 0.0
    )
    base_lig_d = int(state.get("lig_d") or 0)
    base_lig_legs = int(state.get("lig_legs") or 0)
    base_lig_spacing = float(state.get("s_lig") or 0.0)
    selected_lig_d = int(updates.get("lig_d") or base_lig_d)
    selected_lig_legs = int(updates.get("lig_legs") or base_lig_legs)
    selected_lig_spacing = float(
        updates.get("s_lig") or base_lig_spacing
    )

    checks = {
        "one_guidance_item": len(items) == 1,
        "selected_family_is_combined": (
            debug.get("family_ladder_dispatch_selected_family_id")
            == "COMBINED_BENDING_SHEAR_FAIL"
        ),
        "family_ladder_branch_selected": (
            debug.get("guidance_branch") == "critical_family_ladder_first"
        ),
        "family_ladder_succeeded": (
            debug.get("direct_target_band_ladder_success") is True
            and debug.get("family_ladder_runtime_selected") is True
        ),
        "unlocked_failure_did_not_terminalise": not debug.get(
            "unlocked_underdesign_ladder_failed_to_repair"
        ),
        "application_truth_reached_target_band": (
            utilisation_value is not None
            and 0.88 <= utilisation_value <= 0.95
        ),
        "legal_incremental_geometry_selected": (
            width_increase >= 0.0
            and depth_increase >= 0.0
            and (width_increase > 0.0 or depth_increase > 0.0)
            and abs((width_increase / 25.0) - round(width_increase / 25.0))
            < 1e-9
            and abs((depth_increase / 25.0) - round(depth_increase / 25.0))
            < 1e-9
        ),
        "second_row_reinforcement_selected": (
            selected_row_1_bars > 0
            and selected_row_1_dia > 0.0
            and selected_row_2_bars > 0
            and selected_row_2_dia > 0.0
        ),
        "strengthened_shear_selected": (
            selected_lig_d >= base_lig_d
            and selected_lig_legs >= base_lig_legs
            and selected_lig_spacing <= base_lig_spacing
            and (
                selected_lig_d > base_lig_d
                or selected_lig_legs > base_lig_legs
                or selected_lig_spacing < base_lig_spacing
            )
        ),
        "enabled_executor_action": (
            item.get("action_type") == "apply_resolved_candidate"
            and button.get("enabled") is True
        ),
        "family_ladder_phase_order": (
            bool(observed_ranks)
            and observed_ranks == sorted(observed_ranks)
            and observed_ranks[-1] == phase_rank["GEOMETRY"]
        ),
        "canonical_geometry_inventory_reaches_both_limits": (
            max(runtime_depths, default=0.0) == 5000.0
            and max(runtime_widths, default=0.0) == 5000.0
        ),
        "bounded_incremental_search": (
            bool(specs) and 0 < ladder_attempts <= len(specs)
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    artifact = {
        "schema": "unlocked_combined_captured_state_direct_runtime.v1",
        "status": "PASS" if not failures else "FAIL",
        "root_cause_category": "candidate_search_failure",
        "source": str(SOURCE),
        "checks": checks,
        "failures": failures,
        "selected_updates": updates,
        "selected_shear": {
            "base": {
                "lig_d": base_lig_d,
                "lig_legs": base_lig_legs,
                "s_lig": base_lig_spacing,
            },
            "selected": {
                "lig_d": selected_lig_d,
                "lig_legs": selected_lig_legs,
                "s_lig": selected_lig_spacing,
            },
        },
        "selected_utilisation": utilisation_value,
        "guidance_branch": debug.get("guidance_branch"),
        "ladder_attempts": ladder_attempts,
        "runtime_spec_count": len(specs),
        "runtime_max_depth_mm": max(runtime_depths, default=None),
        "runtime_max_width_mm": max(runtime_widths, default=None),
        "observed_phases": observed_phases,
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PASS: captured unlocked combined failure selects a full-truth "
        "target-band repair"
        if not failures
        else f"FAIL: {failures}"
    )
    print(f"Artifact: {ARTIFACT}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
