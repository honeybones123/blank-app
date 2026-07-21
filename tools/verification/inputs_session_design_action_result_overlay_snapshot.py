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
SESSION_ROOT = ROOT / "inputs_page_modules" / "session"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_window(source: str, name: str) -> str:
    marker = f"def {name}("
    if marker not in source:
        return ""
    window = source.split(marker, 1)[1].split("\ndef ", 1)[0]
    return window.split("\n", 1)[1] if "\n" in window else window


def _mapping_get(source: dict[str, Any], key: str, default: Any = None) -> Any:
    try:
        return source.get(key, default)
    except Exception:
        return default


def _legacy_design_action_overlay(
    *,
    working_state: dict[str, Any],
    source_state: dict[str, Any],
    result_keys: tuple[str, ...],
    overlay_applied: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    working = dict(working_state)
    overlay = {
        str(key): dict(value)
        for key, value in dict(overlay_applied or {}).items()
        if isinstance(value, dict)
    }
    source_mode = str(
        _mapping_get(
            source_state,
            "actions_mode",
            working.get("actions_mode", ""),
        )
        or ""
    ).strip().lower()
    working_mode = str(working.get("actions_mode", "") or "").strip().lower()
    if source_mode != "design" and working_mode != "design":
        return working, {}, overlay

    overlaid: dict[str, dict[str, Any]] = {}
    for key in result_keys:
        if _mapping_get(source_state, key, None) is None:
            continue
        value = _mapping_get(source_state, key)
        if isinstance(value, (dict, list, tuple, set)):
            continue
        previous = working.get(key)
        if previous != value:
            overlaid[key] = {
                "from": previous,
                "to": value,
                "source": "design_action_result",
            }
            overlay[key] = dict(overlaid[key])
        working[key] = value
    return working, overlaid, overlay


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Action Result Overlay Snapshot",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This snapshot compares module-owned design-action result overlay planning with the legacy page helper semantics and verifies live delegation.",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- The live page delegates `_overlay_current_design_action_results_for_summary` to `inputs_page_modules.session`.",
            "- Source/session selection, session writes, UX probe, derived recompute, normalized shear truth overlay, callbacks, Apply routing, and rendering remain page-owned.",
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    page = _read(INPUTS_PAGE)
    helper_window = _function_window(page, "_overlay_current_design_action_results_for_summary")
    summary_window = _function_window(page, "_resolved_inputs_summary_state")
    module_sources = {
        path.name: _read(path)
        for path in SESSION_ROOT.glob("*.py")
    }
    module_combined = "\n".join(module_sources.values())
    executable_module = "\n".join(
        source for name, source in module_sources.items() if name != "contracts.py"
    )

    from inputs_page_modules.session import build_inputs_design_action_result_overlay_snapshot

    result_keys = (
        "uls_Mstar",
        "Mu_star",
        "uls_Vstar",
        "Vu_star",
        "Tu_star",
        "crack_Ms",
    )
    scenarios = [
        {
            "name": "design_mode_overlays_scalar_results",
            "working": {"actions_mode": "design", "uls_Mstar": 100.0, "Mu_star": 110.0},
            "source": {"actions_mode": "design", "uls_Mstar": 125.0, "Mu_star": 110.0, "uls_Vstar": 70.0},
            "overlay": {"b": {"from": 300, "to": 350, "widget_key": "inputs_b"}},
        },
        {
            "name": "manual_mode_no_overlay",
            "working": {"actions_mode": "manual", "uls_Mstar": 100.0},
            "source": {"actions_mode": "manual", "uls_Mstar": 125.0},
            "overlay": {},
        },
        {
            "name": "working_design_mode_source_missing_mode",
            "working": {"actions_mode": "design", "uls_Vstar": 55.0},
            "source": {"uls_Vstar": 90.0},
            "overlay": {},
        },
        {
            "name": "non_scalar_values_skipped",
            "working": {"actions_mode": "design", "Vu_star": 12.0, "Tu_star": 1.0},
            "source": {"actions_mode": "design", "Vu_star": {"skip": True}, "Tu_star": [2.0]},
            "overlay": {},
        },
    ]
    scenario_results: list[dict[str, Any]] = []
    for scenario in scenarios:
        legacy_working, legacy_result_overlay, legacy_overlay = _legacy_design_action_overlay(
            working_state=scenario["working"],
            source_state=scenario["source"],
            result_keys=result_keys,
            overlay_applied=scenario["overlay"],
        )
        module_snapshot = build_inputs_design_action_result_overlay_snapshot(
            working_state=scenario["working"],
            source_state=scenario["source"],
            result_keys=result_keys,
            overlay_applied=scenario["overlay"],
        )
        scenario_results.append(
            {
                "name": scenario["name"],
                "working_matches": module_snapshot.working_state == legacy_working,
                "result_overlay_matches": module_snapshot.result_overlay == legacy_result_overlay,
                "overlay_applied_matches": module_snapshot.overlay_applied == legacy_overlay,
                "module_display_hash": module_snapshot.display_hash,
            }
        )

    checks = {
        "builder_exported": "build_inputs_design_action_result_overlay_snapshot" in module_sources.get("__init__.py", ""),
        "model_exported": "InputsDesignActionResultOverlaySnapshot" in module_sources.get("__init__.py", ""),
        "builder_present": "def build_inputs_design_action_result_overlay_snapshot(" in module_sources.get("builders.py", ""),
        "page_helper_delegates_to_module_builder": "_overlay_current_design_action_results_for_summary(" in summary_window
        and "build_inputs_design_action_result_overlay_snapshot(" in helper_window
        and "source = source_state if source_state is not None else st.session_state" in helper_window
        and "result_keys=_SUMMARY_DESIGN_ACTION_RESULT_KEYS" in helper_window,
        "page_inline_overlay_loop_deleted": "for key in _SUMMARY_DESIGN_ACTION_RESULT_KEYS:" not in helper_window
        and "working[key] = value" not in helper_window
        and "overlaid[key]" not in helper_window,
        "page_helper_preserves_mutation_contract": "working.clear()" in helper_window
        and "working.update(dict(_design_action_overlay.working_state))" in helper_window
        and "overlay_applied.update(dict(_design_action_overlay.overlay_applied))" in helper_window,
        "page_helper_emits_delegated_trace": "inputs_summary_design_action_result_overlay_delegated" in helper_window
        and "live_page_cutover=True" in helper_window,
        "all_scenarios_match": all(
            row["working_matches"] and row["result_overlay_matches"] and row["overlay_applied_matches"]
            for row in scenario_results
        ),
        "module_streamlit_free": "import streamlit" not in module_combined
        and "from streamlit" not in module_combined,
        "module_inputs_page_free": "import inputs_page" not in executable_module
        and "from inputs_page" not in executable_module,
        "module_session_mutation_free": "st.session_state" not in executable_module
        and ".session_state" not in executable_module,
        "module_apply_routing_free": "apply_guidance_action(" not in executable_module
        and "_apply_resolved_candidate_payload(" not in executable_module
        and "route_apply(" not in executable_module,
        "module_callback_execution_free": "on_change" not in executable_module
        and "sync_callback" not in executable_module,
        "module_rendering_free": not re.search(r"\bst\.", executable_module)
        and not re.search(r"(?m)^\s*(import|from)\s+streamlit\b", executable_module),
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "SESSION_DESIGN_ACTION_RESULT_OVERLAY_DELEGATED" if not failures else "SESSION_DESIGN_ACTION_RESULT_OVERLAY_GAPS_REMAIN"
    payload = {
        "audit": "inputs_session_design_action_result_overlay_snapshot",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "scenarios": scenario_results,
        "live_page_cutover": True,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "next_safe_slice": "add/refresh boundary lock, then audit the next Session State sub-boundary",
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_action_result_overlay_snapshot_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_action_result_overlay_snapshot_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_action_result_overlay_snapshot", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
