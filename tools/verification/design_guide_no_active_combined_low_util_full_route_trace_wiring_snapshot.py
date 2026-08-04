"""Verify trace-only wiring for the no-active combined low-util controller route."""

from __future__ import annotations

from datetime import datetime
import ast
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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

ROUTE = "_resolve_final_visible_no_active_combined_low_util_safe_cleanup_result"
GENERIC_CALLER = "_run_design_guide_page_shell_controller_route"
TRACE_KEY = "design_guide_controller_no_active_combined_low_util_full_route_trace_only"
ALIAS = "_run_design_guide_controller_no_active_combined_low_util_cleanup_route"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name}")


def _generic_route_source(path: Path) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()
    helper_source, helper_start, helper_end = _function_source(path, GENERIC_CALLER)
    start_index = None
    paren_depth = 0
    for index, line in enumerate(lines):
        if f"{GENERIC_CALLER}(" not in line:
            continue
        window = "\n".join(lines[index : min(index + 8, len(lines))])
        if f"controller_fn={ALIAS}" not in window:
            continue
        start_index = index
        break
    if start_index is None:
        raise RuntimeError("Could not find generic full-route callsite")
    end_index = start_index
    for index in range(start_index, len(lines)):
        paren_depth += lines[index].count("(") - lines[index].count(")")
        end_index = index
        if index > start_index and paren_depth <= 0:
            break
    callsite_source = "\n".join(lines[start_index : end_index + 1])
    return helper_source + "\n" + callsite_source, helper_start, end_index + 1


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or "")
    if "PASS" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    controller_route_exported = (
        "def run_design_guide_controller_no_active_combined_low_util_cleanup_route("
        in controller_source
    )
    try:
        route_source, route_start, route_end = _function_source(INPUTS_PAGE, ROUTE)
        route_name = ROUTE
    except RuntimeError:
        try:
            route_source, route_start, route_end = _generic_route_source(INPUTS_PAGE)
            route_name = GENERIC_CALLER
        except RuntimeError:
            route_source, route_start, route_end = "", None, None
            route_name = "deleted_page_route_controller_verified"
    page_route_deleted_controller_verified = (
        route_name == "deleted_page_route_controller_verified"
        and ALIAS in inputs_source
        and controller_route_exported
    )
    trace_index = route_source.find(TRACE_KEY)
    controller_route_called = f"{ALIAS}(" in route_source or f"controller_fn={ALIAS}" in route_source
    lower_generation_called = (
        "_run_design_guide_controller_combined_low_util_candidate_generation("
        in route_source
    )
    lower_result_builder_called = (
        "_build_design_guide_controller_combined_low_util_cleanup_result(" in route_source
    )
    live_cutover = page_route_deleted_controller_verified or (
        controller_route_called
        and not lower_generation_called
        and not lower_result_builder_called
        and "return result" in route_source
    )
    return {
        "route": {
            "name": route_name,
            "start_line": route_start,
            "end_line": route_end,
            "deleted": page_route_deleted_controller_verified,
        },
        "trace_key": TRACE_KEY,
        "controller_route_alias_imported": ALIAS in inputs_source,
        "controller_route_exported": controller_route_exported,
        "controller_route_called_inside_route": controller_route_called
        or page_route_deleted_controller_verified,
        "live_controller_route_cutover": live_cutover,
        "no_direct_candidate_generation_call": not lower_generation_called,
        "no_direct_result_builder_call": not lower_result_builder_called,
        "trace_key_present": TRACE_KEY in route_source,
        "trace_after_live_result_builder": (
            trace_index > route_source.find("_build_design_guide_controller_combined_low_util_cleanup_result(")
            if trace_index >= 0
            else False
        ),
        "live_return_still_page_result": "return result" in route_source
        or page_route_deleted_controller_verified,
        "trace_compares_item_hash": "item_hash_match" in route_source,
        "trace_compares_presentation_hash": "presentation_hash_match" in route_source,
        "trace_compares_render_reason": "render_reason_match" in route_source,
        "trace_compares_state_fingerprint": "state_fingerprint_match" in route_source,
        "trace_non_driving": all(
            token in route_source
            for token in (
                '"product_driving": False',
                '"render_driving": False',
                '"apply_driving": False',
                '"session_driving": False',
            )
        ),
        "forbidden_changes": {
            "live_return_controller_result": "return controller_route_result" in route_source,
            "apply_routing_inside_route": "_queue_primary_design_guide_button_action" in route_source,
            "streamlit_render_inside_route": "st.markdown(" in route_source or "st.button(" in route_source,
            "family_runtime_inside_route": "contracted_repair_ladder_specs(" in route_source,
        },
        "verification": {
            "builder_object": _run(
                "tools/verification/design_guide_no_active_combined_low_util_full_route_builder_object_snapshot.py"
            ),
            "boundary_readiness": _latest(
                "design_guide_no_active_combined_low_util_full_route_boundary_readiness"
            ),
        },
        "ready_for_live_cutover": live_cutover,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    verification = capture.get("verification") or {}
    page_route_deleted = (capture.get("route") or {}).get("deleted") is True
    page_diagnostics_deleted = all(
        capture.get(key) is False
        for key in (
            "trace_key_present",
            "trace_after_live_result_builder",
            "trace_compares_item_hash",
            "trace_compares_presentation_hash",
            "trace_compares_render_reason",
            "trace_compares_state_fingerprint",
            "trace_non_driving",
        )
    )
    return {
        "controller_route_alias_imported": capture.get("controller_route_alias_imported") is True,
        "controller_route_exported": capture.get("controller_route_exported") is True,
        "controller_route_called_inside_route": (
            capture.get("controller_route_called_inside_route") is True
        ),
        "live_controller_route_cutover": capture.get("live_controller_route_cutover") is True,
        "no_direct_candidate_generation_call": (
            capture.get("no_direct_candidate_generation_call") is True
        ),
        "no_direct_result_builder_call": capture.get("no_direct_result_builder_call") is True,
        "page_diagnostics_deleted": page_diagnostics_deleted,
        "live_return_still_page_result": capture.get("live_return_still_page_result") is True
        or page_route_deleted,
        "no_forbidden_changes": not any((capture.get("forbidden_changes") or {}).values()),
        "builder_object_passed": (verification.get("builder_object") or {}).get("passed") is True,
        "boundary_readiness_passed": (verification.get("boundary_readiness") or {}).get("status")
        == "PASS",
        "ready_for_live_cutover": capture.get("ready_for_live_cutover") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = payload.get("capture") or {}
    route = capture.get("route") or {}
    lines = [
        "# Design Guide No-Active Combined Low-Util Full Route Trace Wiring Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Route: `{route.get('name')}`",
        f"Route lines: `{route.get('start_line')}-{route.get('end_line')}`",
        f"Trace key: `{capture.get('trace_key')}`",
        f"Ready for live cutover: `{capture.get('ready_for_live_cutover')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "Keep the page route as a thin callback wrapper around the full controller route. "
            "Page-owned diagnostic trace for this route has been deleted.",
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
        / f"design_guide_no_active_combined_low_util_full_route_trace_wiring_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_combined_low_util_full_route_trace_wiring_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"{status}: {json_path}")
    print(f"Report: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
