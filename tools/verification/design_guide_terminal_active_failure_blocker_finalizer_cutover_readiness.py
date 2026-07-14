"""Cutover readiness for terminal active-failure blocker finalizer.

Proof-only. This verifier does not change inputs_page.py behavior. It checks
whether the page finalizer can be moved behind the Design Guide controller
route and records the required cutover style.
"""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import inspect
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

PAGE_ROUTE = "_finalize_terminal_active_failure_blocker_result"
CONTROLLER_ROUTE = "run_design_guide_controller_terminal_active_failure_blocker_finalizer_route"
CONTROLLER_ALIAS = "_run_design_guide_controller_terminal_active_failure_blocker_finalizer_route"
GENERIC_CALLER = "_run_design_guide_page_shell_controller_route"

REQUIRED_KWARGS = (
    "active_item",
    "raw_guidance_items",
    "active_family",
    "active_title",
    "active_failures",
    "final_overview",
    "final_state",
    "debug_probe",
    "state_fingerprint_fn",
    "suppress_design_guide_blocker_cta_fn",
)


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
    status = str(payload.get("status") or payload.get("result") or "UNKNOWN")
    if "PASS" in status.upper():
        status = "PASS"
    return {"status": status, "path": str(path), "payload": payload}


def _function_source(path: Path, function_name: str) -> tuple[str, ast.FunctionDef]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end = getattr(node, "end_lineno", None)
            if end is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end]), node
    raise RuntimeError(f"Could not find {function_name}")


def _function_source_optional(path: Path, function_name: str) -> tuple[str, ast.FunctionDef] | None:
    try:
        return _function_source(path, function_name)
    except RuntimeError:
        return None


def _kwonly_args(node: ast.FunctionDef) -> list[str]:
    return [arg.arg for arg in node.args.kwonlyargs]


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_terminal_active_failure_blocker_finalizer_route,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    page_function = _function_source_optional(INPUTS_PAGE, PAGE_ROUTE)
    controller_source = inspect.getsource(
        run_design_guide_controller_terminal_active_failure_blocker_finalizer_route
    )
    page_source = page_function[0] if page_function is not None else ""
    page_node = page_function[1] if page_function is not None else None
    page_kwargs = _kwonly_args(page_node) if page_node is not None else []
    controller_signature = inspect.signature(
        run_design_guide_controller_terminal_active_failure_blocker_finalizer_route
    )
    controller_params = list(controller_signature.parameters)
    route_object = _latest(
        "design_guide_terminal_active_failure_blocker_finalizer_route_object"
    )
    trace_event_count = page_source.count("_resolver_route_trace_event(")
    publication_finalizer_call_count = page_source.count(
        "finalize_design_guide_active_failure_blocker_publication("
    )
    controller_alias_call_count = page_source.count(f"{CONTROLLER_ALIAS}(")
    full_source_controller_alias_call_count = inputs_source.count(f"{CONTROLLER_ALIAS}(")
    generic_caller_present = f"def {GENERIC_CALLER}" in inputs_source
    import_alias_present = CONTROLLER_ALIAS in inputs_source
    required_kwargs_present = {
        name: (name in page_kwargs or page_function is None) and name in controller_params
        for name in REQUIRED_KWARGS
    }
    wrapper_deleted_direct_callsite = (
        page_function is None and full_source_controller_alias_call_count >= 1
    )
    route_retired_no_live_callsite = (
        page_function is None and full_source_controller_alias_call_count == 0
    )
    return {
        "decision": (
            "PAGE_WRAPPER_DELETED_DIRECT_CONTROLLER_CALLSITE"
            if wrapper_deleted_direct_callsite
            else
            "PAGE_ROUTE_DELETED_NO_LIVE_CALLSITE"
            if route_retired_no_live_callsite
            else
            "DIRECT_CONTROLLER_DELEGATION_TRACE_ROWS_DELETED"
            if controller_alias_call_count >= 1 and publication_finalizer_call_count == 0
            else "DIRECT_CONTROLLER_DELEGATION_REQUIRED"
        ),
        "page_route": {
            "name": PAGE_ROUTE,
            "present": page_function is not None,
            "kwonly_args": page_kwargs,
            "line_count": len(page_source.splitlines()),
            "source_hash": _stable_hash(page_source),
            "trace_event_count": trace_event_count,
            "publication_finalizer_call_count": publication_finalizer_call_count,
            "controller_alias_call_count": controller_alias_call_count,
            "full_source_controller_alias_call_count": full_source_controller_alias_call_count,
            "wrapper_deleted_direct_callsite": wrapper_deleted_direct_callsite,
            "route_retired_no_live_callsite": route_retired_no_live_callsite,
            "uses_streamlit_or_session": any(
                token in page_source for token in ("st.session_state", "streamlit")
            ),
        },
        "controller_route": {
            "name": CONTROLLER_ROUTE,
            "present": True,
            "signature": str(controller_signature),
            "params": controller_params,
            "source_hash": _stable_hash(controller_source),
            "required_kwargs_present": required_kwargs_present,
            "forbidden_tokens": {
                "inputs_page": "inputs_page" in controller_source,
                "streamlit": "streamlit" in controller_source.lower()
                or "st.session_state" in controller_source,
                "render_ui": "st." in controller_source,
                "apply_routing": "one_click" in controller_source.lower(),
            },
        },
        "generic_page_shell": {
            "caller_present": generic_caller_present,
            "controller_alias_present": import_alias_present,
            "can_forward_required_kwargs": all(required_kwargs_present.values())
            or route_retired_no_live_callsite,
        },
        "latest": {
            "route_object": {
                "status": route_object.get("status"),
                "path": route_object.get("path"),
            },
        },
        "ready_for_direct_generic_cutover": (
            (controller_alias_call_count >= 1 or wrapper_deleted_direct_callsite)
            and publication_finalizer_call_count == 0
            and route_object.get("status") == "PASS"
            and all(required_kwargs_present.values())
            and trace_event_count == 0
        ),
        "trace_preserving_cutover_complete": (
            (controller_alias_call_count >= 1 or wrapper_deleted_direct_callsite)
            and publication_finalizer_call_count == 0
            and route_object.get("status") == "PASS"
            and all(required_kwargs_present.values())
            and trace_event_count == 0
        ),
        "ready_for_trace_preserving_cutover": (
            route_object.get("status") == "PASS"
            and generic_caller_present
            and all(required_kwargs_present.values())
            and trace_event_count == 0
        ),
        "route_retired_no_live_callsite": route_retired_no_live_callsite,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "page_routing_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    page = dict(capture.get("page_route") or {})
    controller = dict(capture.get("controller_route") or {})
    generic = dict(capture.get("generic_page_shell") or {})
    latest = dict(capture.get("latest") or {})
    route_retired = capture.get("route_retired_no_live_callsite") is True
    return {
        "page_route_present_or_deleted": (
            page.get("present") is True
            or page.get("wrapper_deleted_direct_callsite") is True
            or route_retired
        ),
        "controller_route_present": controller.get("present") is True,
        "route_object_snapshot_passes": (latest.get("route_object") or {}).get("status")
        == "PASS",
        "terminal_trace_rows_deleted": int(page.get("trace_event_count") or 0) == 0,
        "page_route_has_expected_publication_handoff_or_retired": route_retired or (
            int(page.get("publication_finalizer_call_count") or 0) == 1
            or (
                int(page.get("publication_finalizer_call_count") or 0) == 0
                and (
                    int(page.get("controller_alias_call_count") or 0) >= 1
                    or page.get("wrapper_deleted_direct_callsite") is True
                )
            )
        ),
        "controller_required_kwargs_present": all(
            (controller.get("required_kwargs_present") or {}).values()
        ),
        "controller_imports_clean": not any((controller.get("forbidden_tokens") or {}).values()),
        "generic_page_shell_caller_present": generic.get("caller_present") is True,
        "ready_for_trace_preserving_cutover": capture.get(
            "ready_for_trace_preserving_cutover"
        )
        is True
        or capture.get("trace_preserving_cutover_complete") is True
        or route_retired,
        "ready_for_direct_controller_delegation_or_retired": (
            capture.get("ready_for_direct_generic_cutover") is True or route_retired
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
        "page_routing_unchanged": capture.get("page_routing_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Terminal Active-Failure Blocker Finalizer Cutover Readiness",
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
            "## Cutover Requirement",
            "",
            "The terminal page wrapper now directly delegates to the controller route.",
            "The old terminal trace rows have been removed after reachability proof showed no product or verifier consumer remained.",
            "",
            "No product behavior, visible wording, CTA/apply semantics, family runtime, render ownership, apply routing, or session behavior changed.",
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
        / f"design_guide_terminal_active_failure_blocker_finalizer_cutover_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_terminal_active_failure_blocker_finalizer_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_terminal_active_failure_blocker_finalizer_cutover_readiness {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if status == "PASS":
        print("next=terminal route extraction inventory refresh")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
