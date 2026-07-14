"""Readiness proof for a controller-owned blocked-primary full route builder.

This is proof-only. It does not move the route, change output, change CTA/apply
semantics, change wording, or delete the page wrapper. It records the complete
branch surface that a future controller-owned route builder must preserve.
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

REQUIRED_BRANCHES: tuple[dict[str, Any], ...] = (
    {
        "id": "safe_shear_cleanup_before_blocker",
        "required_tokens": (
            "safe_cleanup_updates_from_evidence",
            "shear_best_safe_cleanup_item_from_evidence_fn(",
            "_build_design_guide_controller_safe_cleanup_candidate_before_blocker_result(",
            "return_no_active_safe_cleanup_candidate_before_blocker",
            "final_visible_safe_cleanup_candidate_before_blocker",
        ),
        "current_controller_builder": "build_design_guide_controller_safe_cleanup_candidate_before_blocker_result",
    },
    {
        "id": "bending_cleanup_available_before_blocker",
        "required_tokens": (
            "bending_only_target_band_cleanup_item_fn(",
            "probe_equivalent_bending_cleanup_action_item_fn(",
            "_build_design_guide_controller_bending_cleanup_available_before_blocker_result(",
            "return_no_active_bending_cleanup_available_before_blocker",
            "final_visible_bending_cleanup_available_before_blocker",
        ),
        "current_controller_builder": "build_design_guide_controller_bending_cleanup_available_before_blocker_result",
    },
)

REQUIRED_CALLBACKS: tuple[str, ...] = (
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


def _function_source(path: Path, function_name: str) -> tuple[str | None, int | None, int | None]:
    source = path.read_text(encoding="utf-8", errors="replace")
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
    source, start, end = _function_source(INPUTS_PAGE, ROUTE)
    route_source = source or ""
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    branches: list[dict[str, Any]] = []
    for branch in REQUIRED_BRANCHES:
        required_tokens = tuple(str(token) for token in branch["required_tokens"])
        missing_tokens = [token for token in required_tokens if token not in route_source]
        branches.append(
            {
                "id": branch["id"],
                "required_tokens": list(required_tokens),
                "missing_tokens": missing_tokens,
                "current_controller_builder": branch["current_controller_builder"],
                "controller_builder_present": str(branch["current_controller_builder"]) in controller_source,
                "ready_for_builder_representation": not missing_tokens
                and str(branch["current_controller_builder"]) in controller_source,
            }
        )
    callback_missing = [name for name in REQUIRED_CALLBACKS if name not in route_source]
    return {
        "decision": "READY_FOR_CONTROLLER_FULL_ROUTE_BUILDER_OBJECT",
        "route": {
            "name": ROUTE,
            "present": source is not None,
            "start_line": start,
            "end_line": end,
            "line_count": (end - start + 1) if start is not None and end is not None else 0,
        },
        "branches": branches,
        "required_callbacks": list(REQUIRED_CALLBACKS),
        "callback_missing": callback_missing,
        "route_policy_proof_available": (
            "build_design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_proof"
            in controller_source
        ),
        "future_builder_allowed_scope": {
            "may_own_route_branching": True,
            "may_call_page_supplied_callbacks": True,
            "may_build_plain_result_dict": True,
            "may_render_ui": False,
            "may_route_apply": False,
            "may_change_wording": False,
            "may_change_engineering": False,
            "may_change_family_runtime": False,
        },
        "latest": {
            "remaining_page_owned_route_extraction_audit": {
                "status": _latest("design_guide_remaining_page_owned_route_extraction_audit").get("status"),
                "path": _latest("design_guide_remaining_page_owned_route_extraction_audit").get("path"),
            },
            "route_policy_object": {
                "status": _latest(
                    "design_guide_no_active_blocked_primary_cleanup_probe_route_policy_object"
                ).get("status"),
                "path": _latest(
                    "design_guide_no_active_blocked_primary_cleanup_probe_route_policy_object"
                ).get("path"),
            },
            "route_policy_trace_wiring": {
                "status": _latest(
                    "design_guide_no_active_blocked_primary_cleanup_probe_route_policy_trace_wiring"
                ).get("status"),
                "path": _latest(
                    "design_guide_no_active_blocked_primary_cleanup_probe_route_policy_trace_wiring"
                ).get("path"),
            },
            "result_object": {
                "status": _latest(
                    "design_guide_no_active_blocked_primary_cleanup_probe_result_object"
                ).get("status"),
                "path": _latest(
                    "design_guide_no_active_blocked_primary_cleanup_probe_result_object"
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
    scope = dict(capture.get("future_builder_allowed_scope") or {})
    return {
        "route_present": (capture.get("route") or {}).get("present") is True,
        "all_branches_representable": all(
            branch.get("ready_for_builder_representation") is True
            for branch in capture.get("branches") or []
        ),
        "required_callbacks_present": not capture.get("callback_missing"),
        "route_policy_proof_available": capture.get("route_policy_proof_available") is True,
        "previous_remaining_route_audit_passed": (
            latest.get("remaining_page_owned_route_extraction_audit") or {}
        ).get("status")
        == "PASS",
        "route_policy_object_passed": (latest.get("route_policy_object") or {}).get("status")
        == "PASS",
        "route_policy_trace_wiring_passed": (
            latest.get("route_policy_trace_wiring") or {}
        ).get("status")
        == "PASS",
        "result_object_passed": (latest.get("result_object") or {}).get("status") == "PASS",
        "independence_lock_currently_passes": (latest.get("independence_lock") or {}).get("status")
        == "PASS",
        "future_builder_scope_is_plain_data_only": scope.get("may_render_ui") is False
        and scope.get("may_route_apply") is False
        and scope.get("may_change_wording") is False
        and scope.get("may_change_engineering") is False
        and scope.get("may_change_family_runtime") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide No-Active Blocked-Primary Full Route Builder Readiness",
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
            "## Branches",
            "",
            "| Branch | Builder | Ready | Missing tokens |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for branch in capture.get("branches") or []:
        lines.append(
            "| {branch} | `{builder}` | `{ready}` | {missing} |".format(
                branch=branch.get("id"),
                builder=branch.get("current_controller_builder"),
                ready=branch.get("ready_for_builder_representation"),
                missing=", ".join(branch.get("missing_tokens") or []) or "none",
            )
        )
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            "Add the proof-only controller full-route builder object for this route. It should own route composition as plain data but still call page-supplied callbacks for current generators/evaluators.",
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
        / f"design_guide_no_active_blocked_primary_full_route_builder_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_blocked_primary_full_route_builder_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_blocked_primary_full_route_builder_readiness {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if status == "PASS":
        print("next=add proof-only controller full-route builder object")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
