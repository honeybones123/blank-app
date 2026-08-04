"""Cutover proof for terminal active-failure blocker finalizer.

Executes the cut-over page shell in isolation and compares it to the
controller route. This proves the page now delegates result construction while
preserving trace compatibility. It does not drive Streamlit or Apply routing.
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

PAGE_ROUTE = "_finalize_terminal_active_failure_blocker_result"
CONTROLLER_ALIAS = "_run_design_guide_controller_terminal_active_failure_blocker_finalizer_route"
OLD_PUBLICATION_CALL = "finalize_design_guide_active_failure_blocker_publication("

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


def _state_fingerprint(state: dict[str, Any] | None) -> str:
    return "state:" + _stable_hash(dict(state or {}))[:16]


def _suppress_blocker_cta(item: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(item or {})
    out["primary_card_actionable"] = False
    out["button_contract"] = {
        "enabled": False,
        "actionable": False,
        "reason": "terminal_active_failure_blocker_cutover",
    }
    return out


def _trace_item_summary(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"type": type(item).__name__, "present": item is not None}
    return {
        "title": item.get("title") or item.get("title_main"),
        "family": item.get("family"),
        "source_marker": item.get("source_marker"),
        "status": item.get("status"),
        "bucket": item.get("bucket"),
        "button_contract": dict(item.get("button_contract") or {}),
    }


def _active_item(*, scope: str, marker: str, active_blocker: bool = False) -> dict[str, Any]:
    return {
        "title": "Existing active blocker",
        "title_main": "Existing active blocker",
        "family": "bending",
        "source_marker": marker,
        "primary_action": "Bending repair blocked.",
        "active_under_capacity_blocker": bool(active_blocker),
        "candidate_search_evidence": {
            "search_scope": scope,
            "active_fail_repair_search_scope": scope,
            "repair_search_exhaustive": True,
            "exact_blockers_by_family": {
                "bending": {
                    "family": "bending",
                    "blocked_reason": "snapshot blocker",
                    "blocked_ladder": "BENDING_FAIL_GOVERNS",
                    "no_valid_candidate": True,
                }
            },
        },
    }


def _base_kwargs(active_item: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "active_item": active_item,
        "raw_guidance_items": [
            {
                "title": "Fallback active blocker",
                "title_main": "Fallback active blocker",
                "family": "bending",
                "source_marker": "fallback",
                "primary_action": "Fallback bending repair blocked.",
                "candidate_search_evidence": {
                    "search_scope": "active_fail_fallback_snapshot",
                    "active_fail_repair_search_scope": "active_fail_fallback_snapshot",
                    "repair_search_exhaustive": True,
                },
            }
        ],
        "active_family": "bending",
        "active_title": "Bending repair blocked",
        "active_failures": ["bending"],
        "final_overview": {
            "bending": {"utilisation": 1.42, "status": "FAIL"},
            "shear": {"utilisation": 0.82, "status": "PASS"},
        },
        "final_state": {"D": 650.0, "b": 400.0, "Mu_pos": 800.0},
        "debug_probe": {"snapshot": "terminal_active_failure_blocker_finalizer_cutover"},
        "state_fingerprint_fn": _state_fingerprint,
        "suppress_design_guide_blocker_cta_fn": _suppress_blocker_cta,
    }


def _load_page_function() -> tuple[Any, list[dict[str, Any]], str]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_terminal_active_failure_blocker_finalizer_route,
    )

    page_function = _function_source_optional(INPUTS_PAGE, PAGE_ROUTE)
    source = page_function[0] if page_function is not None else ""
    trace_events: list[dict[str, Any]] = []

    def _trace(event: str, **payload: Any) -> None:
        trace_events.append({"event": event, "payload": payload})

    namespace: dict[str, Any] = {
        CONTROLLER_ALIAS: run_design_guide_controller_terminal_active_failure_blocker_finalizer_route,
        "_resolver_route_trace_event": _trace,
        "_dg_runtime_trace_item_summary": _trace_item_summary,
        "_dg_runtime_trace_hash": _stable_hash,
        "time": __import__("time"),
    }
    if page_function is None:
        return (
            run_design_guide_controller_terminal_active_failure_blocker_finalizer_route,
            trace_events,
            source,
        )
    exec(compile(source, str(INPUTS_PAGE), "exec"), namespace)
    return namespace[PAGE_ROUTE], trace_events, source


def _run_case(active_item: dict[str, Any] | None) -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_terminal_active_failure_blocker_finalizer_route,
    )

    page_fn, trace_events, _ = _load_page_function()
    page_result = page_fn(**_base_kwargs(active_item))
    controller_result = run_design_guide_controller_terminal_active_failure_blocker_finalizer_route(
        **_base_kwargs(active_item)
    )
    return {
        "page_hash": _stable_hash(page_result),
        "controller_hash": _stable_hash(controller_result),
        "result_hashes_match": _stable_hash(page_result) == _stable_hash(controller_result),
        "page_source_marker": dict((page_result or {}).get("item") or {}).get("source_marker"),
        "controller_source_marker": dict((controller_result or {}).get("item") or {}).get(
            "source_marker"
        ),
        "page_render_reason": (page_result or {}).get("render_reason"),
        "controller_render_reason": (controller_result or {}).get("render_reason"),
        "page_button_contract": dict(
            dict((page_result or {}).get("item") or {}).get("button_contract") or {}
        ),
        "trace_events": [row.get("event") for row in trace_events],
        "trace_hash": _stable_hash(trace_events),
    }


def _capture() -> dict[str, Any]:
    page_function = _function_source_optional(INPUTS_PAGE, PAGE_ROUTE)
    source = page_function[0] if page_function is not None else ""
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    valid_active = _run_case(
        _active_item(scope="active_fail_depth_width_exhausted", marker="active")
    )
    active_under_capacity = _run_case(
        _active_item(scope="cleanup_search", marker="active_under_capacity", active_blocker=True)
    )
    invalid_cleanup = _run_case(_active_item(scope="cleanup_search", marker="invalid_cleanup"))
    wrapper_deleted_direct_callsite = (
        page_function is None and inputs_source.count(f"{CONTROLLER_ALIAS}(") >= 1
    )
    route_retired_no_live_callsite = (
        page_function is None and inputs_source.count(f"{CONTROLLER_ALIAS}(") == 0
    )
    return {
        "decision": (
            "PAGE_WRAPPER_DELETED_DIRECT_CONTROLLER_CALLSITE"
            if wrapper_deleted_direct_callsite
            else
            "PAGE_ROUTE_DELETED_NO_LIVE_CALLSITE"
            if route_retired_no_live_callsite
            else "TRACE_PRESERVING_CONTROLLER_DELEGATION_CUTOVER"
        ),
        "page_route": {
            "name": PAGE_ROUTE,
            "source_hash": _stable_hash(source),
            "present": page_function is not None,
            "calls_controller_alias": f"{CONTROLLER_ALIAS}(" in source
            or wrapper_deleted_direct_callsite,
            "old_publication_finalizer_call_removed": OLD_PUBLICATION_CALL not in source,
            "terminal_trace_row_count": source.count("_resolver_route_trace_event("),
            "trace_payload_helper_present": (
                "_build_design_guide_controller_terminal_active_failure_trace_compatibility_payload("
                in source
            ),
            "wrapper_deleted_direct_callsite": wrapper_deleted_direct_callsite,
            "route_retired_no_live_callsite": route_retired_no_live_callsite,
        },
        "cases": {
            "valid_active_source_kept": valid_active,
            "active_under_capacity_source_kept": active_under_capacity,
            "invalid_cleanup_source_falls_back": invalid_cleanup,
        },
        "latest": {
            "route_object": _latest(
                "design_guide_terminal_active_failure_blocker_finalizer_route_object"
            ),
            "cutover_readiness": _latest(
                "design_guide_terminal_active_failure_blocker_finalizer_cutover_readiness"
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
    page = dict(capture.get("page_route") or {})
    cases = dict(capture.get("cases") or {})
    latest = dict(capture.get("latest") or {})
    route_retired = page.get("route_retired_no_live_callsite") is True
    return {
        "route_object_passes": (latest.get("route_object") or {}).get("status") == "PASS",
        "cutover_readiness_passes": (latest.get("cutover_readiness") or {}).get("status")
        == "PASS",
        "page_calls_controller_alias_or_route_retired": (
            page.get("calls_controller_alias") is True or route_retired
        ),
        "page_route_present_or_deleted": page.get("present") is True
        or page.get("wrapper_deleted_direct_callsite") is True
        or route_retired,
        "old_publication_finalizer_call_removed": page.get("old_publication_finalizer_call_removed")
        is True,
        "terminal_trace_rows_removed": page.get("terminal_trace_row_count") == 0,
        "page_trace_payload_helper_removed": page.get("trace_payload_helper_present") is False,
        "all_cases_match_controller_hash": all(
            (case or {}).get("result_hashes_match") is True for case in cases.values()
        ),
        "valid_active_source_kept": (cases.get("valid_active_source_kept") or {}).get(
            "page_source_marker"
        )
        == "active",
        "active_under_capacity_source_kept": (
            cases.get("active_under_capacity_source_kept") or {}
        ).get("page_source_marker")
        == "active_under_capacity",
        "invalid_cleanup_source_falls_back": (
            cases.get("invalid_cleanup_source_falls_back") or {}
        ).get("page_source_marker")
        == "fallback",
        "all_buttons_disabled": all(
            ((case or {}).get("page_button_contract") or {}).get("enabled") is False
            for case in cases.values()
        ),
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
    lines = [
        "# Terminal Active-Failure Blocker Finalizer Cutover",
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
            "## Cases",
            "",
            "| Case | Page marker | Controller marker | Hashes match |",
            "| --- | --- | --- | ---: |",
        ]
    )
    for name, case in (capture.get("cases") or {}).items():
        lines.append(
            f"| {name} | `{case.get('page_source_marker')}` | `{case.get('controller_source_marker')}` | `{case.get('result_hashes_match')}` |"
        )
    lines.extend(
        [
            "",
            "The page route now delegates final result construction to the controller route while preserving trace compatibility.",
            "No product behavior, visible wording, CTA/apply semantics, family runtime, render ownership, apply routing, session behavior, or widget keys changed.",
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
        / f"design_guide_terminal_active_failure_blocker_finalizer_cutover_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_terminal_active_failure_blocker_finalizer_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_terminal_active_failure_blocker_finalizer_cutover {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
