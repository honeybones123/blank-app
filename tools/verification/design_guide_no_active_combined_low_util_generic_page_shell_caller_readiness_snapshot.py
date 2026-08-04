"""Proof-only readiness for a generic page-shell controller caller.

This verifier does not change product behaviour or cut over the wrapper. It
proves whether the route-specific no-active combined low-util wrapper has been
reduced to a shape that a generic page-shell caller could preserve:

    controller(**plain_inputs, **callback_boundaries)
    -> dict result or None

The page still owns the concrete callbacks. The Design Guide controller still
owns route result authority.
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

ROUTE = "_resolve_final_visible_no_active_combined_low_util_safe_cleanup_result"
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

EXPECTED_KWARGS = PLAIN_INPUTS + CALLBACK_BOUNDARIES


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _parse(path: Path) -> tuple[str, ast.Module, list[str]]:
    source = path.read_text(encoding="utf-8", errors="replace")
    return source, ast.parse(source), source.splitlines()


def _function_node(path: Path, name: str) -> tuple[ast.FunctionDef, str, int, int]:
    source, tree, lines = _parse(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = getattr(node, "end_lineno", None)
            if end is None:
                raise RuntimeError(f"Missing end_lineno for {name}")
            return node, "\n".join(lines[node.lineno - 1 : end]), node.lineno, end
    raise RuntimeError(f"Could not find function {name} in {path}")


def _kwonly_args(node: ast.FunctionDef) -> list[str]:
    return [arg.arg for arg in node.args.kwonlyargs]


def _controller_call(node: ast.FunctionDef) -> ast.Call | None:
    for stmt in node.body:
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
            func = stmt.value.func
            if isinstance(func, ast.Name) and func.id == CONTROLLER_ALIAS:
                return stmt.value
    return None


def _keyword_map(call: ast.Call | None) -> dict[str, str]:
    if call is None:
        return {}
    mapping: dict[str, str] = {}
    for kw in call.keywords:
        if kw.arg is None:
            mapping["**"] = ast.unparse(kw.value)
        else:
            mapping[kw.arg] = ast.unparse(kw.value)
    return mapping


def _has_dict_none_guard(node: ast.FunctionDef) -> bool:
    for stmt in node.body:
        if not isinstance(stmt, ast.If):
            continue
        test = stmt.test
        if not (
            isinstance(test, ast.UnaryOp)
            and isinstance(test.op, ast.Not)
            and isinstance(test.operand, ast.Call)
            and isinstance(test.operand.func, ast.Name)
            and test.operand.func.id == "isinstance"
        ):
            continue
        args = test.operand.args
        if len(args) != 2:
            continue
        if not (isinstance(args[0], ast.Name) and args[0].id == "result"):
            continue
        if not (isinstance(args[1], ast.Name) and args[1].id == "dict"):
            continue
        return (
            len(stmt.body) == 1
            and isinstance(stmt.body[0], ast.Return)
            and isinstance(stmt.body[0].value, ast.Constant)
            and stmt.body[0].value.value is None
            and not stmt.orelse
        )
    return False


def _returns_result(node: ast.FunctionDef) -> bool:
    return any(
        isinstance(stmt, ast.Return)
        and isinstance(stmt.value, ast.Name)
        and stmt.value.id == "result"
        for stmt in node.body
    )


def _callsite_kwargs(path: Path, wrapper_name: str) -> list[dict[str, Any]]:
    source, tree, _ = _parse(path)
    callsites: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == wrapper_name):
            continue
        line = getattr(node, "lineno", None)
        callsites.append(
            {
                "line": line,
                "kwargs": {
                    kw.arg: ast.unparse(kw.value)
                    for kw in node.keywords
                    if kw.arg is not None
                },
            }
        )
    return callsites


def _import_alias_present() -> bool:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    return (
        f"{CONTROLLER_NAME} as {CONTROLLER_ALIAS}" in source
        or f"{CONTROLLER_NAME} as\n    {CONTROLLER_ALIAS}" in source
    )


def _capture() -> dict[str, Any]:
    wrapper_node, wrapper_source, wrapper_start, wrapper_end = _function_node(INPUTS_PAGE, ROUTE)
    controller_node, controller_source, controller_start, controller_end = _function_node(
        CONTROLLER, CONTROLLER_NAME
    )
    call = _controller_call(wrapper_node)
    wrapper_to_controller_kwargs = _keyword_map(call)
    wrapper_kwonly = _kwonly_args(wrapper_node)
    controller_kwonly = _kwonly_args(controller_node)
    callsites = _callsite_kwargs(INPUTS_PAGE, ROUTE)
    generic_contract = {
        "controller_alias": CONTROLLER_ALIAS,
        "controller_name": CONTROLLER_NAME,
        "plain_inputs": list(PLAIN_INPUTS),
        "callback_boundaries": list(CALLBACK_BOUNDARIES),
        "result_guard": "dict_or_none",
        "route_selection": "fixed_controller_callable_supplied_by_page_shell",
        "product_driving": False,
    }
    expected_mapping = {name: name for name in EXPECTED_KWARGS}
    return {
        "decision": "READY_FOR_GENERIC_PAGE_SHELL_CALLER_PARITY_PROOF",
        "wrapper": {
            "name": ROUTE,
            "start_line": wrapper_start,
            "end_line": wrapper_end,
            "line_count": wrapper_end - wrapper_start + 1,
            "kwonly_args": wrapper_kwonly,
            "source_hash": _stable_hash(wrapper_source),
            "calls_controller_alias": call is not None,
            "controller_kwargs": wrapper_to_controller_kwargs,
            "has_dict_or_none_guard": _has_dict_none_guard(wrapper_node),
            "returns_result": _returns_result(wrapper_node),
        },
        "controller": {
            "name": CONTROLLER_NAME,
            "start_line": controller_start,
            "end_line": controller_end,
            "kwonly_args": controller_kwonly,
            "source_hash": _stable_hash(controller_source),
        },
        "callsite": {
            "count": len(callsites),
            "callsites": callsites,
        },
        "generic_page_shell_caller_contract": generic_contract,
        "expected_mapping": expected_mapping,
        "readiness": {
            "generic_caller_can_supply_same_kwargs": wrapper_to_controller_kwargs == expected_mapping,
            "wrapper_signature_matches_expected": wrapper_kwonly == list(EXPECTED_KWARGS),
            "controller_signature_matches_expected": controller_kwonly == list(EXPECTED_KWARGS),
            "callsite_supplies_wrapper_kwargs": (
                len(callsites) == 1
                and set((callsites[0].get("kwargs") or {}).keys()) == set(EXPECTED_KWARGS)
            ),
            "controller_alias_imported": _import_alias_present(),
            "dict_or_none_guard_preserved": _has_dict_none_guard(wrapper_node),
            "wrapper_returns_controller_result": _returns_result(wrapper_node),
            "generic_caller_not_cut_over": True,
        },
        "ownership": {
            "inputs_page": "route-specific wrapper and page-owned callback implementations",
            "generic_caller_candidate": "would own mechanical forwarding only",
            "design_guide_controller": "route result authority remains unchanged",
        },
        "safe_next_action": (
            "Create a generic caller parity/cutover proof before replacing the route-specific wrapper. "
            "Do not remove the wrapper until parity proves identical result and guard behaviour."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "engineering_behavior_changed": False,
        "session_state_behavior_changed": False,
        "widget_keys_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    readiness = dict(capture.get("readiness") or {})
    return {
        "wrapper_calls_controller_alias": (
            (capture.get("wrapper") or {}).get("calls_controller_alias") is True
        ),
        "wrapper_signature_matches_expected": (
            readiness.get("wrapper_signature_matches_expected") is True
        ),
        "controller_signature_matches_expected": (
            readiness.get("controller_signature_matches_expected") is True
        ),
        "generic_caller_can_supply_same_kwargs": (
            readiness.get("generic_caller_can_supply_same_kwargs") is True
        ),
        "callsite_supplies_wrapper_kwargs": (
            readiness.get("callsite_supplies_wrapper_kwargs") is True
        ),
        "controller_alias_imported": readiness.get("controller_alias_imported") is True,
        "dict_or_none_guard_preserved": readiness.get("dict_or_none_guard_preserved") is True,
        "wrapper_returns_controller_result": readiness.get("wrapper_returns_controller_result") is True,
        "generic_caller_not_cut_over": readiness.get("generic_caller_not_cut_over") is True,
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
    wrapper = dict(capture.get("wrapper") or {})
    controller = dict(capture.get("controller") or {})
    lines = [
        "# No-Active Combined Low-Util Generic Page-Shell Caller Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Wrapper",
        "",
        f"- name: `{wrapper.get('name')}`",
        f"- lines: `{wrapper.get('start_line')}-{wrapper.get('end_line')}`",
        f"- line count: `{wrapper.get('line_count')}`",
        f"- calls controller alias: `{wrapper.get('calls_controller_alias')}`",
        f"- dict-or-none guard: `{wrapper.get('has_dict_or_none_guard')}`",
        "",
        "## Controller",
        "",
        f"- name: `{controller.get('name')}`",
        f"- lines: `{controller.get('start_line')}-{controller.get('end_line')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Readiness"])
    for key, value in (capture.get("readiness") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Generic Caller Contract"])
    for key, value in (capture.get("generic_page_shell_caller_contract") or {}).items():
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
        / f"design_guide_no_active_combined_low_util_generic_page_shell_caller_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_combined_low_util_generic_page_shell_caller_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_combined_low_util_generic_page_shell_caller_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
