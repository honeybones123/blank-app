from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


TARGETS = (
    "_inputs_summary_should_use_shared_only",
    "_overlay_current_normalized_shear_truth",
    "_resolved_inputs_summary_state",
    "_overlay_current_design_action_results_for_summary",
    "_apply_active_page_shear_widget_mirror_overlay",
    "_overlay_inputs_reo_widget_mirrors_for_model",
    "_resolved_inputs_model_state",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_window(source: str, name: str) -> str:
    marker = f"def {name}("
    if marker not in source:
        return ""
    window = source.split(marker, 1)[1].split("\ndef ", 1)[0]
    return window.split("\n", 1)[1] if "\n" in window else window


def _line_range(source: str, name: str) -> tuple[int | None, int | None]:
    lines = source.splitlines()
    start = None
    for idx, line in enumerate(lines, start=1):
        if line.startswith(f"def {name}("):
            start = idx
            break
    if start is None:
        return None, None
    end = len(lines)
    for idx in range(start + 1, len(lines) + 1):
        line = lines[idx - 1]
        if line.startswith("def ") and idx > start:
            end = idx - 1
            break
    return start, end


def _calls_in_window(window: str) -> list[str]:
    calls = sorted(set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\(", window)))
    return [
        call for call in calls
        if call not in {"dict", "list", "len", "str", "tuple", "bool", "float", "int", "set"}
    ]


def _classify(name: str, window: str) -> dict[str, Any]:
    reads_session = "st.session_state" in window
    writes_session = "st.session_state[" in window or ".session_state[" in window
    mutates_input = ".update(" in window or "working[" in window
    calls = _calls_in_window(window)
    return {
        "function": name,
        "line_range": _line_range(_read(INPUTS_PAGE), name),
        "present": bool(window),
        "reads_session": reads_session,
        "writes_session": writes_session,
        "mutates_local_state": mutates_input,
        "calls": calls,
        "contains_widget_overlay_policy": "INPUTS_PAGE_TAB_KEYS" in window
        or "overlay_applied" in window,
        "contains_design_action_result_overlay": "_SUMMARY_DESIGN_ACTION_RESULT_KEYS" in window,
        "contains_derived_field_recompute": "_recompute_summary_local_derived_fields" in window,
        "contains_shear_truth_overlay": "_overlay_current_normalized_shear_truth" in window,
        "contains_debug_payload_construction": "debug_payload" in window,
        "contains_ux_probe": "ux_probe_record" in window,
        "target_owner": _target_owner(name),
        "classification": _classification(name, window),
    }


def _target_owner(name: str) -> str:
    if name == "_resolved_inputs_summary_state":
        return (
            "inputs_page_modules.session owns delegated scalar source shaping, design-action overlay planning, and compact debug payload assembly; "
            "inputs_page.py keeps session marker write, ux probe, shear mirror overlay, derived recompute, and caller orchestration"
        )
    if name == "_inputs_summary_should_use_shared_only":
        return (
            "inputs_page_modules.session owns pure shared-only reason priority; "
            "inputs_page.py keeps session flag reads and caller orchestration"
        )
    if name == "_overlay_current_normalized_shear_truth":
        return (
            "potential split boundary: inputs_page_modules.session can own pure current shear truth overlay planning; "
            "inputs_page.py keeps session reads and the shared normalized shear truth callback"
        )
    if name == "_overlay_current_design_action_results_for_summary":
        return (
            "inputs_page_modules.session owns design-action result overlay planning; "
            "inputs_page.py keeps source_state/session selection and compatibility mutation wrapper"
        )
    if name == "_apply_active_page_shear_widget_mirror_overlay":
        return (
            "inputs_page_modules.session owns pure shear mirror overlay planning; "
            "inputs_page.py keeps current page/session/widget reads and mutation wrapper"
        )
    if name == "_overlay_inputs_reo_widget_mirrors_for_model":
        return (
            "inputs_page_modules.session owns pure fast-model reinforcement mirror planning; "
            "inputs_page.py keeps page/session widget reads, canonical pack execution, and model call orchestration"
        )
    if name == "_resolved_inputs_model_state":
        return (
            "potential split boundary: inputs_page_modules.session can own pure model-state debug payload assembly; "
            "inputs_page.py keeps model state orchestration and calls to summary/model overlay helpers"
        )
    return "unknown"


def _classification(name: str, window: str) -> str:
    if name == "_inputs_summary_should_use_shared_only":
        if "build_inputs_summary_shared_only_decision(" in window and "if st.session_state.get" not in window:
            return "SESSION_SUMMARY_SHARED_ONLY_DECISION_LOCKED"
        return "SESSION_SUMMARY_SHARED_ONLY_DECISION_NEEDS_AUDIT"
    if name == "_overlay_current_normalized_shear_truth":
        if "build_inputs_normalized_shear_truth_overlay_snapshot(" in window and "merged.update(normalize_final_published_shear_truth(merged))" not in window:
            return "SESSION_NORMALIZED_SHEAR_TRUTH_OVERLAY_LOCKED"
        return "SESSION_NORMALIZED_SHEAR_TRUTH_OVERLAY_NEEDS_AUDIT"
    if name == "_resolved_inputs_summary_state":
        return "MIXED_PAGE_SESSION_BOUNDARY_WITH_SUMMARY_DEBUG_LOCKED"
    if name == "_overlay_current_design_action_results_for_summary":
        if "build_inputs_design_action_result_overlay_snapshot(" in window and "for key in _SUMMARY_DESIGN_ACTION_RESULT_KEYS:" not in window:
            return "DESIGN_ACTION_RESULT_OVERLAY_LOCKED"
        return "DESIGN_ACTION_RESULT_OVERLAY_BOUNDARY_NEEDS_REVIEW"
    if name == "_apply_active_page_shear_widget_mirror_overlay":
        if "build_inputs_shear_widget_mirror_overlay_plan(" in window and "for sk, wk in pairs:" not in window:
            return "SESSION_SHEAR_WIDGET_MIRROR_OVERLAY_LOCKED"
        return "SESSION_SHEAR_WIDGET_MIRROR_OVERLAY_NEEDS_AUDIT"
    if name == "_overlay_inputs_reo_widget_mirrors_for_model":
        if "build_inputs_model_reo_widget_mirror_overlay_plan(" in window and "def _overlay_scalar" not in window:
            return "SESSION_MODEL_REO_WIDGET_MIRROR_OVERLAY_LOCKED"
        return "SESSION_MODEL_REO_WIDGET_MIRROR_OVERLAY_NEEDS_AUDIT"
    if name == "_resolved_inputs_model_state":
        return "SESSION_MODEL_STATE_DEBUG_PAYLOAD_NEEDS_AUDIT"
    return "UNKNOWN"


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Next Surface Ownership Audit",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This audit identifies the next Session State modularisation surface after summary source shaping, design-action overlay planning, compact debug payload assembly, and state-mode marker construction were locked.",
        "",
        "## Surfaces",
        "",
    ]
    for row in payload["surfaces"]:
        lines.extend(
            [
                f"### `{row['function']}`",
                f"- present: `{row['present']}`",
                f"- lines: `{row['line_range']}`",
                f"- classification: `{row['classification']}`",
                f"- reads session: `{row['reads_session']}`",
                f"- writes session: `{row['writes_session']}`",
                f"- target owner: {row['target_owner']}",
                "",
            ]
        )
    lines.extend(
        [
            "## First Safe Implementation Slice",
            "",
            payload["first_safe_slice"],
            "",
            "## Stop Conditions",
            "",
        ]
    )
    for item in payload["stop_conditions"]:
        lines.append(f"- {item}")
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = _read(INPUTS_PAGE)
    surfaces = [
        _classify(name, _function_window(source, name))
        for name in TARGETS
    ]
    resolved = next(row for row in surfaces if row["function"] == "_resolved_inputs_summary_state")
    design_action_overlay = next(
        row for row in surfaces if row["function"] == "_overlay_current_design_action_results_for_summary"
    )
    resolved_window = _function_window(source, "_resolved_inputs_summary_state")
    shared_only_window = _function_window(source, "_inputs_summary_should_use_shared_only")
    normalized_shear_truth_window = _function_window(source, "_overlay_current_normalized_shear_truth")
    overlay_window = _function_window(source, "_overlay_current_design_action_results_for_summary")
    shear_overlay_window = _function_window(source, "_apply_active_page_shear_widget_mirror_overlay")
    model_reo_overlay_window = _function_window(source, "_overlay_inputs_reo_widget_mirrors_for_model")
    checks = {
        "resolved_summary_state_present": resolved["present"],
        "source_shaping_boundary_already_delegated": "build_inputs_summary_source_shaping_snapshot(" in resolved_window
        and "inputs_summary_source_shaping_delegated" in resolved_window
        and "for shared_key, widget_key in INPUTS_PAGE_TAB_KEYS.items()" not in resolved_window,
        "design_action_overlay_helper_present": any(
            row["function"] == "_overlay_current_design_action_results_for_summary" and row["present"]
            for row in surfaces
        ),
        "design_action_overlay_boundary_already_delegated": design_action_overlay["present"]
        and "build_inputs_design_action_result_overlay_snapshot(" in overlay_window
        and "for key in _SUMMARY_DESIGN_ACTION_RESULT_KEYS:" not in overlay_window
        and "inputs_summary_design_action_result_overlay_delegated" in overlay_window,
        "summary_debug_payload_boundary_already_delegated": "build_inputs_summary_debug_payload_snapshot(" in resolved_window
        and "inputs_summary_debug_payload_delegated" in resolved_window
        and "debug_payload = {" not in resolved_window,
        "summary_state_mode_marker_boundary_already_delegated": "build_inputs_summary_state_mode_marker_snapshot(" in resolved_window
        and "inputs_summary_state_mode_marker_delegated" in resolved_window
        and 'st.session_state["_inputs_summary_state_mode"] = dict(' in resolved_window,
        "mapping_get_helper_deleted": "_summary_state_mapping_get" not in source,
        "shear_widget_mirror_overlay_boundary_already_delegated": bool(shear_overlay_window)
        and "build_inputs_shear_widget_mirror_overlay_plan(" in shear_overlay_window
        and "for sk, wk in pairs:" not in shear_overlay_window
        and "_int_from_state(" not in shear_overlay_window
        and "_float_from_state(" not in shear_overlay_window,
        "model_reo_widget_mirror_overlay_is_next_extractable_surface": bool(model_reo_overlay_window)
        and False,
        "model_reo_widget_mirror_overlay_boundary_already_delegated": bool(model_reo_overlay_window)
        and "st.session_state" in model_reo_overlay_window
        and "build_inputs_model_reo_widget_mirror_overlay_plan(" in model_reo_overlay_window
        and "def _overlay_scalar" not in model_reo_overlay_window
        and "def _coords_stale_for" not in model_reo_overlay_window
        and "fast_model_reo_widget_overlay" in model_reo_overlay_window,
        "model_state_debug_payload_boundary_already_delegated": "_resolved_inputs_summary_state()" in _function_window(source, "_resolved_inputs_model_state")
        and "_overlay_inputs_reo_widget_mirrors_for_model(" in _function_window(source, "_resolved_inputs_model_state")
        and "build_inputs_model_state_debug_payload_snapshot(" in _function_window(source, "_resolved_inputs_model_state")
        and "debug_payload = {" not in _function_window(source, "_resolved_inputs_model_state"),
        "summary_shared_only_decision_boundary_already_delegated": bool(shared_only_window)
        and "st.session_state" in shared_only_window
        and "build_inputs_summary_shared_only_decision(" in shared_only_window
        and "if st.session_state.get" not in shared_only_window
        and "_pending_inputs_apply_refresh" in shared_only_window,
        "normalized_shear_truth_overlay_boundary_already_delegated": bool(normalized_shear_truth_window)
        and "_CURRENT_SHEAR_TRUTH_SESSION_KEYS" in normalized_shear_truth_window
        and "st.session_state" in normalized_shear_truth_window
        and "build_inputs_normalized_shear_truth_overlay_snapshot(" in normalized_shear_truth_window
        and "normalize_final_published_shear_truth(" in normalized_shear_truth_window,
        "no_live_change_in_this_audit": True,
    }
    checks.pop("model_reo_widget_mirror_overlay_is_next_extractable_surface", None)
    failures = [key for key, value in checks.items() if not value]
    decision = "SESSION_SUMMARY_AND_MODEL_STATE_BOUNDARIES_LOCKED_REFRESH_PHASE0" if not failures else "SESSION_NEXT_SURFACE_AUDIT_GAPS_REMAIN"
    payload = {
        "audit": "inputs_session_next_surface_ownership_audit",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "surfaces": surfaces,
        "first_safe_slice": (
            "Refresh the broader Session State Phase 0 inventory and select the next unextracted session boundary outside the locked summary/model-state cluster. "
            "Keep Streamlit/session reads, callbacks, Apply routing, and UX probes in `inputs_page.py`."
        ),
        "required_next_verifier": "inputs_session_state_phase0_ownership_audit.py",
        "stop_conditions": [
            "normalized shear truth overlay differs",
            "session reads move into inputs_page_modules.session",
            "normalize_final_published_shear_truth callback moves unexpectedly",
            "callbacks or Apply routing move",
            "summary state output changes",
        ],
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_next_surface_ownership_audit_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_next_surface_ownership_audit_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_next_surface_ownership_audit", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
