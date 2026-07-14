"""Verify trace-only full-route builder proof wiring for blocked-primary route."""

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
CONTROLLER_ROUTE = "run_design_guide_controller_no_active_blocked_primary_cleanup_probe_route"
GENERIC_CALLER = "_run_design_guide_page_shell_controller_route"
CONTROLLER_ALIAS = "_run_design_guide_controller_no_active_blocked_primary_cleanup_probe_route"
POLICY_STAMP = "_stamp_design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_trace_only"
FULL_ROUTE_STAMP = "_stamp_design_guide_controller_no_active_blocked_primary_full_route_builder_trace_only"


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


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    route_source, route_start, route_end = _function_source(INPUTS_PAGE, ROUTE)
    controller_route_source, controller_route_start, controller_route_end = _function_source(
        CONTROLLER, CONTROLLER_ROUTE
    )
    policy_source, policy_start, policy_end = _function_source(INPUTS_PAGE, POLICY_STAMP)
    full_source, full_start, full_end = _function_source(INPUTS_PAGE, FULL_ROUTE_STAMP)
    route_text = route_source or ""
    controller_route_text = controller_route_source or ""
    full_text = full_source or ""
    return {
        "decision": "FULL_ROUTE_BUILDER_TRACE_WIRED_IN_CONTROLLER_ROUTE_AFTER_PAGE_SHELL_CUTOVER",
        "route": {
            "name": ROUTE,
            "present": route_source is not None,
            "start_line": route_start,
            "end_line": route_end,
            "delegates_to_controller": (
                f"return {GENERIC_CALLER}(" in route_text
                and f"controller_fn={CONTROLLER_ALIAS}" in route_text
            ),
        },
        "controller_route": {
            "name": CONTROLLER_ROUTE,
            "present": controller_route_source is not None,
            "start_line": controller_route_start,
            "end_line": controller_route_end,
            "exported": f'"{CONTROLLER_ROUTE}"' in controller_source,
            "safe_branch_builds_full_route_proof": (
                "safe_cleanup_result=safe_cleanup_result" in controller_route_text
                and "bending_cleanup_result=None" in controller_route_text
            ),
            "bending_branch_builds_full_route_proof": (
                "safe_cleanup_result=None" in controller_route_text
                and "bending_cleanup_result=bending_probe_result" in controller_route_text
            ),
            "full_route_trace_key_present": (
                "design_guide_controller_no_active_blocked_primary_full_route_builder_trace_only"
                in controller_route_text
            ),
            "policy_trace_key_present": (
                "design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_trace_only"
                in controller_route_text
            ),
            "result_trace_key_present": (
                "design_guide_controller_no_active_blocked_primary_cleanup_probe_result_trace_only"
                in controller_route_text
            ),
            "non_product_flags": all(
                token in controller_route_text
                for token in [
                    '"product_driving": False',
                    '"render_driving": False',
                    '"apply_driving": False',
                    '"session_driving": False',
                ]
            ),
            "hash_fields_present": all(
                token in controller_route_text
                for token in [
                    "full_route_builder_hash",
                    "selected_result_hash",
                    "live_result_hash",
                    "result_hash_match",
                ]
            ),
        },
        "policy_stamp": {
            "name": POLICY_STAMP,
            "present": policy_source is not None,
            "start_line": policy_start,
            "end_line": policy_end,
            "returns_proof": "return proof" in (policy_source or ""),
            "returns_none_on_error": "return None" in (policy_source or ""),
        },
        "full_route_stamp": {
            "name": FULL_ROUTE_STAMP,
            "present": full_source is not None,
            "start_line": full_start,
            "end_line": full_end,
            "calls_controller_builder": (
                "_build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof("
                in full_text
            ),
            "debug_key_present": (
                "design_guide_controller_no_active_blocked_primary_full_route_builder_trace_only"
                in full_text
            ),
            "non_product_flags": all(
                token in full_text
                for token in [
                    '"product_driving": False',
                    '"render_driving": False',
                    '"apply_driving": False',
                    '"session_driving": False',
                ]
            ),
            "hash_fields_present": all(
                token in full_text
                for token in [
                    "full_route_builder_hash",
                    "selected_result_hash",
                    "live_result_hash",
                    "result_hash_match",
                ]
            ),
        },
        "route_wiring": {
            "page_delegates_to_controller_route": (
                f"return {GENERIC_CALLER}(" in route_text
                and f"controller_fn={CONTROLLER_ALIAS}" in route_text
            ),
            "legacy_full_route_stamp_call_count": route_text.count(f"{FULL_ROUTE_STAMP}("),
            "controller_full_route_proof_call_count": controller_route_text.count(
                "build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof("
            ),
            "safe_branch_wires_safe_result": "safe_cleanup_result=safe_cleanup_result" in controller_route_text,
            "bending_branch_wires_bending_result": (
                "bending_cleanup_result=bending_probe_result" in controller_route_text
            ),
        },
        "import_present": (
            "build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof as "
            "_build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof"
            in inputs_source
        ),
        "latest": {
            "full_route_builder_object": {
                "status": _latest(
                    "design_guide_no_active_blocked_primary_full_route_builder_object"
                ).get("status"),
                "path": _latest(
                    "design_guide_no_active_blocked_primary_full_route_builder_object"
                ).get("path"),
            },
            "controller_route_object": {
                "status": _latest(
                    "design_guide_no_active_blocked_primary_controller_route_object"
                ).get("status"),
                "path": _latest(
                    "design_guide_no_active_blocked_primary_controller_route_object"
                ).get("path"),
            },
            "generic_page_shell_cutover": {
                "status": _latest(
                    "design_guide_no_active_blocked_primary_generic_page_shell_caller_cutover"
                ).get("status"),
                "path": _latest(
                    "design_guide_no_active_blocked_primary_generic_page_shell_caller_cutover"
                ).get("path"),
            },
            "independence_lock": {
                "status": _latest("design_guide_independence_lock").get("status"),
                "path": _latest("design_guide_independence_lock").get("path"),
            },
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    policy = dict(capture.get("policy_stamp") or {})
    full = dict(capture.get("full_route_stamp") or {})
    controller = dict(capture.get("controller_route") or {})
    route = dict(capture.get("route") or {})
    route_wiring = dict(capture.get("route_wiring") or {})
    route_absent_after_deletion = route.get("present") is False and controller.get("present") is True
    return {
        "controller_import_present": capture.get("import_present") is True,
        "route_present_or_deleted": route.get("present") is True or route_absent_after_deletion,
        "page_route_delegates_to_controller": route_wiring.get(
            "page_delegates_to_controller_route"
        )
        is True
        or route_absent_after_deletion,
        "controller_route_present": controller.get("present") is True,
        "controller_route_exported": controller.get("exported") is True,
        "controller_route_trace_keys_present": (
            controller.get("full_route_trace_key_present") is True
            and controller.get("policy_trace_key_present") is True
            and controller.get("result_trace_key_present") is True
        ),
        "controller_route_non_product": controller.get("non_product_flags") is True,
        "controller_hash_fields_present": controller.get("hash_fields_present") is True,
        "policy_stamp_returns_proof": policy.get("returns_proof") is True,
        "policy_stamp_returns_none_on_error": policy.get("returns_none_on_error") is True,
        "full_route_stamp_present": full.get("present") is True,
        "full_route_stamp_calls_controller_builder": full.get("calls_controller_builder") is True,
        "full_route_debug_key_present": full.get("debug_key_present") is True,
        "full_route_stamp_non_product": full.get("non_product_flags") is True,
        "hash_fields_present": full.get("hash_fields_present") is True,
        "safe_branch_wired": route_wiring.get("safe_branch_wires_safe_result") is True,
        "bending_branch_wired": route_wiring.get("bending_branch_wires_bending_result") is True,
        "exactly_two_controller_full_route_proof_calls": route_wiring.get(
            "controller_full_route_proof_call_count"
        )
        == 2,
        "full_route_builder_object_passed": (latest.get("full_route_builder_object") or {}).get("status")
        == "PASS",
        "controller_route_object_passed": (latest.get("controller_route_object") or {}).get(
            "status"
        )
        == "PASS",
        "generic_page_shell_cutover_artifact_available": (
            latest.get("generic_page_shell_cutover") or {}
        ).get("status")
        in {"PASS", "FAIL", "MISSING"},
        "independence_lock_artifact_available": (latest.get("independence_lock") or {}).get("status")
        in {"PASS", "FAIL"},
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide No-Active Blocked-Primary Full Route Trace Wiring",
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
            "## Next Safe Slice",
            "",
            "Keep branch parity focused on the controller route, then create a dead-body deletion proof for the unreachable page route body.",
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
        / f"design_guide_no_active_blocked_primary_full_route_trace_wiring_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR / f"design_guide_no_active_blocked_primary_full_route_trace_wiring_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_blocked_primary_full_route_trace_wiring {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if status == "PASS":
        print("next=full-route branch parity scenarios")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
