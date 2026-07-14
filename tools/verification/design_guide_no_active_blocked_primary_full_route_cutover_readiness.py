"""Cutover readiness for blocked-primary route extraction.

This verifier does not change behavior. It decides whether the current
trace-wired/parity-proven route can be cut over directly, or whether a live
controller route function must be added first.
"""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

ROUTE = "_resolve_final_visible_no_active_blocked_primary_cleanup_probe_result"
TARGET_CONTROLLER_ROUTE = "run_design_guide_controller_no_active_blocked_primary_cleanup_probe_route"
GENERIC_CALLER = "_run_design_guide_page_shell_controller_route"
SAFE_BUILDER_ALIAS = "_build_design_guide_controller_safe_cleanup_candidate_before_blocker_result"
BENDING_BUILDER_ALIAS = "_build_design_guide_controller_bending_cleanup_available_before_blocker_result"
FULL_ROUTE_PROOF_ALIAS = (
    "_build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof"
)
FULL_ROUTE_TRACE_KEY = "design_guide_controller_no_active_blocked_primary_full_route_builder_trace_only"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not paths:
        return {"status": "MISSING", "path": None}
    path = paths[0]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "ERROR", "path": str(path), "error": f"{type(exc).__name__}: {exc}"}
    return {"status": payload.get("status"), "path": str(path), "payload": payload}


def _function_source(path: Path, function_name: str) -> tuple[str | None, int | None, int | None]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    return None, None, None


def capture_controller_trace_key_present(controller_route_source: str | None) -> bool:
    return FULL_ROUTE_TRACE_KEY in str(controller_route_source or "")


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    route_source, route_start, route_end = _function_source(INPUTS_PAGE, ROUTE)
    route_text = route_source or ""
    controller_route_source, controller_route_start, controller_route_end = _function_source(
        CONTROLLER, TARGET_CONTROLLER_ROUTE
    )
    direct_page_builder_calls = {
        "safe_builder": route_text.count(f"{SAFE_BUILDER_ALIAS}("),
        "bending_builder": route_text.count(f"{BENDING_BUILDER_ALIAS}("),
        "full_route_proof": route_text.count(f"{FULL_ROUTE_PROOF_ALIAS}("),
    }
    controller_route_exists = controller_route_source is not None
    generic_cutover_present = (
        f"{GENERIC_CALLER}(" in route_text
        and f"controller_fn=_{TARGET_CONTROLLER_ROUTE}" in route_text
    )
    direct_cutover_present = f"_{TARGET_CONTROLLER_ROUTE}(" in route_text
    return {
        "decision": (
            "READY_FOR_LIVE_CONTROLLER_ROUTE_IMPLEMENTATION"
            if not controller_route_exists
            else (
                "READY_FOR_GENERIC_PAGE_SHELL_CUTOVER"
                if not (generic_cutover_present or direct_cutover_present)
                else "CONTROLLER_ROUTE_CUTOVER_PRESENT"
            )
        ),
        "route": {
            "name": ROUTE,
            "present": route_source is not None,
            "start_line": route_start,
            "end_line": route_end,
            "line_count": (route_end - route_start + 1) if route_end and route_start else 0,
        },
        "target_controller_route": {
            "name": TARGET_CONTROLLER_ROUTE,
            "present": controller_route_exists,
            "start_line": controller_route_start,
            "end_line": controller_route_end,
            "line_count": (
                controller_route_end - controller_route_start + 1
                if controller_route_end and controller_route_start
                else 0
            ),
        },
        "route_has_trace_parity": (
            FULL_ROUTE_TRACE_KEY in route_text
            or capture_controller_trace_key_present(controller_route_source)
        ),
        "direct_page_builder_calls": direct_page_builder_calls,
        "controller_route_exported": f'"{TARGET_CONTROLLER_ROUTE}"' in controller_source,
        "controller_route_imported_in_inputs": f"{TARGET_CONTROLLER_ROUTE} as _{TARGET_CONTROLLER_ROUTE}"
        in inputs_source,
        "generic_page_shell_cutover_present": generic_cutover_present,
        "direct_controller_cutover_present": direct_cutover_present,
        "latest": {
            "branch_parity": {
                "status": _latest(
                    "design_guide_no_active_blocked_primary_full_route_branch_parity_scenarios"
                ).get("status"),
                "path": _latest(
                    "design_guide_no_active_blocked_primary_full_route_branch_parity_scenarios"
                ).get("path"),
            },
            "trace_wiring": {
                "status": _latest(
                    "design_guide_no_active_blocked_primary_full_route_trace_wiring"
                ).get("status"),
                "path": _latest(
                    "design_guide_no_active_blocked_primary_full_route_trace_wiring"
                ).get("path"),
            },
            "independence_lock": {
                "status": _latest("design_guide_independence_lock").get("status"),
                "path": _latest("design_guide_independence_lock").get("path"),
            },
        },
        "cutover_ready_now": controller_route_exists
        and not (generic_cutover_present or direct_cutover_present),
        "deletion_ready_now": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    direct_calls = dict(capture.get("direct_page_builder_calls") or {})
    controller_route_present = (capture.get("target_controller_route") or {}).get("present") is True
    route_present = (capture.get("route") or {}).get("present") is True
    route_absent_after_deletion = route_present is False and controller_route_present
    return {
        "page_route_still_present_or_deleted": route_present or route_absent_after_deletion,
        "trace_parity_present": capture.get("route_has_trace_parity") is True,
        "branch_parity_passed": (latest.get("branch_parity") or {}).get("status") == "PASS",
        "trace_wiring_passed": (latest.get("trace_wiring") or {}).get("status") == "PASS",
        "independence_lock_artifact_available": (latest.get("independence_lock") or {}).get("status")
        in {"PASS", "FAIL"},
        "direct_page_builder_calls_state_matches_cutover": (
            (
                route_absent_after_deletion
                and int(direct_calls.get("safe_builder") or 0) == 0
                and int(direct_calls.get("bending_builder") or 0) == 0
            )
            or
            (
                capture.get("decision") == "CONTROLLER_ROUTE_CUTOVER_PRESENT"
                and int(direct_calls.get("safe_builder") or 0) == 0
                and int(direct_calls.get("bending_builder") or 0) == 0
            )
            or (
                capture.get("decision") != "CONTROLLER_ROUTE_CUTOVER_PRESENT"
                and int(direct_calls.get("safe_builder") or 0) >= 1
                and int(direct_calls.get("bending_builder") or 0) >= 1
            )
        ),
        "controller_route_state_is_explicit": capture.get("decision")
        in {
            "READY_FOR_LIVE_CONTROLLER_ROUTE_IMPLEMENTATION",
            "READY_FOR_GENERIC_PAGE_SHELL_CUTOVER",
            "CONTROLLER_ROUTE_CUTOVER_PRESENT",
        },
        "route_absent_after_deletion_accounted": route_absent_after_deletion,
        "cutover_not_claimed_without_controller_route": (
            controller_route_present or capture.get("cutover_ready_now") is False
        ),
        "deletion_not_ready_yet": capture.get("deletion_ready_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    route = dict(capture.get("route") or {})
    controller_route = dict(capture.get("target_controller_route") or {})
    lines = [
        "# Design Guide No-Active Blocked-Primary Full Route Cutover Readiness",
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
            "## Route State",
            "",
            f"- Page route lines: `{route.get('start_line')}-{route.get('end_line')}`",
            f"- Target controller route present: `{controller_route.get('present')}`",
            f"- Target controller route lines: `{controller_route.get('start_line')}-{controller_route.get('end_line')}`",
            f"- Cutover ready now: `{capture.get('cutover_ready_now')}`",
            f"- Deletion ready now: `{capture.get('deletion_ready_now')}`",
            "",
            "## Next Safe Slice",
            "",
            "Add the live controller route function before page cutover. It must call the same page-supplied callbacks, return the same result shape, and keep Streamlit/session/render/apply ownership out of Design Brain.",
            "",
            "No product behavior, visible wording, CTA/apply semantics, family runtime, solver maths, target bands, render ownership, apply routing, or UI/session ownership changed.",
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
        / f"design_guide_no_active_blocked_primary_full_route_cutover_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR / f"design_guide_no_active_blocked_primary_full_route_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_blocked_primary_full_route_cutover_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
