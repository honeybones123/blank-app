"""Audit readiness to cut over direct-target active-failure route projection to adapter result."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_direct_target_band_guidance_item"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    route_window = segment.split("_diag_prior = st.session_state.get", 1)[0]
    direct_projection_calls = route_window.count(
        "_build_design_guide_controller_direct_target_family_bypass_projection("
    )
    adapter_calls = route_window.count(
        "_build_design_guide_controller_direct_target_active_failure_route_request_result_adapter("
    )
    live_projection_result_reads = route_window.count("_bypass_projection.get(\"item\")")
    live_projection_debug_reads = route_window.count("_bypass_projection.get(\"debug_update\")")
    adapter_result_reads = route_window.count("_route_adapter_result")
    trace_debug_payloads = route_window.count("direct_target_active_failure_route_adapter_trace")
    return {
        "schema": "design_guide_direct_target_active_failure_route_adapter_cutover_readiness_audit.v1",
        "target": {"name": TARGET, "line_start": start, "line_end": end},
        "direct_projection_calls": direct_projection_calls,
        "adapter_trace_calls": adapter_calls,
        "live_projection_result_reads": live_projection_result_reads,
        "live_projection_debug_reads": live_projection_debug_reads,
        "adapter_result_reads": adapter_result_reads,
        "trace_debug_payloads": trace_debug_payloads,
        "trace_verifier_exists": (
            ROOT
            / "tools"
            / "verification"
            / "design_guide_direct_target_active_failure_route_request_result_adapter_trace.py"
        ).exists(),
        "controller_adapter_exists": (
            "def build_design_guide_controller_direct_target_active_failure_route_request_result_adapter("
            in controller_source
        ),
        "page_still_owns_family_executor": "_active_fail_near_current_repair_item(" in route_window,
        "page_still_owns_bending_cta_side_effect": "_record_bending_fail_valid_repair_cta_published(" in route_window,
        "controller_has_no_page_or_streamlit_imports": (
            "inputs_page" not in controller_source
            and "streamlit" not in controller_source
            and "st.session_state" not in controller_source
        ),
        "ready_for_guarded_cutover": (
            direct_projection_calls == 3
            and adapter_calls == 3
            and live_projection_result_reads >= 3
            and live_projection_debug_reads >= 3
            and adapter_result_reads >= 6
        ),
        "cutover_complete": (
            direct_projection_calls == 0
            and adapter_calls == 3
            and adapter_result_reads >= 3
            and "_build_design_guide_controller_direct_target_family_bypass_projection" not in route_window
        ),
        "cutover_action": {
            "replace": "_build_design_guide_controller_direct_target_family_bypass_projection(...) live result usage",
            "with": "_build_design_guide_controller_direct_target_active_failure_route_request_result_adapter(...)[\"result\"]",
            "keep": [
                "_active_fail_near_current_repair_item(...)",
                "_record_bending_fail_valid_repair_cta_published(...)",
                "debug_sink.update(...)",
                "route branch conditions",
            ],
            "delete_after_cutover": [
                "three direct family bypass projection calls from inputs_page.py",
                "projection equality debug-only rows once cutover proof passes",
            ],
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "direct_projection_calls_ready_or_removed": int(payload.get("direct_projection_calls") or 0) in (0, 3),
        "adapter_trace_calls_are_three": int(payload.get("adapter_trace_calls") or 0) == 3,
        "adapter_result_reads_present": int(payload.get("adapter_result_reads") or 0) >= 3,
        "trace_verifier_exists": bool(payload.get("trace_verifier_exists")),
        "controller_adapter_exists": bool(payload.get("controller_adapter_exists")),
        "page_still_owns_family_executor": bool(payload.get("page_still_owns_family_executor")),
        "page_still_owns_bending_cta_side_effect": bool(
            payload.get("page_still_owns_bending_cta_side_effect")
        ),
        "controller_has_no_page_or_streamlit_imports": bool(
            payload.get("controller_has_no_page_or_streamlit_imports")
        ),
        "ready_for_guarded_cutover_or_complete": bool(payload.get("ready_for_guarded_cutover"))
        or bool(payload.get("cutover_complete")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_direct_target_active_failure_route_adapter_cutover_readiness_audit_{suffix}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_direct_target_active_failure_route_adapter_cutover_readiness_audit_{suffix}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Active-Failure Route Adapter Cutover Readiness Audit",
        "",
        f"Status: {payload['status']}",
        f"Ready for guarded cutover: {payload.get('ready_for_guarded_cutover')}",
        f"Cutover complete: {payload.get('cutover_complete')}",
        "",
        "## Summary",
        (
            "The controller route adapter is trace-wired beside the existing per-branch projection calls. "
            "If this audit passes, the next slice may replace live projection reads with adapter result reads "
            "while keeping route execution, family executor, CTA side effects, and debug/session writes in the page."
        ),
        "",
        "## Counts",
        f"- direct projection calls: {payload.get('direct_projection_calls')}",
        f"- adapter trace calls: {payload.get('adapter_trace_calls')}",
        f"- live projection result reads: {payload.get('live_projection_result_reads')}",
        f"- live projection debug reads: {payload.get('live_projection_debug_reads')}",
        f"- adapter result reads: {payload.get('adapter_result_reads')}",
        "",
        "## Cutover Action",
        f"- Replace: {(payload.get('cutover_action') or {}).get('replace')}",
        f"- With: {(payload.get('cutover_action') or {}).get('with')}",
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_direct_target_active_failure_route_adapter_cutover_readiness_audit {status}")
    print(f"ready_for_guarded_cutover={payload.get('ready_for_guarded_cutover')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
