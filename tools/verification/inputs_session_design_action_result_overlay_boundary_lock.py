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
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
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


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Action Result Overlay Boundary Lock",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This lock covers the delegated design-action result overlay surface used by `_resolved_inputs_summary_state`.",
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
            "- Design-action result overlay planning is owned by `inputs_page_modules.session`.",
            "- `inputs_page.py` keeps source/session selection and the compatibility mutation wrapper.",
            "- The old inline loop over `_SUMMARY_DESIGN_ACTION_RESULT_KEYS` is deleted from the page helper.",
            "- Session writes, UX probe, derived recompute, normalized shear truth overlay, callbacks, Apply routing, and rendering remain page-owned.",
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
    bridge = _read(APP_CONTRACT_BRIDGE)
    helper_window = _function_window(page, "_overlay_current_design_action_results_for_summary") or _function_window(
        bridge,
        "_overlay_current_design_action_results_for_summary_for_app_bridge",
    )
    summary_window = _function_window(page, "_resolved_inputs_summary_state") or _function_window(
        bridge,
        "_resolved_inputs_summary_state",
    )
    module_sources = {
        path.name: _read(path)
        for path in SESSION_ROOT.glob("*.py")
    }
    module_combined = "\n".join(module_sources.values())
    executable_module = "\n".join(
        source for name, source in module_sources.items() if name != "contracts.py"
    )

    checks = {
        "builder_exported": "build_inputs_design_action_result_overlay_snapshot" in module_sources.get("__init__.py", ""),
        "model_exported": "InputsDesignActionResultOverlaySnapshot" in module_sources.get("__init__.py", ""),
        "builder_present": "def build_inputs_design_action_result_overlay_snapshot(" in module_sources.get("builders.py", ""),
        "page_imports_builder": "build_inputs_design_action_result_overlay_snapshot" in page
        or "build_inputs_design_action_result_overlay_snapshot" in bridge,
        "summary_calls_page_wrapper": "_overlay_current_design_action_results_for_summary(" in summary_window
        or "_overlay_current_design_action_results_for_summary_for_app_bridge(" in summary_window,
        "page_wrapper_delegates_to_module": "build_inputs_design_action_result_overlay_snapshot(" in helper_window
        and "source = source_state if source_state is not None else st.session_state" in helper_window
        and "result_keys=_SUMMARY_DESIGN_ACTION_RESULT_KEYS" in helper_window,
        "old_inline_loop_deleted": "for key in _SUMMARY_DESIGN_ACTION_RESULT_KEYS:" not in helper_window
        and "working[key] = value" not in helper_window
        and "overlaid[key]" not in helper_window
        and "_summary_state_mapping_get(" not in helper_window,
        "compatibility_mutation_wrapper_retained": "working.clear()" in helper_window
        and ".working_state" in helper_window
        and "overlay_applied.clear()" in helper_window
        and ".overlay_applied" in helper_window,
        "delegated_trace_present": "inputs_summary_design_action_result_overlay_delegated" in helper_window
        and ".display_hash" in helper_window
        and ("live_page_cutover=True" in helper_window or '"live_page_cutover": True' in helper_window),
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
    decision = (
        "INPUTS_SESSION_DESIGN_ACTION_RESULT_OVERLAY_BOUNDARY_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_ACTION_RESULT_OVERLAY_BOUNDARY_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_action_result_overlay_boundary_lock",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "locked_surface": "_overlay_current_design_action_results_for_summary",
        "overlay_owner": "inputs_page_modules.session",
        "page_role": "source/session selector and compatibility mutation wrapper",
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "next_safe_slice": "refresh next-surface audit and extract the next session sub-boundary",
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_action_result_overlay_boundary_lock_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_action_result_overlay_boundary_lock_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_action_result_overlay_boundary_lock", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
