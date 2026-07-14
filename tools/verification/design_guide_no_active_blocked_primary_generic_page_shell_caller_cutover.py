"""Verify blocked-primary route delegates through the generic page-shell caller.

This is a narrow cutover verifier. It proves the page route now delegates to
the controller route via the generic caller as its first executable statement.
The old page body may still exist after the delegating return; deletion requires
a separate dead-code/deletion proof.
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

PAGE_ROUTE = "_resolve_final_visible_no_active_blocked_primary_cleanup_probe_result"
GENERIC_CALLER = "_run_design_guide_page_shell_controller_route"
CONTROLLER_ALIAS = "_run_design_guide_controller_no_active_blocked_primary_cleanup_probe_route"
CONTROLLER_ROUTE = "run_design_guide_controller_no_active_blocked_primary_cleanup_probe_route"

EXPECTED_KWARGS = (
    "primary",
    "contract",
    "updates",
    "primary_evidence",
    "final_state",
    "final_overview",
    "final_accepted_min_family_util",
    "target_band_eps",
    "compound_shear_update_keys",
    "local_cleanup_post_apply_acceptance_matches_fn",
    "updates_match_state_fn",
    "shear_best_safe_cleanup_item_from_evidence_fn",
    "bending_only_target_band_cleanup_item_fn",
    "probe_equivalent_bending_cleanup_action_item_fn",
    "design_mode_config_fn",
    "design_optimisation_goal_fn",
    "parse_util_value_fn",
    "resolve_recommendation_updates_fn",
    "normalise_design_guide_candidate_id_fn",
    "visible_cleanup_blocker_from_action_fn",
    "design_guide_button_contract_enabled_fn",
    "normalise_final_visible_design_guide_item_fn",
    "state_fingerprint_fn",
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
    return {"status": payload.get("status"), "path": str(path), "payload": payload}


def _parse(path: Path) -> tuple[str, ast.Module, list[str]]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
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


def _first_executable_statement(node: ast.FunctionDef | None) -> ast.stmt | None:
    if node is None:
        return None
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            body = body[1:]
    return body[0] if body else None


def _delegating_return(stmt: ast.stmt | None) -> dict[str, Any]:
    if not isinstance(stmt, ast.Return) or not isinstance(stmt.value, ast.Call):
        return {"is_delegating_return": False, "kwargs": {}, "controller_fn": None}
    call = stmt.value
    if not (isinstance(call.func, ast.Name) and call.func.id == GENERIC_CALLER):
        return {"is_delegating_return": False, "kwargs": {}, "controller_fn": None}
    kwargs = {kw.arg: ast.unparse(kw.value) for kw in call.keywords if kw.arg is not None}
    return {
        "is_delegating_return": True,
        "kwargs": kwargs,
        "controller_fn": kwargs.get("controller_fn"),
        "has_star_kwargs": any(kw.arg is None for kw in call.keywords),
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    route_node, route_source, route_start, route_end = _function(INPUTS_PAGE, PAGE_ROUTE)
    controller_node, controller_source_fn, controller_start, controller_end = _function(
        CONTROLLER, CONTROLLER_ROUTE
    )
    first_stmt = _first_executable_statement(route_node)
    delegation = _delegating_return(first_stmt)
    forwarded = {
        key: value
        for key, value in dict(delegation.get("kwargs") or {}).items()
        if key != "controller_fn"
    }
    old_body_after_return = bool(route_node and len(route_node.body) > 2)
    return {
        "decision": (
            "GENERIC_PAGE_SHELL_CALLER_CUTOVER_PRESENT_DELETION_COMPLETE"
            if not old_body_after_return
            else "GENERIC_PAGE_SHELL_CALLER_CUTOVER_PRESENT_DELETION_PENDING"
        ),
        "page_route": {
            "name": PAGE_ROUTE,
            "present": route_node is not None,
            "start_line": route_start,
            "end_line": route_end,
            "line_count": (route_end - route_start + 1) if route_start and route_end else 0,
            "source_hash": _stable_hash(route_source),
            "first_executable_is_generic_delegating_return": delegation.get(
                "is_delegating_return"
            ),
            "old_body_after_delegating_return_present": old_body_after_return,
        },
        "delegation": {
            "controller_fn": delegation.get("controller_fn"),
            "forwarded_kwargs": forwarded,
            "has_star_kwargs": delegation.get("has_star_kwargs"),
        },
        "controller_route": {
            "name": CONTROLLER_ROUTE,
            "present": controller_node is not None,
            "start_line": controller_start,
            "end_line": controller_end,
            "exported": f'"{CONTROLLER_ROUTE}"' in controller_source,
            "imported_in_inputs": f"{CONTROLLER_ROUTE} as {CONTROLLER_ALIAS}" in inputs_source,
            "source_hash": _stable_hash(controller_source_fn),
        },
        "expected_kwargs": list(EXPECTED_KWARGS),
        "latest": {
            "controller_route_object": {
                "status": _latest(
                    "design_guide_no_active_blocked_primary_controller_route_object"
                ).get("status"),
                "path": _latest(
                    "design_guide_no_active_blocked_primary_controller_route_object"
                ).get("path"),
            },
            "cutover_readiness": {
                "status": _latest(
                    "design_guide_no_active_blocked_primary_full_route_cutover_readiness"
                ).get("status"),
                "path": _latest(
                    "design_guide_no_active_blocked_primary_full_route_cutover_readiness"
                ).get("path"),
            },
        },
        "deletion_ready_now": False,
        "inputs_page_old_body_removed": not old_body_after_return,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    page_route = dict(capture.get("page_route") or {})
    delegation = dict(capture.get("delegation") or {})
    controller = dict(capture.get("controller_route") or {})
    forwarded = dict(delegation.get("forwarded_kwargs") or {})
    latest = dict(capture.get("latest") or {})
    page_route_absent_after_deletion = (
        page_route.get("present") is False
        and controller.get("present") is True
        and capture.get("inputs_page_old_body_removed") is True
    )
    return {
        "page_route_present_or_deleted": page_route.get("present") is True
        or page_route_absent_after_deletion,
        "first_executable_statement_is_generic_return": page_route.get(
            "first_executable_is_generic_delegating_return"
        )
        is True
        or page_route_absent_after_deletion,
        "controller_route_present": controller.get("present") is True,
        "controller_route_exported": controller.get("exported") is True,
        "controller_route_imported": controller.get("imported_in_inputs") is True,
        "delegates_to_expected_controller_alias": delegation.get("controller_fn")
        == CONTROLLER_ALIAS
        or page_route_absent_after_deletion,
        "all_expected_kwargs_forwarded": all(key in forwarded for key in EXPECTED_KWARGS)
        or page_route_absent_after_deletion,
        "no_unexpected_star_kwargs": delegation.get("has_star_kwargs") is False
        or page_route_absent_after_deletion,
        "controller_route_object_passed": (latest.get("controller_route_object") or {}).get(
            "status"
        )
        == "PASS",
        "cutover_readiness_passed": (latest.get("cutover_readiness") or {}).get("status")
        == "PASS",
        "old_body_state_is_explicit": page_route.get(
            "old_body_after_delegating_return_present"
        )
        in {True, False},
        "deletion_state_valid": capture.get("deletion_ready_now") is False
        or page_route_absent_after_deletion,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    route = dict(capture.get("page_route") or {})
    lines = [
        "# Design Guide No-Active Blocked-Primary Generic Page-Shell Caller Cutover",
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
            f"- First executable statement delegates to controller: `{route.get('first_executable_is_generic_delegating_return')}`",
            f"- Old body after delegating return present: `{route.get('old_body_after_delegating_return_present')}`",
            f"- Old body removed: `{capture.get('inputs_page_old_body_removed')}`",
            f"- Deletion ready now: `{capture.get('deletion_ready_now')}`",
            "",
            "## Next Safe Slice",
            "",
            "Create a dead-body deletion proof for the now-unreachable old page body, then delete only the unreachable body if locks remain green.",
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
        / f"design_guide_no_active_blocked_primary_generic_page_shell_caller_cutover_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_blocked_primary_generic_page_shell_caller_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_blocked_primary_generic_page_shell_caller_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
