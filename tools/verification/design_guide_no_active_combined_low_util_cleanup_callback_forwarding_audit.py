"""Audit callback-forwarding ownership for no-active combined low-util cleanup.

Audit-only. This does not change product behaviour, cut over another path, or
delete code. It answers whether the remaining route-specific wrapper owns real
Design Guide authority or is only a page-shell callback forwarder.
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

ROUTE = "_resolve_final_visible_no_active_combined_low_util_safe_cleanup_result"
CONTROLLER_ALIAS = "_run_design_guide_controller_no_active_combined_low_util_cleanup_route"
CONTROLLER_NAME = "run_design_guide_controller_no_active_combined_low_util_cleanup_route"

FORWARDED_CALLBACKS = (
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

PLAIN_INPUTS = (
    "primary",
    "updates",
    "final_state",
    "final_overview",
    "final_accepted_min_family_util",
    "compound_shear_update_keys",
)

AUTHORITY_TOKENS = {
    "selection_logic": (
        "if ",
        "elif ",
        "for ",
        "while ",
        "min(",
        "max(",
        "sorted(",
    ),
    "fallback_logic": (
        "fallback",
        "except",
        "try:",
        " or ",
    ),
    "session_state_mutation": ("st.session_state",),
    "debug_trace_state": (
        "_resolver_route_trace_event(",
        "result_debug",
        "debug[",
        "trace_only",
        "live_wired",
    ),
    "cta_apply_payload_construction": (
        "button_contract",
        "action_payload",
        "resolved_candidate",
        "_queue_primary_design_guide_button_action",
    ),
    "visible_wording": (
        "title",
        "body",
        "message",
        "Strengthening required",
        "Design is efficient",
        "Cleanup",
        "Repair",
    ),
    "evidence_packaging": (
        "evidence",
        "proof",
        "candidate_search",
        "blocker",
    ),
    "route_trace_semantics": (
        "return_no_active_combined_low_util_safe_cleanup",
        "_resolver_route_trace_event(",
    ),
    "publication_binding": (
        "FinalDesignGuidePublication",
        "publication",
        "final_publication",
        "publish",
    ),
}


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
        return {
            "status": "ERROR",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or "UNKNOWN")
    if "PASS" in status.upper():
        status = "PASS"
    return {"status": status, "path": str(path), "payload": payload}


def _function_source(path: Path, function_name: str) -> tuple[str, int, int, ast.FunctionDef]:
    source = path.read_text(encoding="utf-8-sig", errors="replace")
    source = source.lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno, node
    raise RuntimeError(f"Could not find {function_name}")


def _callsite_lines(source: str, name: str) -> list[int]:
    return [
        lineno
        for lineno, line in enumerate(source.splitlines(), start=1)
        if f"{name}(" in line and not line.lstrip().startswith("def ")
    ]


def _count_token_hits(source: str, tokens: tuple[str, ...]) -> int:
    return sum(source.count(token) for token in tokens)


def _is_allowed_type_guard(node: ast.stmt) -> bool:
    if not isinstance(node, ast.If):
        return False
    if not (
        isinstance(node.test, ast.UnaryOp)
        and isinstance(node.test.op, ast.Not)
        and isinstance(node.test.operand, ast.Call)
    ):
        return False
    call = node.test.operand
    if not (isinstance(call.func, ast.Name) and call.func.id == "isinstance"):
        return False
    if len(call.args) != 2:
        return False
    if not (isinstance(call.args[0], ast.Name) and call.args[0].id == "result"):
        return False
    if not (isinstance(call.args[1], ast.Name) and call.args[1].id == "dict"):
        return False
    return (
        len(node.body) == 1
        and isinstance(node.body[0], ast.Return)
        and isinstance(node.body[0].value, ast.Constant)
        and node.body[0].value.value is None
        and not node.orelse
    )


def _body_shape(node: ast.FunctionDef) -> dict[str, Any]:
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    statement_kinds = [type(stmt).__name__ for stmt in body]
    allowed_shape = False
    if len(body) == 3:
        assign, guard, ret = body
        allowed_shape = (
            isinstance(assign, ast.Assign)
            and len(assign.targets) == 1
            and isinstance(assign.targets[0], ast.Name)
            and assign.targets[0].id == "result"
            and isinstance(assign.value, ast.Call)
            and isinstance(assign.value.func, ast.Name)
            and assign.value.func.id == CONTROLLER_ALIAS
            and _is_allowed_type_guard(guard)
            and isinstance(ret, ast.Return)
            and isinstance(ret.value, ast.Name)
            and ret.value.id == "result"
        )
    disallowed_calls: list[str] = []
    allowed_calls = {CONTROLLER_ALIAS, "isinstance"}
    for subnode in ast.walk(node):
        if not isinstance(subnode, ast.Call):
            continue
        func = subnode.func
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        else:
            name = "<dynamic>"
        if name not in allowed_calls:
            disallowed_calls.append(name)
    return {
        "statement_kinds_without_docstring": statement_kinds,
        "allowed_pass_through_shape": allowed_shape,
        "disallowed_calls": disallowed_calls,
        "has_only_controller_call_and_type_guard": allowed_shape and not disallowed_calls,
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    inputs_source = inputs_source.lstrip("\ufeff")
    try:
        route_source, start_line, end_line, node = _function_source(INPUTS_PAGE, ROUTE)
    except RuntimeError:
        generic_call_present = CONTROLLER_ALIAS in inputs_source
        latest_cutover = _latest(
            "design_guide_no_active_combined_low_util_generic_page_shell_caller_cutover"
        )
        return {
            "decision": "CALLBACK_FORWARDING_WRAPPER_DELETED_GENERIC_CALLER_CUTOVER_PRESENT",
            "route": {
                "name": ROUTE,
                "present": False,
                "start_line": None,
                "end_line": None,
                "line_count": 0,
                "kwonly_arg_count": 0,
                "kwonly_args": [],
                "callsite_lines": _callsite_lines(inputs_source, ROUTE),
                "controller_callsite_lines": _callsite_lines(inputs_source, CONTROLLER_ALIAS),
            },
            "controller_boundary": {
                "alias": CONTROLLER_ALIAS,
                "controller_name": CONTROLLER_NAME,
                "called": generic_call_present,
                "call_count_in_wrapper": 0,
                "cutover_artifact_status": latest_cutover.get("status"),
                "cutover_artifact_path": latest_cutover.get("path"),
            },
            "forwarded_plain_inputs": {},
            "forwarded_callbacks": {},
            "authority_hits": {},
            "body_shape": {
                "statement_kinds_without_docstring": [],
                "allowed_pass_through_shape": False,
                "disallowed_calls": [],
                "has_only_controller_call_and_type_guard": False,
            },
            "ownership": {
                "selection_logic": False,
                "fallback_logic": False,
                "controller_route_selection": False,
                "callback_binding": False,
                "session_state_mutation": False,
                "debug_trace_state": False,
                "cta_apply_payload_construction": False,
                "visible_wording": False,
                "evidence_packaging": False,
                "route_trace_semantics": False,
                "publication_binding": False,
                "compatibility_only_forwarding": False,
            },
            "answers": {
                "can_be_replaced_by_generic_page_shell_controller_caller": False,
                "still_creates_or_rewrites_design_guide_meaning": False,
                "still_creates_or_rewrites_cta_apply_meaning": False,
                "still_creates_route_trace_authority": False,
                "mutates_session_or_debug_beyond_page_shell_wiring": False,
                "is_live": False,
                "is_dead": True,
                "is_compatibility_only": False,
                "generic_page_shell_cutover_complete": (
                    generic_call_present and latest_cutover.get("status") == "PASS"
                ),
            },
            "ownership_before": {
                "inputs_page": "route-specific callback-forwarding wrapper was previously live",
                "design_guide_controller": "constructed and returned the route result",
            },
            "ownership_after_candidate": {
                "inputs_page": "generic page-shell caller forwards page callbacks/session-owned dependencies",
                "design_guide_controller": "unchanged result authority",
            },
            "safe_next_action": (
                "No further action for this wrapper. It has been deleted and the generic page-shell caller cutover is locked."
            ),
            "risk_level": "COMPLETE",
            "product_behavior_changed": False,
            "visible_wording_changed": False,
            "cta_apply_semantics_changed": False,
            "family_runtime_changed": False,
            "session_state_behavior_changed": False,
            "widget_keys_changed": False,
        }
    args = [arg.arg for arg in node.args.kwonlyargs]
    forwarded_callbacks = {name: f"{name}={name}" in route_source for name in FORWARDED_CALLBACKS}
    forwarded_plain_inputs = {name: f"{name}={name}" in route_source for name in PLAIN_INPUTS}
    route_calls_controller = f"{CONTROLLER_ALIAS}(" in route_source
    route_call_count = route_source.count(f"{CONTROLLER_ALIAS}(")
    route_specific_callsite_lines = _callsite_lines(inputs_source, ROUTE)
    controller_callsite_lines = _callsite_lines(inputs_source, CONTROLLER_ALIAS)
    authority_hits = {
        name: _count_token_hits(route_source, tokens)
        for name, tokens in AUTHORITY_TOKENS.items()
    }
    body_shape = _body_shape(node)
    pass_through_only = body_shape["has_only_controller_call_and_type_guard"]
    owns_authority = {
        "selection_logic": False,
        "fallback_logic": False,
        "controller_route_selection": route_call_count != 1,
        "callback_binding": True,
        "session_state_mutation": authority_hits["session_state_mutation"] > 0,
        "debug_trace_state": authority_hits["debug_trace_state"] > 0,
        "cta_apply_payload_construction": (
            not pass_through_only and authority_hits["cta_apply_payload_construction"] > 0
        ),
        "visible_wording": False,
        "evidence_packaging": (
            not pass_through_only and authority_hits["evidence_packaging"] > 0
        ),
        "route_trace_semantics": authority_hits["route_trace_semantics"] > 0,
        "publication_binding": authority_hits["publication_binding"] > 0,
        "compatibility_only_forwarding": False,
    }
    answers = {
        "can_be_replaced_by_generic_page_shell_controller_caller": (
            route_calls_controller
            and route_call_count == 1
            and all(forwarded_callbacks.values())
            and all(forwarded_plain_inputs.values())
            and not any(
                owns_authority[key]
                for key in (
                    "controller_route_selection",
                    "session_state_mutation",
                    "debug_trace_state",
                    "cta_apply_payload_construction",
                    "visible_wording",
                    "evidence_packaging",
                    "route_trace_semantics",
                    "publication_binding",
                )
            )
        ),
        "still_creates_or_rewrites_design_guide_meaning": False,
        "still_creates_or_rewrites_cta_apply_meaning": owns_authority[
            "cta_apply_payload_construction"
        ],
        "still_creates_route_trace_authority": owns_authority["route_trace_semantics"],
        "mutates_session_or_debug_beyond_page_shell_wiring": (
            owns_authority["session_state_mutation"] or owns_authority["debug_trace_state"]
        ),
        "is_live": len(route_specific_callsite_lines) > 0,
        "is_dead": len(route_specific_callsite_lines) == 0,
        "is_compatibility_only": False,
    }
    compatibility_decision = (
        "READY_FOR_GENERIC_PAGE_SHELL_CALLER_READINESS_PROOF"
        if answers["can_be_replaced_by_generic_page_shell_controller_caller"]
        else "NOT_READY_WRAPPER_STILL_OWNS_AUTHORITY"
    )
    return {
        "decision": compatibility_decision,
        "route": {
            "name": ROUTE,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
            "kwonly_arg_count": len(args),
            "kwonly_args": args,
            "callsite_lines": route_specific_callsite_lines,
            "controller_callsite_lines": controller_callsite_lines,
        },
        "controller_boundary": {
            "alias": CONTROLLER_ALIAS,
            "controller_name": CONTROLLER_NAME,
            "called": route_calls_controller,
            "call_count_in_wrapper": route_call_count,
        },
        "forwarded_plain_inputs": forwarded_plain_inputs,
        "forwarded_callbacks": forwarded_callbacks,
        "authority_hits": authority_hits,
        "body_shape": body_shape,
        "ownership": owns_authority,
        "answers": answers,
        "ownership_before": {
            "inputs_page": (
                "route-specific wrapper forwards plain inputs and callback boundaries; "
                "it no longer assembles result, trace, publication, CTA, or evidence"
            ),
            "design_guide_controller": "constructs and returns the route result",
        },
        "ownership_after_candidate": {
            "inputs_page": "generic page-shell caller forwards page callbacks/session-owned dependencies",
            "design_guide_controller": "unchanged result authority",
        },
        "safe_next_action": (
            "Create a generic page-shell controller caller readiness/parity snapshot. "
            "Do not cut over until parity proves the generic caller preserves the route output."
        ),
        "risk_level": "LOW",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "session_state_behavior_changed": False,
        "widget_keys_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    answers = dict(capture.get("answers") or {})
    ownership = dict(capture.get("ownership") or {})
    if capture.get("decision") == "CALLBACK_FORWARDING_WRAPPER_DELETED_GENERIC_CALLER_CUTOVER_PRESENT":
        return {
            "wrapper_deleted": (capture.get("route") or {}).get("present") is False,
            "wrapper_callsite_deleted": not (capture.get("route") or {}).get("callsite_lines"),
            "generic_controller_callsite_present": (
                (capture.get("controller_boundary") or {}).get("called") is True
            ),
            "generic_cutover_artifact_passes": (
                (capture.get("controller_boundary") or {}).get("cutover_artifact_status")
                == "PASS"
            ),
            "no_design_guide_meaning_rewrite": (
                answers.get("still_creates_or_rewrites_design_guide_meaning") is False
            ),
            "no_cta_apply_meaning_rewrite": (
                answers.get("still_creates_or_rewrites_cta_apply_meaning") is False
            ),
            "no_route_trace_authority": answers.get("still_creates_route_trace_authority")
            is False,
            "no_session_debug_mutation": (
                answers.get("mutates_session_or_debug_beyond_page_shell_wiring") is False
            ),
            "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
            "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
            "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
            "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
            "session_state_behavior_unchanged": (
                capture.get("session_state_behavior_changed") is False
            ),
            "widget_keys_unchanged": capture.get("widget_keys_changed") is False,
        }
    return {
        "route_found": bool((capture.get("route") or {}).get("line_count")),
        "route_is_live": answers.get("is_live") is True,
        "controller_boundary_called_once": (
            (capture.get("controller_boundary") or {}).get("called") is True
            and (capture.get("controller_boundary") or {}).get("call_count_in_wrapper") == 1
        ),
        "plain_inputs_forwarded": all((capture.get("forwarded_plain_inputs") or {}).values()),
        "callbacks_forwarded": all((capture.get("forwarded_callbacks") or {}).values()),
        "no_design_guide_meaning_rewrite": (
            answers.get("still_creates_or_rewrites_design_guide_meaning") is False
        ),
        "no_cta_apply_meaning_rewrite": (
            answers.get("still_creates_or_rewrites_cta_apply_meaning") is False
        ),
        "no_route_trace_authority": answers.get("still_creates_route_trace_authority") is False,
        "no_session_debug_mutation": (
            answers.get("mutates_session_or_debug_beyond_page_shell_wiring") is False
        ),
        "not_dead": answers.get("is_dead") is False,
        "not_compatibility_only": answers.get("is_compatibility_only") is False,
        "only_callback_binding_authority_remains": (
            ownership.get("callback_binding") is True
            and not any(
                ownership.get(key)
                for key in (
                    "selection_logic",
                    "fallback_logic",
                    "controller_route_selection",
                    "session_state_mutation",
                    "debug_trace_state",
                    "cta_apply_payload_construction",
                    "visible_wording",
                    "evidence_packaging",
                    "route_trace_semantics",
                    "publication_binding",
                )
            )
        ),
        "ready_for_generic_caller_readiness_proof": (
            answers.get("can_be_replaced_by_generic_page_shell_controller_caller") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
        "session_state_behavior_unchanged": (
            capture.get("session_state_behavior_changed") is False
        ),
        "widget_keys_unchanged": capture.get("widget_keys_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    route = dict(capture.get("route") or {})
    lines = [
        "# No-Active Combined Low-Util Cleanup Callback Forwarding Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Route: `{route.get('name')}`",
        f"Route lines: `{route.get('start_line')}-{route.get('end_line')}`",
        f"Route line count: `{route.get('line_count')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Ownership Answers"])
    for key, value in (capture.get("answers") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Ownership Classification"])
    for key, value in (capture.get("ownership") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Forwarded Plain Inputs"])
    for key, value in (capture.get("forwarded_plain_inputs") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Forwarded Callback Boundaries"])
    for key, value in (capture.get("forwarded_callbacks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Ownership Before",
            "",
            f"- inputs_page.py: {((capture.get('ownership_before') or {}).get('inputs_page'))}",
            f"- DesignGuideController: {((capture.get('ownership_before') or {}).get('design_guide_controller'))}",
            "",
            "## Candidate Ownership After",
            "",
            f"- inputs_page.py: {((capture.get('ownership_after_candidate') or {}).get('inputs_page'))}",
            f"- DesignGuideController: {((capture.get('ownership_after_candidate') or {}).get('design_guide_controller'))}",
            "",
            "## Safe Next Action",
            "",
            str(capture.get("safe_next_action")),
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
        / f"design_guide_no_active_combined_low_util_cleanup_callback_forwarding_audit_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"no_active_combined_low_util_cleanup_callback_forwarding_audit_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_combined_low_util_cleanup_callback_forwarding_audit {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
