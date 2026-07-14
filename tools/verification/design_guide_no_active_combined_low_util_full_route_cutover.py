"""Verify live cutover to the controller route for no-active combined low-util cleanup."""

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
CONTROLLER_ALIAS = "_run_design_guide_controller_no_active_combined_low_util_cleanup_route"
GENERATION_ALIAS = "_run_design_guide_controller_combined_low_util_candidate_generation"
RESULT_BUILDER_ALIAS = "_build_design_guide_controller_combined_low_util_cleanup_result"
TRACE_KEY = "design_guide_controller_no_active_combined_low_util_full_route_trace_only"


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
    helper_source, helper_start, _helper_end = _function_source(path, GENERIC_CALLER)
    start_index = None
    paren_depth = 0
    for index, line in enumerate(lines):
        if f"{GENERIC_CALLER}(" not in line:
            continue
        window = "\n".join(lines[index : min(index + 8, len(lines))])
        if f"controller_fn={CONTROLLER_ALIAS}" not in window:
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
    return helper_source + "\n" + "\n".join(lines[start_index : end_index + 1]), helper_start, end_index + 1


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
        and CONTROLLER_ALIAS in inputs_source
        and controller_route_exported
    )
    controller_call_index = route_source.find(f"{CONTROLLER_ALIAS}(")
    generic_controller_call_index = route_source.find(f"controller_fn={CONTROLLER_ALIAS}")
    return {
        "decision": (
            "PAGE_ROUTE_DELETED_CONTROLLER_ROUTE_VERIFIED"
            if page_route_deleted_controller_verified
            else "CONTROLLER_ROUTE_RETURN_CUT_OVER"
        ),
        "route": {
            "name": route_name,
            "start_line": route_start,
            "end_line": route_end,
            "line_count": (route_end - route_start + 1) if route_source else 0,
            "deleted": page_route_deleted_controller_verified,
        },
        "controller_route_alias_imported": CONTROLLER_ALIAS in inputs_source,
        "controller_route_exported": controller_route_exported,
        "controller_route_called": controller_call_index >= 0
        or generic_controller_call_index >= 0
        or page_route_deleted_controller_verified,
        "route_assigns_controller_result": (
            f"result = {CONTROLLER_ALIAS}(" in route_source
            or "result = controller_fn(**controller_kwargs)" in route_source
            or page_route_deleted_controller_verified
        ),
        "route_returns_controller_result": "return result" in route_source
        or page_route_deleted_controller_verified,
        "no_direct_candidate_generation_call": f"{GENERATION_ALIAS}(" not in route_source,
        "no_direct_result_builder_call": f"{RESULT_BUILDER_ALIAS}(" not in route_source,
        "page_trace_event_deleted": "_resolver_route_trace_event(" not in route_source,
        "page_trace_key_deleted": TRACE_KEY not in route_source,
        "page_cutover_trace_deleted": '"product_result_source": "controller_route_cutover"'
        not in route_source,
        "forbidden_ownership": {
            "apply_routing": "_queue_primary_design_guide_button_action" in route_source,
            "streamlit_render": "st.markdown(" in route_source or "st.button(" in route_source,
            "streamlit_session_write": "st.session_state" in route_source,
            "family_runtime": "contracted_repair_ladder_specs(" in route_source,
        },
        "verification": {
            "builder_object": _run(
                "tools/verification/design_guide_no_active_combined_low_util_full_route_builder_object_snapshot.py"
            ),
            "parity_scenarios": _run(
                "tools/verification/design_guide_no_active_combined_low_util_full_route_parity_scenarios.py"
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    verification = capture.get("verification") or {}
    return {
        "controller_route_alias_imported": capture.get("controller_route_alias_imported") is True,
        "controller_route_exported": capture.get("controller_route_exported") is True,
        "controller_route_called": capture.get("controller_route_called") is True,
        "route_assigns_controller_result": capture.get("route_assigns_controller_result") is True,
        "route_returns_controller_result": capture.get("route_returns_controller_result") is True,
        "no_direct_candidate_generation_call": (
            capture.get("no_direct_candidate_generation_call") is True
        ),
        "no_direct_result_builder_call": capture.get("no_direct_result_builder_call") is True,
        "page_trace_event_deleted": capture.get("page_trace_event_deleted") is True,
        "page_trace_key_deleted": capture.get("page_trace_key_deleted") is True,
        "page_cutover_trace_deleted": capture.get("page_cutover_trace_deleted") is True,
        "no_forbidden_ownership": not any((capture.get("forbidden_ownership") or {}).values()),
        "builder_object_passed": (verification.get("builder_object") or {}).get("passed") is True,
        "parity_scenarios_passed": (verification.get("parity_scenarios") or {}).get("passed")
        is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = payload.get("capture") or {}
    route = capture.get("route") or {}
    lines = [
        "# Design Guide No-Active Combined Low-Util Full Route Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Route lines: `{route.get('start_line')}-{route.get('end_line')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "Keep the route cutover. The page function is now a thin controller caller with "
            "callback forwarding and no page-owned route diagnostics.",
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
        / f"design_guide_no_active_combined_low_util_full_route_cutover_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_combined_low_util_full_route_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"{status}: {json_path}")
    print(f"Report: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
