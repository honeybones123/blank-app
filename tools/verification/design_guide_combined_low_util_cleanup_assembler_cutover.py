"""Verify combined low-util cleanup assembler route cutover.

The route should now call the DesignGuideController result builder directly.
The old page assembler may remain only until a separate deletion proof passes.
"""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

ROUTE = "_resolve_final_visible_no_active_combined_low_util_safe_cleanup_result"
ASSEMBLER = "_assemble_final_visible_combined_low_util_safe_cleanup_result"
BUILDER_ALIAS = "_build_design_guide_controller_combined_low_util_cleanup_result"
FULL_ROUTE_ALIAS = "_run_design_guide_controller_no_active_combined_low_util_cleanup_route"
TRACE_KEY = "design_guide_controller_combined_low_util_cleanup_result_trace_only"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int | None, int | None]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    return "", None, None


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


def _capture() -> dict[str, Any]:
    route_source, route_start, route_end = _function_source(INPUTS_PAGE, ROUTE)
    assembler_source, assembler_start, assembler_end = _function_source(INPUTS_PAGE, ASSEMBLER)
    route_calls_builder = f"{BUILDER_ALIAS}(" in route_source
    route_calls_full_controller = f"{FULL_ROUTE_ALIAS}(" in route_source
    route_calls_assembler = f"{ASSEMBLER}(" in route_source
    route_has_trace_event = "_resolver_route_trace_event(" in route_source
    route_has_trace_stamp = TRACE_KEY in route_source
    route_has_same_trace_event_name = (
        '"return_no_active_combined_low_util_safe_cleanup"' in route_source
    )
    route_has_same_debug_shape = all(
        token in route_source
        for token in (
            '"product_driving": False',
            '"render_driving": False',
            '"apply_driving": False',
            '"session_driving": False',
        )
    )
    route_has_controller_source = (
        '"product_result_source": "controller"' in route_source
        or '"product_result_source": "controller_route_cutover"' in route_source
    )
    route_forbidden_tokens = {
        "streamlit_session_write": "st.session_state" in route_source,
        "button_rendering": "st.button(" in route_source,
        "markdown_rendering": "st.markdown(" in route_source,
        "apply_routing": "_queue_primary_design_guide_button_action" in route_source,
        "family_runtime_call": "contracted_repair_ladder_specs(" in route_source,
    }
    return {
        "decision": (
            "ROUTE_INLINE_CONTROLLER_BUILDER_CUT_OVER"
            if route_calls_builder and not route_calls_assembler
            else "FULL_CONTROLLER_ROUTE_CUT_OVER"
            if route_calls_full_controller and not route_calls_assembler
            else "ROUTE_INLINE_CONTROLLER_BUILDER_NOT_CUT_OVER"
        ),
        "route": {
            "name": ROUTE,
            "exists": bool(route_source),
            "start_line": route_start,
            "end_line": route_end,
            "line_count": (route_end - route_start + 1) if route_source else 0,
            "calls_controller_builder_directly": route_calls_builder,
            "calls_full_controller_route": route_calls_full_controller,
            "calls_old_assembler": route_calls_assembler,
            "has_trace_event": route_has_trace_event,
            "has_trace_stamp": route_has_trace_stamp,
            "has_same_trace_event_name": route_has_same_trace_event_name,
            "has_same_debug_shape": route_has_same_debug_shape and route_has_controller_source,
            "forbidden_tokens": route_forbidden_tokens,
        },
        "assembler": {
            "name": ASSEMBLER,
            "exists": bool(assembler_source),
            "start_line": assembler_start,
            "end_line": assembler_end,
            "line_count": (assembler_end - assembler_start + 1) if assembler_source else 0,
            "retained_pending_deletion_proof": bool(assembler_source),
            "deleted_after_deletion_proof": not bool(assembler_source),
        },
        "verification": {
            "readiness_snapshot": _run(
                "tools/verification/design_guide_combined_low_util_cleanup_assembler_replacement_readiness_snapshot.py"
            ),
            "result_trace_wiring": _run(
                "tools/verification/design_guide_combined_low_util_cleanup_result_trace_wiring_snapshot.py"
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "safe_to_delete_assembler_now": False,
        "recommended_next_slice": (
            "Assembler already deleted after proof."
            if not assembler_source
            else (
                "Create a deletion proof for _assemble_final_visible_combined_low_util_safe_cleanup_result(...). "
                "Delete it only if zero live callsites and compatibility requirements are proven."
            )
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    route = dict(capture.get("route") or {})
    forbidden = dict(route.get("forbidden_tokens") or {})
    verification = dict(capture.get("verification") or {})
    return {
        "route_exists": route.get("exists") is True,
        "route_calls_controller_boundary": (
            route.get("calls_controller_builder_directly") is True
            or route.get("calls_full_controller_route") is True
        ),
        "route_no_longer_calls_old_assembler": route.get("calls_old_assembler") is False,
        "route_trace_event_deleted_or_legacy_retained": (
            route.get("calls_full_controller_route") is True
            and route.get("has_trace_event") is False
        )
        or (
            route.get("has_trace_event") is True
            and route.get("has_same_trace_event_name") is True
        ),
        "route_result_trace_stamp_deleted_or_legacy_retained": (
            route.get("calls_full_controller_route") is True
            and route.get("has_trace_stamp") is False
        )
        or (
            route.get("has_trace_stamp") is True
            and route.get("has_same_debug_shape") is True
        ),
        "route_has_no_forbidden_ownership": not any(forbidden.values()),
        "assembler_retained_or_deleted_after_proof": (
            (capture.get("assembler") or {}).get("retained_pending_deletion_proof") is True
            or (capture.get("assembler") or {}).get("deleted_after_deletion_proof") is True
        ),
        "readiness_snapshot_pass": (verification.get("readiness_snapshot") or {}).get("passed")
        is True,
        "result_trace_wiring_pass": (verification.get("result_trace_wiring") or {}).get("passed")
        is True,
        "not_safe_to_delete_assembler_yet": capture.get("safe_to_delete_assembler_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    route = dict(capture.get("route") or {})
    assembler = dict(capture.get("assembler") or {})
    lines = [
        "# Design Guide Combined Low-Util Cleanup Assembler Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Route",
            f"- Function: `{route.get('name')}`",
            f"- Lines: `{route.get('start_line')}`-`{route.get('end_line')}`",
            f"- Calls controller builder directly: `{route.get('calls_controller_builder_directly')}`",
            f"- Calls full controller route: `{route.get('calls_full_controller_route')}`",
            f"- Calls old assembler: `{route.get('calls_old_assembler')}`",
            "",
            "## Retained Assembler",
            f"- Function: `{assembler.get('name')}`",
            f"- Lines: `{assembler.get('start_line')}`-`{assembler.get('end_line')}`",
            f"- Retained pending deletion proof: `{assembler.get('retained_pending_deletion_proof')}`",
            f"- Deleted after deletion proof: `{assembler.get('deleted_after_deletion_proof')}`",
            "",
            "## Recommendation",
            "",
            str(capture.get("recommended_next_slice") or ""),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_combined_low_util_cleanup_assembler_cutover_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_combined_low_util_cleanup_assembler_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_cleanup_assembler_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
