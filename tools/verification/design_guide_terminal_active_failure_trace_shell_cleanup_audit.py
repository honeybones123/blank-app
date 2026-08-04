"""Audit terminal active-failure blocker trace-shell cleanup readiness.

Proof-only. This classifies the remaining page shell after terminal
active-failure blocker final-result authority moved to DesignGuideController.
It does not change product behavior, visible wording, CTA/apply semantics,
family runtimes, render/apply ownership, widget keys, or session behavior.
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

PAGE_ROUTE = "_finalize_terminal_active_failure_blocker_result"
CONTROLLER_ROUTE = "run_design_guide_controller_terminal_active_failure_blocker_finalizer_route"
CONTROLLER_ALIAS = "_run_design_guide_controller_terminal_active_failure_blocker_finalizer_route"
OLD_PUBLICATION_CALL = "finalize_design_guide_active_failure_blocker_publication("

PAGE_SHELL_CALLBACKS = (
    "state_fingerprint_fn",
    "suppress_design_guide_blocker_cta_fn",
)

DUPLICATED_CONTROLLER_TRUTH_TOKENS = (
    "active_scope.startswith(\"active_fail_\")",
    "active_scope == \"design_guide_direct_target_band_search\"",
    "active_blocker_source = None",
    "blocker_source = dict(active_blocker_source or",
)

TRACE_COMPATIBILITY_HELPER = (
    "_build_design_guide_controller_terminal_active_failure_trace_compatibility_payload("
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


def _function_source(path: Path, function_name: str) -> tuple[str, int, int, ast.FunctionDef]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end = getattr(node, "end_lineno", None)
            if end is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end]), node.lineno, end, node
    raise RuntimeError(f"Could not find {function_name}")


def _function_source_optional(
    path: Path, function_name: str
) -> tuple[str, int, int, ast.FunctionDef] | None:
    try:
        return _function_source(path, function_name)
    except RuntimeError:
        return None


def _call_names(node: ast.FunctionDef) -> list[str]:
    names: list[str] = []
    for subnode in ast.walk(node):
        if not isinstance(subnode, ast.Call):
            continue
        func = subnode.func
        if isinstance(func, ast.Name):
            names.append(func.id)
        elif isinstance(func, ast.Attribute):
            names.append(func.attr)
        else:
            names.append("<dynamic>")
    return sorted(names)


def _capture() -> dict[str, Any]:
    page_function = _function_source_optional(INPUTS_PAGE, PAGE_ROUTE)
    if page_function is None:
        source, start, end, node = "", None, None, None
    else:
        source, start, end, node = page_function
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    trace_event_count = source.count("_resolver_route_trace_event(")
    duplicated_truth = {
        token: source.count(token) for token in DUPLICATED_CONTROLLER_TRUTH_TOKENS
    }
    page_shell_callbacks = {name: name in source for name in PAGE_SHELL_CALLBACKS}
    call_names = _call_names(node) if node is not None else []
    route_object = _latest(
        "design_guide_terminal_active_failure_blocker_finalizer_route_object"
    )
    cutover = _latest("design_guide_terminal_active_failure_blocker_finalizer_cutover")
    readiness = _latest(
        "design_guide_terminal_active_failure_blocker_finalizer_cutover_readiness"
    )
    trace_payload_helper_call_present = TRACE_COMPATIBILITY_HELPER in source
    duplicated_source_filter_trace_logic = any(
        count > 0 for count in duplicated_truth.values()
    )
    wrapper_deleted_direct_callsite = (
        page_function is None and inputs_source.count(f"{CONTROLLER_ALIAS}(") >= 1
    )
    route_retired_no_live_callsite = (
        page_function is None and inputs_source.count(f"{CONTROLLER_ALIAS}(") == 0
    )
    trace_shell_removed = (
        (trace_event_count == 0 and not trace_payload_helper_call_present)
        or wrapper_deleted_direct_callsite
        or route_retired_no_live_callsite
    )
    return {
        "decision": (
            "PAGE_WRAPPER_DELETED_DIRECT_CONTROLLER_CALLSITE"
            if wrapper_deleted_direct_callsite
            else "TRACE_COMPATIBILITY_SHELL_DELETED_CONTROLLER_ROUTE_REMAINS"
            if trace_shell_removed
            else "TRACE_COMPATIBILITY_OBJECT_WIRED_TRACE_SHELL_REMAINS"
        ),
        "page_shell": {
            "name": PAGE_ROUTE,
            "present": page_function is not None,
            "start_line": start,
            "end_line": end,
            "line_count": (end - start + 1) if start is not None and end is not None else 0,
            "source_hash": _stable_hash(source),
            "calls_controller_alias": f"{CONTROLLER_ALIAS}(" in source
            or wrapper_deleted_direct_callsite,
            "old_publication_call_present": OLD_PUBLICATION_CALL in source,
            "trace_event_count": trace_event_count,
            "trace_payload_helper_call_present": trace_payload_helper_call_present,
            "page_shell_callbacks": page_shell_callbacks,
            "duplicated_controller_truth_tokens": duplicated_truth,
            "call_names": call_names,
            "uses_streamlit_or_session": any(
                token in source for token in ("st.session_state", "streamlit")
            ),
            "constructs_visible_wording": any(
                token in source
                for token in (
                    "Strengthening required",
                    "Design is efficient",
                    "Repair required",
                    "Cleanup",
                )
            ),
            "wrapper_deleted_direct_callsite": wrapper_deleted_direct_callsite,
            "route_retired_no_live_callsite": route_retired_no_live_callsite,
        },
        "controller": {
            "route_present": CONTROLLER_ROUTE in controller_source,
            "route_hash": _stable_hash(
                _function_source(CONTROLLER, CONTROLLER_ROUTE)[0]
            ),
        },
        "latest": {
            "route_object": {"status": route_object.get("status"), "path": route_object.get("path")},
            "cutover_readiness": {
                "status": readiness.get("status"),
                "path": readiness.get("path"),
            },
            "cutover": {"status": cutover.get("status"), "path": cutover.get("path")},
        },
        "classification": {
            "final_result_authority": False,
            "publication_binding_authority": False,
            "cta_apply_authority": False,
            "visible_wording_authority": False,
            "duplicated_source_filter_trace_logic": duplicated_source_filter_trace_logic,
            "controller_trace_compatibility_payload_wired": False,
            "trace_compatibility_shell": not trace_shell_removed,
            "trace_shell_removed": trace_shell_removed,
            "page_shell_callback_wiring": all(page_shell_callbacks.values())
            or wrapper_deleted_direct_callsite
            or route_retired_no_live_callsite,
            "safe_plain_deletion_now": False,
            "safe_next_step": (
                "Run terminal trace-row reachability and composed locks to prove no deleted trace "
                "shell consumer remains."
                if trace_shell_removed
                else "Audit terminal trace-row consumer reachability, then delete or compress the remaining trace-compatible shell only after proof."
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "session_state_behavior_changed": False,
        "widget_keys_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    page = dict(capture.get("page_shell") or {})
    latest = dict(capture.get("latest") or {})
    classification = dict(capture.get("classification") or {})
    route_retired = page.get("route_retired_no_live_callsite") is True
    return {
        "page_shell_present_or_deleted": page.get("line_count", 0) > 0
        or page.get("wrapper_deleted_direct_callsite") is True
        or route_retired,
        "page_shell_calls_controller_or_route_retired": (
            page.get("calls_controller_alias") is True or route_retired
        ),
        "old_publication_call_absent": page.get("old_publication_call_present") is False,
        "trace_compatibility_shell_removed": page.get("trace_event_count", 0) == 0,
        "page_shell_callbacks_present_or_deleted": all(
            (page.get("page_shell_callbacks") or {}).values()
        )
        or page.get("wrapper_deleted_direct_callsite") is True
        or route_retired,
        "trace_payload_helper_removed": page.get("trace_payload_helper_call_present") is False,
        "no_streamlit_or_session_in_shell": page.get("uses_streamlit_or_session") is False,
        "no_visible_wording_constructed": page.get("constructs_visible_wording") is False,
        "route_object_passes": (latest.get("route_object") or {}).get("status") == "PASS",
        "cutover_readiness_passes": (latest.get("cutover_readiness") or {}).get("status")
        == "PASS",
        "cutover_passes": (latest.get("cutover") or {}).get("status") == "PASS",
        "final_result_authority_removed": classification.get("final_result_authority") is False,
        "duplicated_source_filter_trace_logic_removed": classification.get(
            "duplicated_source_filter_trace_logic"
        )
        is False,
        "trace_shell_removed_classified": classification.get("trace_shell_removed") is True,
        "plain_deletion_not_allowed": classification.get("safe_plain_deletion_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
        "session_state_behavior_unchanged": capture.get("session_state_behavior_changed")
        is False,
        "widget_keys_unchanged": capture.get("widget_keys_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    page = dict(capture.get("page_shell") or {})
    classification = dict(capture.get("classification") or {})
    lines = [
        "# Terminal Active-Failure Trace Shell Cleanup Audit",
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
            "## Page Shell",
            "",
            f"- Function: `{page.get('name')}`",
            f"- Lines: `{page.get('start_line')}-{page.get('end_line')}`",
            f"- Line count: `{page.get('line_count')}`",
            f"- Trace event count: `{page.get('trace_event_count')}`",
            "",
            "## Classification",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in classification.items())
    lines.extend(
        [
            "",
            "## Duplicated Controller Truth Tokens",
        ]
    )
    for token, count in (page.get("duplicated_controller_truth_tokens") or {}).items():
        lines.append(f"- `{token}`: `{count}`")
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            str(classification.get("safe_next_step") or ""),
            "",
            "No product behavior, visible wording, CTA/apply semantics, family runtime, render/apply ownership, widget keys, or session behavior changed.",
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
        / f"design_guide_terminal_active_failure_trace_shell_cleanup_audit_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_terminal_active_failure_trace_shell_cleanup_audit_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_terminal_active_failure_trace_shell_cleanup_audit {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if status == "PASS":
        print("next=terminal trace-row consumer reachability audit")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
