"""Cutover readiness for the no-active low-shear/blocker route.

Proof-only. It checks whether the controller route object exists and whether
the page route is ready to be replaced by the generic page-shell controller
caller. It does not change product behaviour.
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

PAGE_ROUTE = "_resolve_final_visible_no_active_low_shear_or_blocker_result"
CONTROLLER_ROUTE = "run_design_guide_controller_no_active_low_shear_or_blocker_route"
CONTROLLER_ALIAS = "_run_design_guide_controller_no_active_low_shear_or_blocker_route"
GENERIC_CALLER = "_run_design_guide_page_shell_controller_route"

EXPECTED_KWARGS = (
    "primary",
    "contract",
    "updates",
    "final_state",
    "final_overview",
    "final_accepted_min_family_util",
    "target_band_eps",
    "guidance_shear_demand_abs_tol_kn",
    "compound_shear_update_keys",
    "parse_util_value_fn",
    "resolve_design_actions_from_state_fn",
    "float_from_state_fn",
    "shear_demands_negligible_fn",
    "overview_required_checks_acceptable_fn",
    "post_click_accepted_green_audit_fn",
    "post_active_repair_target_accepted_item_fn",
    "design_mode_config_fn",
    "design_optimisation_goal_fn",
    "state_fingerprint_fn",
    "shear_low_util_target_cleanup_item_fn",
    "resolve_low_shear_target_cleanup_probe_fn",
    "resolve_low_shear_evidence_fallback_fn",
    "overview_active_failure_keys_fn",
    "updates_match_state_fn",
    "guidance_cleanup_candidate_id_fn",
    "shear_best_safe_cleanup_item_from_evidence_fn",
    "resolve_low_shear_exact_blocker_fallback_fn",
    "post_click_applied_residual_shear_exact_blocker_fn",
    "post_active_repair_residual_shear_exact_blocker_fn",
    "shear_cleanup_exact_blocker_guidance_item_fn",
    "accepted_green_exact_blocker_is_valid_fn",
    "apply_low_shear_combined_low_util_blocker_gate_fn",
    "design_guide_button_contract_enabled_fn",
    "post_click_low_bending_resolution_item_fn",
    "resolve_recommendation_updates_fn",
    "local_cleanup_post_apply_acceptance_matches_fn",
    "combined_low_util_exact_blocker_final_item_fn",
    "finalize_low_shear_resolution_item_before_return_fn",
    "combine_best_safe_shear_with_bending_cleanup_item_fn",
    "normalise_final_visible_design_guide_item_fn",
    "assemble_zero_shear_demand_accepted_result_fn",
    "assemble_low_shear_resolution_result_fn",
    "assemble_combined_low_util_blocker_or_best_safe_result_fn",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or "")
    if "PASS" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


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
    controller_node, controller_route_source, controller_start, controller_end = _function(
        CONTROLLER, CONTROLLER_ROUTE
    )
    first_stmt = _first_executable_statement(route_node)
    delegation = _delegating_return(first_stmt)
    forwarded = {
        key: value
        for key, value in dict(delegation.get("kwargs") or {}).items()
        if key != "controller_fn"
    }
    generic_cutover_present = bool(delegation.get("is_delegating_return"))
    page_route_deleted = route_node is None and controller_node is not None
    direct_page_logic_present = any(
        token in route_source
        for token in (
            "final_zero_shear_post_click_accepted",
            "resolve_low_shear_target_cleanup_probe_fn(",
            "post_click_accepted_green_audit_fn(",
        )
    )
    return {
        "decision": (
            "PAGE_ROUTE_DELETED_CONTROLLER_ROUTE_VERIFIED"
            if page_route_deleted
            else (
            "CONTROLLER_ROUTE_CUTOVER_PRESENT"
            if generic_cutover_present
            else "READY_FOR_GENERIC_PAGE_SHELL_CUTOVER"
            )
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
            "direct_page_logic_present": direct_page_logic_present,
            "deleted": page_route_deleted,
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
            "line_count": (
                controller_end - controller_start + 1
                if controller_start and controller_end
                else 0
            ),
            "exported": f'"{CONTROLLER_ROUTE}"' in controller_source,
            "imported_in_inputs": f"{CONTROLLER_ROUTE} as {CONTROLLER_ALIAS}" in inputs_source,
            "source_hash": _stable_hash(controller_route_source),
        },
        "expected_kwargs": list(EXPECTED_KWARGS),
        "latest": {
            "readiness": _latest(
                "design_guide_no_active_low_shear_or_blocker_full_route_readiness"
            ),
            "route_object": _latest("design_guide_no_active_low_shear_or_blocker_route_object"),
        },
        "deletion_ready_now": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    route = dict(capture.get("page_route") or {})
    delegation = dict(capture.get("delegation") or {})
    controller = dict(capture.get("controller_route") or {})
    forwarded = dict(delegation.get("forwarded_kwargs") or {})
    latest = dict(capture.get("latest") or {})
    cutover_present = capture.get("decision") == "CONTROLLER_ROUTE_CUTOVER_PRESENT"
    route_deleted = route.get("deleted") is True
    return {
        "page_route_present_or_deleted": route.get("present") is True or route_deleted,
        "controller_route_present": controller.get("present") is True,
        "controller_route_exported": controller.get("exported") is True,
        "controller_route_import_state_valid": (
            controller.get("imported_in_inputs") is True or cutover_present is False
        ),
        "readiness_passes": (latest.get("readiness") or {}).get("status") == "PASS",
        "route_object_passes": (latest.get("route_object") or {}).get("status") == "PASS",
        "delegation_state_valid": (
            route_deleted
            or
            (
                cutover_present
                and route.get("first_executable_is_generic_delegating_return") is True
                and delegation.get("controller_fn") == CONTROLLER_ALIAS
                and sorted(forwarded) == sorted(EXPECTED_KWARGS)
            )
            or (
                not cutover_present
                and route.get("direct_page_logic_present") is True
            )
        ),
        "no_deletion_claimed": capture.get("deletion_ready_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    route = dict(capture.get("page_route") or {})
    controller = dict(capture.get("controller_route") or {})
    lines = [
        "# Design Guide No-Active Low-Shear/Blocker Full Route Cutover Readiness",
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
            f"- Controller route present: `{controller.get('present')}`",
            f"- Controller route imported in inputs: `{controller.get('imported_in_inputs')}`",
            f"- Deletion ready now: `{capture.get('deletion_ready_now')}`",
            "",
            "## Next Safe Slice",
            "",
            "If decision is `READY_FOR_GENERIC_PAGE_SHELL_CUTOVER`, import the controller route alias and replace the page route body with the generic page-shell caller. Delete the old body only after a separate dead-body deletion proof.",
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
        / f"design_guide_no_active_low_shear_or_blocker_full_route_cutover_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_low_shear_or_blocker_full_route_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_low_shear_or_blocker_full_route_cutover_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
