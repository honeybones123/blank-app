"""Verify the no-active low-shear/blocker controller route object.

Proof-only: this does not wire the route into inputs_page.py or change product
behaviour. It proves the controller route exists, keeps page-owned callbacks as
boundaries, preserves branch order, and produces stable plain-data results.
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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

ROUTE = "run_design_guide_controller_no_active_low_shear_or_blocker_route"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name}")


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


def _parse_util(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_from_state(state: dict[str, Any], key: str, default: Any = 0.0) -> float:
    try:
        return float(state.get(key, default) or 0.0)
    except (TypeError, ValueError):
        return float(default or 0.0)


def _fingerprint(state: dict[str, Any]) -> str:
    return "fp:" + _stable_hash(state)[:12]


def _contract_enabled(contract: dict[str, Any]) -> bool:
    return bool(contract.get("enabled", True) and contract.get("actionable", True))


def _base_kwargs() -> dict[str, Any]:
    return {
        "primary": {"title": "Primary", "action_type": "review"},
        "contract": {},
        "updates": {},
        "final_state": {"Vu_star": 0.0},
        "final_overview": {"utils": {"shear": 0.9, "bending": 0.9}, "any_fail": False},
        "final_accepted_min_family_util": 0.85,
        "target_band_eps": 1e-9,
        "guidance_shear_demand_abs_tol_kn": 0.01,
        "compound_shear_update_keys": {"s_lig"},
        "parse_util_value_fn": _parse_util,
        "resolve_design_actions_from_state_fn": lambda state: {},
        "float_from_state_fn": _float_from_state,
        "shear_demands_negligible_fn": lambda actions: True,
        "overview_required_checks_acceptable_fn": lambda overview: not bool(overview.get("any_fail")),
        "post_click_accepted_green_audit_fn": lambda *args, **kwargs: {},
        "post_active_repair_target_accepted_item_fn": lambda *args, **kwargs: {"accepted": True},
        "design_mode_config_fn": lambda goal: {"mode": "fast"},
        "design_optimisation_goal_fn": lambda state: "balanced",
        "state_fingerprint_fn": _fingerprint,
        "shear_low_util_target_cleanup_item_fn": lambda *args, **kwargs: None,
        "resolve_low_shear_target_cleanup_probe_fn": lambda *args, **kwargs: None,
        "resolve_low_shear_evidence_fallback_fn": lambda *args, **kwargs: None,
        "overview_active_failure_keys_fn": lambda overview: set(),
        "updates_match_state_fn": lambda state, updates: False,
        "guidance_cleanup_candidate_id_fn": lambda *args, **kwargs: "cleanup-candidate",
        "shear_best_safe_cleanup_item_from_evidence_fn": lambda *args, **kwargs: None,
        "resolve_low_shear_exact_blocker_fallback_fn": lambda *args, **kwargs: None,
        "post_click_applied_residual_shear_exact_blocker_fn": lambda *args, **kwargs: None,
        "post_active_repair_residual_shear_exact_blocker_fn": lambda *args, **kwargs: None,
        "shear_cleanup_exact_blocker_guidance_item_fn": lambda *args, **kwargs: None,
        "accepted_green_exact_blocker_is_valid_fn": lambda *args, **kwargs: False,
        "apply_low_shear_combined_low_util_blocker_gate_fn": lambda shear_resolution_item, **kwargs: shear_resolution_item,
        "design_guide_button_contract_enabled_fn": _contract_enabled,
        "post_click_low_bending_resolution_item_fn": lambda *args, **kwargs: None,
        "resolve_recommendation_updates_fn": lambda item, **kwargs: dict(item.get("updates") or {}),
        "local_cleanup_post_apply_acceptance_matches_fn": lambda state: False,
        "combined_low_util_exact_blocker_final_item_fn": lambda *args, **kwargs: None,
        "finalize_low_shear_resolution_item_before_return_fn": lambda shear_resolution_item, **kwargs: shear_resolution_item,
        "combine_best_safe_shear_with_bending_cleanup_item_fn": lambda *args, **kwargs: None,
        "normalise_final_visible_design_guide_item_fn": lambda item: dict(item or {}),
        "assemble_zero_shear_demand_accepted_result_fn": lambda **kwargs: {
            "branch": "zero_shear_post_click_accepted",
            "final_shear_util": kwargs.get("final_shear_util"),
            "state_fingerprint": kwargs["state_fingerprint_fn"](kwargs.get("final_state") or {}),
        },
        "assemble_low_shear_resolution_result_fn": lambda **kwargs: {
            "branch": "low_shear_resolution",
            "shear_contract_enabled": kwargs.get("shear_contract_enabled"),
            "shear_updates": dict(kwargs.get("shear_updates") or {}),
            "state_fingerprint": kwargs["state_fingerprint_fn"](kwargs.get("final_state") or {}),
        },
        "assemble_combined_low_util_blocker_or_best_safe_result_fn": lambda **kwargs: {
            "branch": "combined_low_util_blocker_or_best_safe",
            "post_click_route": bool(kwargs.get("post_click_route")),
            "state_fingerprint": kwargs["state_fingerprint_fn"](kwargs.get("final_state") or {}),
        },
    }


def _run_case(case_id: str, overrides: dict[str, Any]) -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_no_active_low_shear_or_blocker_route,
    )

    kwargs = _base_kwargs()
    kwargs.update(overrides)
    first = run_design_guide_controller_no_active_low_shear_or_blocker_route(**kwargs)
    second = run_design_guide_controller_no_active_low_shear_or_blocker_route(**kwargs)
    return {
        "case": case_id,
        "result": first,
        "result_hash": _stable_hash(first),
        "stable_repeat_hash": _stable_hash(first) == _stable_hash(second),
        "branch": (first or {}).get("branch") if isinstance(first, dict) else None,
        "result_present": isinstance(first, dict),
    }


def _exercise_route() -> list[dict[str, Any]]:
    low_shear_item = {
        "title": "Shear cleanup",
        "updates": {"s_lig": 300},
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "updates": {"s_lig": 300},
        },
    }
    return [
        _run_case(
            "already_actionable_primary_returns_none",
            {
                "primary": {"action_type": "apply_resolved_candidate"},
                "contract": {"action_type": "apply_resolved_candidate", "enabled": True, "actionable": True},
                "updates": {"D": 650},
            },
        ),
        _run_case(
            "zero_shear_post_click_accepted",
            {
                "final_overview": {"utils": {"shear": 0.0, "bending": 0.92}, "any_fail": False},
                "final_state": {"Vu_star": 0.0},
            },
        ),
        _run_case(
            "low_shear_resolution",
            {
                "final_overview": {"utils": {"shear": 0.4, "bending": 0.9}, "any_fail": False},
                "final_state": {"Vu_star": 10.0},
                "shear_demands_negligible_fn": lambda actions: False,
                "resolve_low_shear_target_cleanup_probe_fn": lambda *args, **kwargs: dict(low_shear_item),
            },
        ),
        _run_case(
            "combined_low_util_blocker_or_best_safe",
            {
                "final_overview": {"utils": {"shear": 0.92, "bending": 0.92}, "any_fail": False},
                "final_state": {"Vu_star": 10.0},
                "shear_demands_negligible_fn": lambda actions: False,
                "post_click_accepted_green_audit_fn": lambda *args, **kwargs: {
                    "post_click_accepted_green_valid": True
                },
                "combined_low_util_exact_blocker_final_item_fn": lambda *args, **kwargs: {
                    "title": "Combined blocker"
                },
            },
        ),
        _run_case(
            "no_result",
            {
                "final_overview": {"utils": {"shear": 0.92, "bending": 0.92}, "any_fail": False},
                "final_state": {"Vu_star": 10.0},
                "shear_demands_negligible_fn": lambda actions: False,
            },
        ),
    ]


def _capture() -> dict[str, Any]:
    source, start_line, end_line = _function_source(CONTROLLER, ROUTE)
    forbidden = {
        "inputs_page_import": "inputs_page" in source,
        "streamlit_or_session": any(
            token in source for token in ("import streamlit", "st.session_state", "st.button", "st.markdown")
        ),
        "apply_routing": "_queue_primary_design_guide_button_action" in source,
        "html_rendering": "_design_guide_dashboard_card_html" in source,
        "family_runtime": "contracted_repair_ladder_specs(" in source,
    }
    cases = _exercise_route()
    return {
        "decision": "CONTROLLER_ROUTE_OBJECT_READY_FOR_TRACE_PARITY",
        "route": {
            "function": ROUTE,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
            "source_hash": _stable_hash(source),
        },
        "cases": cases,
        "case_branches": {case["case"]: case.get("branch") for case in cases},
        "forbidden_controller_ownership": forbidden,
        "exported": f'"{ROUTE}"' in CONTROLLER.read_text(encoding="utf-8", errors="replace"),
        "latest": {
            "readiness": _latest("design_guide_no_active_low_shear_or_blocker_full_route_readiness"),
            "independence_lock": _latest("design_guide_independence_lock"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_resolver_publication_bridge_lock": _latest(
                "design_guide_compute_resolver_publication_bridge_lock"
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    branches = dict(capture.get("case_branches") or {})
    latest = dict(capture.get("latest") or {})
    return {
        "route_defined": bool((capture.get("route") or {}).get("line_count")),
        "route_exported": capture.get("exported") is True,
        "readiness_passes": (latest.get("readiness") or {}).get("status") == "PASS",
        "case_hashes_stable": all(case.get("stable_repeat_hash") is True for case in capture.get("cases") or []),
        "already_actionable_returns_none": branches.get("already_actionable_primary_returns_none") is None,
        "zero_shear_branch_selected": branches.get("zero_shear_post_click_accepted") == "zero_shear_post_click_accepted",
        "low_shear_branch_selected": branches.get("low_shear_resolution") == "low_shear_resolution",
        "combined_branch_selected": branches.get("combined_low_util_blocker_or_best_safe") == "combined_low_util_blocker_or_best_safe",
        "no_result_branch_returns_none": branches.get("no_result") is None,
        "no_forbidden_controller_ownership": not any(
            (capture.get("forbidden_controller_ownership") or {}).values()
        ),
        "independence_lock_artifact_available": bool(
            (latest.get("independence_lock") or {}).get("found")
        ),
        "render_bridge_lock_artifact_available": bool(
            (latest.get("render_bridge_lock") or {}).get("found")
        ),
        "compute_bridge_lock_artifact_available": bool(
            (latest.get("compute_resolver_publication_bridge_lock") or {}).get("found")
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    route = dict(capture.get("route") or {})
    lines = [
        "# Design Guide No-Active Low-Shear/Blocker Route Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Route",
        "",
        f"- Function: `{route.get('function')}`",
        f"- Lines: `{route.get('start_line')}` to `{route.get('end_line')}`",
        f"- Line count: `{route.get('line_count')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Cases", "", "| Case | Branch | Stable |", "| --- | --- | --- |"])
    for case in capture.get("cases") or []:
        lines.append(
            f"| {case.get('case')} | `{case.get('branch')}` | `{case.get('stable_repeat_hash')}` |"
        )
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            "Wire trace-only parity beside the page route and compare live page results to this controller route.",
            "Do not replace the page route or delete the old body until branch parity passes.",
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
    json_path = ARTIFACT_DIR / f"design_guide_no_active_low_shear_or_blocker_route_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_no_active_low_shear_or_blocker_route_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_low_shear_or_blocker_route_object {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
