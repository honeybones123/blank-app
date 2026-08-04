"""Lock terminal, material-reducing combined-overdesign publication."""

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

SOURCES = (
    ROOT
    / "artifacts"
    / "verification"
    / "live_fuzz"
    / "replay_2026-07-28T20-21-19"
    / "failure_browser_state.json",
    ROOT
    / "artifacts"
    / "verification"
    / "live_fuzz"
    / "replay_2026-07-28T20-22-31"
    / "failure_browser_state.json",
)
ARTIFACT = (
    ROOT
    / "artifacts"
    / "verification"
    / "combined_overdesign_ranked_material_cleanup_direct_runtime.json"
)


def _bottom_area_key(state: dict) -> float:
    return float(
        state.get("bot1_count", state.get("bot_row_1_bars")) or 0
    ) * float(
        state.get("db_bot_1", state.get("bot_row_1_dia")) or 0
    ) ** 2


def main() -> int:
    missing = [str(path) for path in SOURCES if not path.exists()]
    if missing:
        print(f"FAIL: captured states missing: {missing}")
        return 1

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import streamlit as st

        from design_brain.families.bending_overdesign_governs.runtime import (
            _candidate_updates_from_contract,
        )
        from inputs_application.guidance_entrypoint import (
            build_guidance_entrypoint_runtime,
            compute_inputs_guidance,
        )

    reduction_probe_state = {
        "b": 250.0,
        "D": 400.0,
        "bot1_count": 4,
        "db_bot_1": 16,
    }
    current_area = _bottom_area_key(reduction_probe_state)
    generated_rows = _candidate_updates_from_contract(reduction_probe_state)
    generated_bottom_rows = [
        dict(row.get("updates") or {})
        for row in generated_rows
        if set(dict(row.get("updates") or {}))
        & {
            "bot1_count",
            "db_bot_1",
            "bot_row_1_bars",
            "bot_row_1_dia",
        }
    ]
    nonreducing_rows = [
        row
        for row in generated_bottom_rows
        if _bottom_area_key({**reduction_probe_state, **row})
        >= current_area - 1e-9
    ]

    cases: list[dict] = []
    for source in SOURCES:
        browser_state = json.loads(source.read_text(encoding="utf-8"))
        state = dict(browser_state.get("browser_shared_probe") or {})
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
        with contextlib.redirect_stdout(
            io.StringIO()
        ), contextlib.redirect_stderr(io.StringIO()):
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
        fold = dict(
            dict(debug.get("family_ladder_runtime_result") or {}).get(
                "combined_overdesign_terminal_fold"
            )
            or {}
        )
        before_area = _bottom_area_key(state)
        after_area = _bottom_area_key({**state, **updates})
        before_section_area = float(state.get("b", state.get("bw", 0.0)) or 0.0) * float(
            state.get("D", 0.0) or 0.0
        )
        after_state = {**state, **updates}
        after_section_area = float(
            after_state.get("b", after_state.get("bw", 0.0)) or 0.0
        ) * float(after_state.get("D", 0.0) or 0.0)

        st.session_state.clear()
        for key, value in after_state.items():
            st.session_state[key] = deepcopy(value)
        post_runtime = build_guidance_entrypoint_runtime(
            st_module=st,
            os_module=os,
            sys_module=sys,
        )
        with contextlib.redirect_stdout(
            io.StringIO()
        ), contextlib.redirect_stderr(io.StringIO()):
            post_payload = compute_inputs_guidance(
                post_runtime,
                deepcopy(after_state),
                guidance_debug_verbose=True,
                debug_enabled=True,
            )
        post_items = [
            dict(row)
            for row in list(post_payload.get("guidance_items") or [])
            if isinstance(row, dict)
        ]
        post_item = dict(post_items[0] if post_items else {})
        post_button = dict(post_item.get("button_contract") or {})
        checks = {
            "combined_overdesign_dispatched": (
                debug.get("family_ladder_dispatch_selected_family_id")
                == "COMBINED_OVERDESIGN"
            ),
            "terminal_fold_completed": (
                fold.get("terminal_reached") is True
                and str(fold.get("terminal_candidate_status") or "")
                in {"TERMINAL_TARGET_BAND", "TERMINAL_EXACT_STOP"}
                and dict(fold.get("cumulative_updates") or {}) == updates
            ),
            "combined_cleanup_branch": (
                debug.get("guidance_branch") == "local_cleanup_combined"
            ),
            "overdesign_family_ladder_ran_before_generic_selector": (
                debug.get("overdesign_branch_used_family_ladder_first")
                is True
                and debug.get(
                    "generic_optimisation_selector_skipped_by_family_owner"
                )
                is True
            ),
            "primary_enabled_preview_passing_action": (
                bool(items)
                and item.get("action_type") == "apply_resolved_candidate"
                and button.get("enabled") is True
                and button.get("actionable") is True
                and button.get("preview_pass") is True
            ),
            "bottom_reinforcement_does_not_increase": (
                after_area <= before_area + 1e-9
            ),
            "section_material_reduced": (
                after_section_area < before_section_area - 1e-9
            ),
            "rectangular_width_aliases_coherent": (
                str(state.get("sec_shape") or "").upper() != "RECT"
                or after_state.get("b") == after_state.get("bw")
            ),
            "post_apply_is_terminal_without_second_cta": (
                str(post_item.get("status") or "").upper() == "PASS"
                and str(post_item.get("family") or "").upper()
                in {"EXACT_STOP_PROVEN", "TARGET_BAND_REACHED"}
                and post_button.get("enabled") is False
                and not bool(
                    post_button.get("updates") or post_item.get("updates")
                )
            ),
        }
        cases.append(
            {
                "source": str(source),
                "status": "PASS" if all(checks.values()) else "FAIL",
                "checks": checks,
                "before_bottom_area_key": before_area,
                "after_bottom_area_key": after_area,
                "before_section_area": before_section_area,
                "after_section_area": after_section_area,
                "updates": updates,
                "terminal_fold_status": fold.get(
                    "terminal_candidate_status"
                ),
                "post_apply_status": post_item.get("status"),
                "post_apply_family": post_item.get("family"),
            }
        )

    checks = {
        "contract_reduction_lane_never_increases_bottom_steel": not nonreducing_rows,
        "both_captured_runtime_cases_pass": all(
            case["status"] == "PASS" for case in cases
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    artifact = {
        "schema": "combined_overdesign_terminal_material_cleanup_direct_runtime.v2",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "generated_bottom_candidate_count": len(generated_bottom_rows),
        "nonreducing_generated_rows": nonreducing_rows,
        "cases": cases,
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PASS: combined overdesign publishes one terminal material-reducing "
        "safe action"
        if not failures
        else f"FAIL: {failures}"
    )
    print(f"Artifact: {ARTIFACT}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
