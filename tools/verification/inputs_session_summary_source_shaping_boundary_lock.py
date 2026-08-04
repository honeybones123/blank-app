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
SUMMARY_STATE_RESOLVER = ROOT / "inputs_page_modules" / "summaries" / "summary_state_resolver.py"
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
        "# Inputs Session Summary Source Shaping Boundary Lock",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This lock covers the delegated scalar widget-overlay source-shaping surface inside `_resolved_inputs_summary_state`.",
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
            "- Scalar widget-overlay source shaping is owned by `inputs_page_modules.session`.",
            "- `inputs_page.py` calls the builder, copies the returned working state, and emits trace.",
            "- The page-local authoritative scalar overlay loop in `_resolved_inputs_summary_state` is deleted.",
            "- Shear mirror overlay, derived recompute, normalized shear truth overlay, UX probe, session writes, callbacks, Apply routing, and render triggers remain page-owned.",
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _module_inputs_page_free(module_source: str) -> bool:
    return not re.search(r"^\s*(from\s+inputs_page\b|import\s+inputs_page\b)", module_source, re.MULTILINE)


def _module_apply_routing_free(module_source: str) -> bool:
    return not re.search(r"\b(route_apply|apply_payload)\s*[=(]", module_source)


def _module_rendering_free(module_source: str) -> bool:
    return not (
        re.search(r"(?<![A-Za-z0-9_])st\.", module_source)
        or "streamlit" in module_source
        or re.search(r"\b(render_final|render_card)\s*\(", module_source)
    )


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    page = _read(INPUTS_PAGE)
    bridge = _read(APP_CONTRACT_BRIDGE)
    summary_resolver = _read(SUMMARY_STATE_RESOLVER)
    helper_window = "\n".join(
        window
        for window in (
            _function_window(page, "_resolved_inputs_summary_state"),
            _function_window(bridge, "_resolved_inputs_summary_state"),
            _function_window(summary_resolver, "_resolved_inputs_summary_state"),
        )
        if window
    )
    shear_overlay_window = _function_window(page, "_apply_active_page_shear_widget_mirror_overlay") or _function_window(
        bridge,
        "_apply_active_page_shear_widget_mirror_overlay_for_app_bridge",
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
        "session_module_exists": SESSION_ROOT.exists(),
        "builder_exported": "build_inputs_summary_source_shaping_snapshot" in module_sources.get("__init__.py", ""),
        "model_exported": "InputsSummarySourceShapingSnapshot" in module_sources.get("__init__.py", ""),
        "builder_present": "def build_inputs_summary_source_shaping_snapshot(" in module_sources.get("builders.py", ""),
        "page_imports_builder": "build_inputs_summary_source_shaping_snapshot" in page
        or "build_inputs_summary_source_shaping_snapshot" in bridge
        or "build_inputs_summary_source_shaping_snapshot" in summary_resolver,
        "helper_exists": bool(helper_window),
        "helper_delegates_to_module_builder": "build_inputs_summary_source_shaping_snapshot(" in helper_window
        and "base_state=base" in helper_window
        and "source_state=st.session_state" in helper_window
        and "input_tab_keys=INPUTS_PAGE_TAB_KEYS" in helper_window,
        "helper_uses_module_result": ".working_state" in helper_window
        and ".overlay_applied" in helper_window,
        "helper_emits_delegated_trace": "inputs_summary_source_shaping_delegated" in helper_window
        and ".display_hash" in helper_window
        and ("live_page_cutover=True" in helper_window or '"live_page_cutover": True' in helper_window),
        "legacy_scalar_overlay_loop_deleted_from_helper": "for shared_key, widget_key in INPUTS_PAGE_TAB_KEYS.items()" not in helper_window
        and "working[sk] = wval" not in helper_window
        and "overlay_applied[sk]" not in helper_window
        and "inputs_summary_source_shaping_parity_error" not in helper_window,
        "shear_mirror_overlay_still_page_owned": bool(shear_overlay_window)
        and (
            "working[sk] = wval" in shear_overlay_window
            or "build_inputs_shear_widget_mirror_overlay_plan(" in shear_overlay_window
        )
        and (
            "_apply_active_page_shear_widget_mirror_overlay(" in helper_window
            or "_apply_active_page_shear_widget_mirror_overlay_for_app_bridge(" in helper_window
        ),
        "derived_recompute_still_page_owned": "_recompute_summary_local_derived_fields(working)" in helper_window
        or "_recompute_summary_local_derived_fields_for_app_bridge(working)" in helper_window
        and "_recompute_summary_local_derived_fields" not in module_combined,
        "normalized_shear_truth_overlay_still_page_owned": (
            "_overlay_current_normalized_shear_truth(resolved)" in helper_window
            or "_overlay_current_normalized_shear_truth_for_app_bridge(resolved)" in helper_window
        )
        and "_overlay_current_normalized_shear_truth" not in module_combined,
        "session_write_still_page_owned": 'st.session_state["_inputs_summary_state_mode"] = dict(' in helper_window
        and ".marker_payload" in helper_window
        and "overlay_count=len(overlay_applied)" in helper_window
        and "widget_shear_state={" in helper_window,
        "module_streamlit_free": "import streamlit" not in module_combined
        and "from streamlit" not in module_combined,
        "module_inputs_page_free": _module_inputs_page_free(module_combined),
        "module_session_mutation_free": "st.session_state" not in executable_module
        and ".session_state" not in executable_module,
        "module_apply_routing_free": _module_apply_routing_free(executable_module),
        "module_callback_execution_free": "on_change" not in executable_module
        and "sync_callback" not in executable_module,
        "module_rendering_free": _module_rendering_free(executable_module),
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_SUMMARY_SOURCE_SHAPING_BOUNDARY_LOCKED"
        if not failures
        else "INPUTS_SESSION_SUMMARY_SOURCE_SHAPING_BOUNDARY_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_summary_source_shaping_boundary_lock",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "locked_surface": "_resolved_inputs_summary_state scalar widget-overlay source shaping",
        "source_shaping_owner": "inputs_page_modules.session",
        "page_role": "session source provider, trace emitter, and downstream shell/session processing",
        "legacy_scalar_overlay_loop_deleted": checks["legacy_scalar_overlay_loop_deleted_from_helper"],
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "derived_recompute_moved": False,
        "normalized_shear_truth_overlay_moved": False,
        "next_safe_slice": "audit next Session State sub-boundary before extraction",
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_summary_source_shaping_boundary_lock_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_summary_source_shaping_boundary_lock_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_summary_source_shaping_boundary_lock", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
