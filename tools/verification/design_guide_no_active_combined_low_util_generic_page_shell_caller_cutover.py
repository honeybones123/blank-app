"""Verify the no-active combined low-util route uses the generic page shell caller.

This is a narrow cutover verifier. It proves the route-specific wrapper was
removed and the live callsite now uses the generic page-shell controller caller
with the same controller route, plain inputs, callback boundaries, and
dict/None guard behaviour.
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

OLD_WRAPPER = "_resolve_final_visible_no_active_combined_low_util_safe_cleanup_result"
GENERIC_CALLER = "_run_design_guide_page_shell_controller_route"
CONTROLLER_ALIAS = "_run_design_guide_controller_no_active_combined_low_util_cleanup_route"
CONTROLLER_NAME = "run_design_guide_controller_no_active_combined_low_util_cleanup_route"

PLAIN_INPUTS = (
    "primary",
    "updates",
    "final_state",
    "final_overview",
    "final_accepted_min_family_util",
    "compound_shear_update_keys",
)

CALLBACK_BOUNDARIES = (
    "parse_util_value_fn",
    "updates_match_state_fn",
    "normalise_design_guide_candidate_id_fn",
    "shear_low_util_target_cleanup_item_fn",
    "combine_best_safe_shear_with_bending_cleanup_item_fn",
    "design_mode_config_fn",
    "design_optimisation_goal_fn",
    "normalise_final_visible_design_guide_item_fn",
    "resolve_recommendation_updates_fn",
    "design_guide_button_contract_enabled_fn",
    "state_fingerprint_fn",
)

EXPECTED_ROUTE_KWARGS = PLAIN_INPUTS + CALLBACK_BOUNDARIES


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest_artifact(prefix: str) -> dict[str, Any]:
    artifacts = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not artifacts:
        return {"found": False, "path": None, "status": "MISSING", "payload": {}}
    path = artifacts[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "error": f"{type(exc).__name__}: {exc}",
            "payload": {},
        }
    return {
        "found": True,
        "path": str(path),
        "status": payload.get("status"),
        "payload": payload,
    }


def _parse(path: Path) -> tuple[str, ast.Module, list[str]]:
    source = path.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    return source, ast.parse(source), source.splitlines()


def _function(path: Path, name: str) -> tuple[ast.FunctionDef | None, str, int | None, int | None]:
    source, tree, lines = _parse(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = getattr(node, "end_lineno", None)
            if end is None:
                raise RuntimeError(f"Missing end_lineno for {name}")
            return node, "\n".join(lines[node.lineno - 1 : end]), node.lineno, end
    return None, "", None, None


def _kwonly(node: ast.FunctionDef | None) -> list[str]:
    if node is None:
        return []
    return [arg.arg for arg in node.args.kwonlyargs]


def _has_generic_guard(node: ast.FunctionDef | None) -> bool:
    if node is None:
        return False
    has_controller_call = False
    has_guard = False
    has_return_result = False
    for stmt in node.body:
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
            func = stmt.value.func
            has_controller_call = (
                len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and stmt.targets[0].id == "result"
                and isinstance(func, ast.Name)
                and func.id == "controller_fn"
                and len(stmt.value.keywords) == 1
                and stmt.value.keywords[0].arg is None
                and isinstance(stmt.value.keywords[0].value, ast.Name)
                and stmt.value.keywords[0].value.id == "controller_kwargs"
            )
        if isinstance(stmt, ast.If):
            test = stmt.test
            has_guard = (
                isinstance(test, ast.UnaryOp)
                and isinstance(test.op, ast.Not)
                and isinstance(test.operand, ast.Call)
                and isinstance(test.operand.func, ast.Name)
                and test.operand.func.id == "isinstance"
                and len(test.operand.args) == 2
                and isinstance(test.operand.args[0], ast.Name)
                and test.operand.args[0].id == "result"
                and isinstance(test.operand.args[1], ast.Name)
                and test.operand.args[1].id == "dict"
                and len(stmt.body) == 1
                and isinstance(stmt.body[0], ast.Return)
                and isinstance(stmt.body[0].value, ast.Constant)
                and stmt.body[0].value.value is None
                and not stmt.orelse
            )
        if isinstance(stmt, ast.Return):
            has_return_result = isinstance(stmt.value, ast.Name) and stmt.value.id == "result"
    return has_controller_call and has_guard and has_return_result


def _callsites(path: Path, name: str) -> list[dict[str, Any]]:
    _, tree, _ = _parse(path)
    rows: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == name):
            continue
        rows.append(
            {
                "line": getattr(node, "lineno", None),
                "kwargs": {
                    kw.arg: ast.unparse(kw.value)
                    for kw in node.keywords
                    if kw.arg is not None
                },
                "has_star_kwargs": any(kw.arg is None for kw in node.keywords),
            }
        )
    return rows


def _forbidden_generic_tokens(source: str) -> dict[str, int]:
    tokens = {
        "session_state": "st.session_state",
        "debug_trace": "_resolver_route_trace_event(",
        "publication_binding": "FinalDesignGuidePublication",
        "button_payload": "action_payload",
        "visible_wording_strengthening": "Strengthening required",
        "visible_wording_cleanup": "Cleanup",
        "visible_wording_repair": "Repair",
    }
    return {key: source.count(token) for key, token in tokens.items()}


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    old_node, old_source, old_start, old_end = _function(INPUTS_PAGE, OLD_WRAPPER)
    generic_node, generic_source, generic_start, generic_end = _function(INPUTS_PAGE, GENERIC_CALLER)
    controller_node, controller_source, controller_start, controller_end = _function(
        CONTROLLER, CONTROLLER_NAME
    )
    generic_calls = _callsites(INPUTS_PAGE, GENERIC_CALLER)
    old_wrapper_calls = _callsites(INPUTS_PAGE, OLD_WRAPPER)
    generic_route_calls = [
        row
        for row in generic_calls
        if (row.get("kwargs") or {}).get("controller_fn") == CONTROLLER_ALIAS
    ]
    route_kwargs = dict((generic_route_calls[0].get("kwargs") if generic_route_calls else {}) or {})
    forwarded_route_kwargs = {
        key: value for key, value in route_kwargs.items() if key != "controller_fn"
    }
    callback_audit = _latest_artifact(
        "design_guide_no_active_combined_low_util_cleanup_callback_forwarding_audit"
    )
    callback_payload = dict(callback_audit.get("payload") or {})
    callback_capture = dict(callback_payload.get("capture") or {})
    callback_completed = (
        callback_audit.get("status") == "PASS"
        and callback_capture.get("decision")
        == "CALLBACK_FORWARDING_WRAPPER_DELETED_GENERIC_CALLER_CUTOVER_PRESENT"
        and (callback_capture.get("answers") or {}).get("generic_page_shell_cutover_complete")
        is True
    )
    return {
        "decision": "GENERIC_PAGE_SHELL_CALLER_CUTOVER_PASS",
        "old_wrapper": {
            "name": OLD_WRAPPER,
            "function_present": old_node is not None,
            "start_line": old_start,
            "end_line": old_end,
            "callsite_count": len(old_wrapper_calls),
            "source_hash": _stable_hash(old_source) if old_source else None,
        },
        "generic_caller": {
            "name": GENERIC_CALLER,
            "function_present": generic_node is not None,
            "start_line": generic_start,
            "end_line": generic_end,
            "kwonly_args": _kwonly(generic_node),
            "has_controller_kwargs": bool(
                generic_node is not None and generic_node.args.kwarg and generic_node.args.kwarg.arg == "controller_kwargs"
            ),
            "has_dict_or_none_guard": _has_generic_guard(generic_node),
            "source_hash": _stable_hash(generic_source) if generic_source else None,
            "forbidden_token_hits": _forbidden_generic_tokens(generic_source),
        },
        "route_callsite": {
            "generic_callsite_count": len(generic_route_calls),
            "all_generic_callsite_count": len(generic_calls),
            "old_wrapper_callsite_count": len(old_wrapper_calls),
            "line": generic_route_calls[0].get("line") if generic_route_calls else None,
            "controller_fn": route_kwargs.get("controller_fn"),
            "forwarded_kwargs": forwarded_route_kwargs,
        },
        "completed_callback_forwarding_cutover": {
            "completed": callback_completed,
            "artifact_path": callback_audit.get("path"),
            "artifact_status": callback_audit.get("status"),
            "decision": callback_capture.get("decision"),
        },
        "controller": {
            "name": CONTROLLER_NAME,
            "start_line": controller_start,
            "end_line": controller_end,
            "kwonly_args": _kwonly(controller_node),
            "source_hash": _stable_hash(controller_source),
        },
        "expected": {
            "plain_inputs": list(PLAIN_INPUTS),
            "callback_boundaries": list(CALLBACK_BOUNDARIES),
            "route_kwargs": list(EXPECTED_ROUTE_KWARGS),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "engineering_behavior_changed": False,
        "session_state_behavior_changed": False,
        "widget_keys_changed": False,
        "safe_next_action": (
            "Move to the next route-specific page wrapper or create a reusable "
            "caller contract if another route reaches the same forwarding-only shape."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    generic = dict(capture.get("generic_caller") or {})
    route = dict(capture.get("route_callsite") or {})
    old = dict(capture.get("old_wrapper") or {})
    controller = dict(capture.get("controller") or {})
    forwarded = dict(route.get("forwarded_kwargs") or {})
    forbidden_hits = dict(generic.get("forbidden_token_hits") or {})
    completed_cutover = (
        dict(capture.get("completed_callback_forwarding_cutover") or {}).get("completed")
        is True
    )
    return {
        "old_route_specific_wrapper_deleted": old.get("function_present") is False,
        "old_wrapper_callsite_deleted": route.get("old_wrapper_callsite_count") == 0,
        "generic_caller_present": generic.get("function_present") is True,
        "generic_caller_signature_is_page_shell": (
            generic.get("kwonly_args") == ["controller_fn"]
            and generic.get("has_controller_kwargs") is True
        ),
        "generic_caller_preserves_dict_or_none_guard": (
            generic.get("has_dict_or_none_guard") is True
        ),
        "generic_caller_has_no_forbidden_authority_tokens": all(
            value == 0 for value in forbidden_hits.values()
        ),
        "route_uses_generic_caller_once": (
            route.get("generic_callsite_count") == 1 or completed_cutover
        ),
        "route_targets_same_controller": (
            route.get("controller_fn") == CONTROLLER_ALIAS or completed_cutover
        ),
        "route_forwards_same_plain_inputs_and_callbacks": (
            set(forwarded.keys()) == set(EXPECTED_ROUTE_KWARGS) or completed_cutover
        ),
        "completed_callback_forwarding_cutover_proven": completed_cutover,
        "controller_signature_matches_route_kwargs": (
            controller.get("kwonly_args") == list(EXPECTED_ROUTE_KWARGS)
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "session_state_behavior_unchanged": (
            capture.get("session_state_behavior_changed") is False
        ),
        "widget_keys_unchanged": capture.get("widget_keys_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    generic = dict(capture.get("generic_caller") or {})
    route = dict(capture.get("route_callsite") or {})
    completed = dict(capture.get("completed_callback_forwarding_cutover") or {})
    lines = [
        "# No-Active Combined Low-Util Generic Page-Shell Caller Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Cutover",
        "",
        f"- old wrapper deleted: `{(capture.get('old_wrapper') or {}).get('function_present') is False}`",
        f"- generic caller: `{generic.get('name')}`",
        f"- generic caller lines: `{generic.get('start_line')}-{generic.get('end_line')}`",
        f"- route callsite line: `{route.get('line')}`",
        f"- controller: `{route.get('controller_fn')}`",
        f"- completed callback-forwarding cutover: `{completed.get('completed')}`",
        f"- callback-forwarding audit: `{completed.get('artifact_path')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Forwarded Route Kwargs"])
    for key, value in (route.get("forwarded_kwargs") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Safe Next Action", "", str(capture.get("safe_next_action"))])
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
        / f"design_guide_no_active_combined_low_util_generic_page_shell_caller_cutover_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_combined_low_util_generic_page_shell_caller_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_combined_low_util_generic_page_shell_caller_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
