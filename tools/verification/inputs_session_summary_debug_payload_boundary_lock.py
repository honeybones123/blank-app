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
        "# Inputs Session Summary Debug Payload Boundary Lock",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This lock covers delegated compact debug payload assembly inside `_resolved_inputs_summary_state`.",
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
            "- Compact debug payload assembly is owned by `inputs_page_modules.session`.",
            "- `inputs_page.py` supplies resolved state and page-owned fingerprints, then emits trace.",
            "- The old inline `debug_payload = {...}` block is deleted from `_resolved_inputs_summary_state`.",
            "- Session writes, UX probe, derived recompute, normalized shear truth overlay, callbacks, Apply routing, and rendering remain page-owned.",
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
    summary_window = "\n".join(
        window
        for window in (
            _function_window(page, "_resolved_inputs_summary_state"),
            _function_window(bridge, "_resolved_inputs_summary_state"),
            _function_window(summary_resolver, "_resolved_inputs_summary_state"),
        )
        if window
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
        "builder_exported": "build_inputs_summary_debug_payload_snapshot" in module_sources.get("__init__.py", ""),
        "model_exported": "InputsSummaryDebugPayloadSnapshot" in module_sources.get("__init__.py", ""),
        "builder_present": "def build_inputs_summary_debug_payload_snapshot(" in module_sources.get("builders.py", ""),
        "page_imports_builder": "build_inputs_summary_debug_payload_snapshot" in page
        or "build_inputs_summary_debug_payload_snapshot" in bridge
        or "build_inputs_summary_debug_payload_snapshot" in summary_resolver,
        "summary_delegates_to_module": "build_inputs_summary_debug_payload_snapshot(" in summary_window
        and ".debug_payload" in summary_window
        and "design_guide_fingerprint=_get_design_guide_fp(resolved)" in summary_window,
        "delegated_trace_present": "inputs_summary_debug_payload_delegated" in summary_window
        and ".display_hash" in summary_window
        and ("live_page_cutover=True" in summary_window or '"live_page_cutover": True' in summary_window),
        "old_inline_debug_payload_deleted": "debug_payload = {" not in summary_window
        and "compact_diffs: dict[str, dict]" not in summary_window,
        "session_write_still_page_owned": 'st.session_state["_inputs_summary_state_mode"]' in summary_window,
        "ux_probe_still_page_owned": "ux_probe_record(" in summary_window,
        "derived_recompute_still_page_owned": "_recompute_summary_local_derived_fields(working)" in summary_window
        or "_recompute_summary_local_derived_fields_for_app_bridge(working)" in summary_window,
        "normalized_shear_truth_overlay_still_page_owned": "_overlay_current_normalized_shear_truth(resolved)" in summary_window
        or "_overlay_current_normalized_shear_truth_for_app_bridge(resolved)" in summary_window,
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
        "INPUTS_SESSION_SUMMARY_DEBUG_PAYLOAD_BOUNDARY_LOCKED"
        if not failures
        else "INPUTS_SESSION_SUMMARY_DEBUG_PAYLOAD_BOUNDARY_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_summary_debug_payload_boundary_lock",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "locked_surface": "_resolved_inputs_summary_state compact debug payload assembly",
        "debug_payload_owner": "inputs_page_modules.session",
        "page_role": "resolved state provider, page fingerprint provider, trace emitter, session/UX owner",
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "next_safe_slice": "refresh next-surface audit and extract the next session sub-boundary",
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_summary_debug_payload_boundary_lock_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_summary_debug_payload_boundary_lock_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_summary_debug_payload_boundary_lock", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
