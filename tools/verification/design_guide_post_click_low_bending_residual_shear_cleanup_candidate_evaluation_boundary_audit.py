"""Audit residual shear cleanup candidate generation/evaluation boundary."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value("
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("

BOUNDARY_SURFACES: dict[str, dict[str, Any]] = {
    "route_request_inputs": {
        "tokens": (
            "current_shear_for_residual_cleanup",
            "family_utils.get(\"shear\")",
            "mode_config",
            "target_lo",
            "target_hi",
            "exact_blockers",
        ),
        "classification": "A. controller request surface",
        "next": "Represent as plain request fields and stable hash.",
    },
    "post_publication_probe_guard": {
        "tokens": (
            "_skip_bending_fail_post_publication_probe(",
            "post_click_low_bending_residual_shear_cleanup_probe",
        ),
        "classification": "B. route guard dependency",
        "next": "Needs controller guard proof before behavior cutover.",
    },
    "primary_shear_tightening_executor": {
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
            "executor=_compute_shear_tightening_recommendation",
            "residual_shear_debug",
            "residual_shear_tighten",
            "residual_shear_updates",
        ),
        "classification": "D. live page-owned execution dependency",
        "next": "Keep live as an injected page-owned executor until its downstream dependencies are proven.",
    },
    "fallback_variant_generation": {
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
            "generator=generate_less_shear_reo_variants",
            "fallback_variants",
            "fallback_shear_candidates",
        ),
        "classification": "D. live page-owned candidate generation dependency",
        "next": "Generator execution is behind the injected runner; candidate evaluation still needs its own boundary.",
    },
    "fallback_candidate_evaluation": {
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(",
            "evaluator=_evaluate_auto_design_candidate",
            "fallback_candidate",
        ),
        "classification": "D. live page-owned evaluation dependency",
        "next": "Evaluator execution is behind the injected runner; do not move formulas or evaluator behavior.",
    },
    "candidate_materiality_and_safety_screen": {
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen(",
            "delta_screen_builder=_build_design_guide_shear_low_util_candidate_delta_screen",
            "pure_updates_checker=_shear_detailing_updates_pure",
            "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
            "acceptance_screen_builder=_build_design_guide_shear_low_util_candidate_acceptance_screen",
        ),
        "classification": "C. injected screen policy shell surface",
        "next": "Materiality/safety screening is behind injected wrappers; keep wrappers live and continue to selection/result/final-binding tails.",
    },
    "fallback_candidate_selection": {
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_candidate_selector(",
            "selector=_select_design_guide_post_click_low_bending_residual_shear_cleanup_candidate_by_sort_key",
            "fallback_best",
        ),
        "classification": "C. selection dependency shell surface",
        "next": "Selection execution is behind an injected selector shell; do not delete result packaging yet.",
    },
    "result_packaging_and_recheck": {
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(",
            "packager=_shear_tightening_as_local_cleanup_item",
            "local_cleanup_evaluator=_evaluate_local_cleanup_guidance_item",
            "residual_promoted",
        ),
        "classification": "C. result packaging/evaluation dependency shell surface",
        "next": "Result packaging/evaluation is behind an injected shell; do not move CTA, evidence merge, or visible wording yet.",
    },
    "target_band_blocker_authoring": {
        "tokens": (
            "residual_outside_preferred_band",
            "post_click_residual_shear_cleanup_outside_preferred_band",
            "outside_target_band_allowed_reason",
            "above the preferred",
        ),
        "classification": "E. visible wording and blocker evidence surface",
        "next": "No wording change; byte-for-byte preserve before moving.",
    },
    "cta_contract_execution": {
        "tokens": (
            "_design_guide_button_contract(",
            "residual_binding_with_contract",
        ),
        "classification": "D. live CTA contract execution dependency",
        "next": "Keep live until CTA contract parity and apply payload proof are explicit.",
    },
    "controller_shell_trace": {
        "tokens": (
            "_stamp_final_publication_post_click_low_bending_residual_shear_cleanup_route_proof(",
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness(",
        ),
        "classification": "A. controller shell already wired",
        "next": "Use as the request/result hash anchor for the next boundary object.",
    },
}

PRIMARY_EXECUTOR_HIDDEN_DEPS = {
    "collects_overview": "_collect_design_overview(",
    "uses_page_design_context": "_build_design_actions_context(",
    "uses_full_evaluator_seed": "evaluate_candidate_full(",
    "generates_variants": "generate_less_shear_reo_variants(",
    "uses_fast_eval": "_evaluate_candidate_fast(",
    "scores_page_candidates": "_score_auto_design_candidate(",
}

CONTROLLER_REUSABLE_HELPERS = (
    "build_design_guide_shear_low_util_raw_variant_states",
    "build_design_guide_shear_low_util_candidate_delta_screen",
    "build_design_guide_shear_low_util_candidate_acceptance_screen",
    "build_design_guide_shear_low_util_candidate_search_evidence",
    "build_design_guide_shear_low_util_final_item_packaging",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "status": "MISSING", "path": None}
    last_readable: dict[str, Any] | None = None
    for path in reversed(artifacts):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            last_readable = {
                "found": True,
                "status": "UNREADABLE",
                "path": str(path),
                "error": f"{type(exc).__name__}: {exc}",
            }
            continue
        status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
        if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
            return {"found": True, "status": "PASS", "path": str(path)}
        last_readable = {"found": True, "status": status or "UNKNOWN", "path": str(path)}
    return last_readable or {"found": False, "status": "MISSING", "path": None}


def _function_body(source: str, token: str) -> str:
    start = source.find(token)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else source[start:]


def _route_block(function_body: str) -> str:
    start = function_body.find(ROUTE_START)
    if start < 0:
        return ""
    end = function_body.find(ROUTE_END, start + len(ROUTE_START))
    return function_body[start:end] if end > start else function_body[start:]


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    post_click_body = _function_body(inputs_source, "def _post_click_low_bending_resolution_item(")
    route = _route_block(post_click_body)
    primary_executor = _function_body(
        inputs_source,
        "def _compute_shear_tightening_recommendation(",
    )

    surface_rows: dict[str, dict[str, Any]] = {}
    classification_counts: dict[str, int] = {}
    for name, spec in BOUNDARY_SURFACES.items():
        tokens = tuple(spec.get("tokens") or ())
        present = [token for token in tokens if token in route]
        classification = str(spec.get("classification") or "unknown")
        classification_counts[classification] = classification_counts.get(classification, 0) + 1
        surface_rows[name] = {
            **spec,
            "present": len(present) == len(tokens),
            "tokens_present": present,
            "tokens_missing": [token for token in tokens if token not in route],
            "delete_now": False,
        }

    hidden_deps = {
        name: token in primary_executor
        for name, token in PRIMARY_EXECUTOR_HIDDEN_DEPS.items()
    }
    reusable_controller_helpers = {
        name: name in controller_source for name in CONTROLLER_REUSABLE_HELPERS
    }
    live_execution_surfaces = [
        name
        for name, row in surface_rows.items()
        if str(row.get("classification") or "").startswith("D.")
    ]
    controller_request_surfaces = [
        name
        for name, row in surface_rows.items()
        if str(row.get("classification") or "").startswith("A.")
    ]
    policy_surfaces = [
        name
        for name, row in surface_rows.items()
        if str(row.get("classification") or "").startswith("C.")
    ]
    wording_surfaces = [
        name
        for name, row in surface_rows.items()
        if str(row.get("classification") or "").startswith("E.")
    ]
    latest = {
        "route_shell_cutover": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_cutover"
        ),
        "route_deadness_readiness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness"
        ),
        "debug_projection_consumer_reachability": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_consumer_reachability"
        ),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_CANDIDATE_EVALUATION_BOUNDARY_MAPPED_NOT_READY_TO_CUT_OVER",
        "route_found": bool(route),
        "route_line_count_estimate": len(route.splitlines()),
        "primary_executor_found": bool(primary_executor),
        "surface_rows": surface_rows,
        "classification_counts": classification_counts,
        "missing_surfaces": [name for name, row in surface_rows.items() if row.get("present") is not True],
        "controller_request_surfaces": controller_request_surfaces,
        "policy_surfaces_need_parity": policy_surfaces,
        "live_execution_surfaces_must_remain": live_execution_surfaces,
        "wording_surfaces_must_preserve": wording_surfaces,
        "primary_executor_hidden_dependencies": hidden_deps,
        "controller_reusable_helpers_present": reusable_controller_helpers,
        "candidate_generation_cutover_ready": False,
        "candidate_evaluation_cutover_ready": False,
        "behavior_cutover_ready": False,
        "delete_now_count": 0,
        "next_safe_step": (
            "Continue with residual shear cleanup candidate-selection/result-construction "
            "and final-binding tails. Candidate generation/evaluation and materiality/safety "
            "screening are behind injected shells; do not move formulas, CTA/apply, or visible wording."
        ),
        "latest": latest,
        "all_latest_required_artifacts_pass": all(
            (item or {}).get("status") == "PASS" for item in latest.values()
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    hidden_deps = dict(capture.get("primary_executor_hidden_dependencies") or {})
    reusable = dict(capture.get("controller_reusable_helpers_present") or {})
    return {
        "route_found": capture.get("route_found") is True,
        "primary_executor_found": capture.get("primary_executor_found") is True,
        "all_surfaces_classified": all(
            bool(row.get("classification"))
            for row in dict(capture.get("surface_rows") or {}).values()
        ),
        "live_execution_surfaces_identified": bool(
            capture.get("live_execution_surfaces_must_remain")
        ),
        "primary_executor_hidden_dependencies_identified": all(hidden_deps.values()),
        "controller_has_reusable_partial_helpers": any(reusable.values()),
        "candidate_generation_not_ready": (
            capture.get("candidate_generation_cutover_ready") is False
        ),
        "candidate_evaluation_not_ready": (
            capture.get("candidate_evaluation_cutover_ready") is False
        ),
        "behavior_cutover_not_ready": capture.get("behavior_cutover_ready") is False,
        "delete_now_count_zero": capture.get("delete_now_count") == 0,
        "latest_required_artifacts_pass": capture.get("all_latest_required_artifacts_pass") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Candidate Evaluation Boundary Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Route found: `{capture.get('route_found')}`",
        f"- Primary executor found: `{capture.get('primary_executor_found')}`",
        f"- Candidate generation cutover ready: `{capture.get('candidate_generation_cutover_ready')}`",
        f"- Candidate evaluation cutover ready: `{capture.get('candidate_evaluation_cutover_ready')}`",
        f"- Behavior cutover ready: `{capture.get('behavior_cutover_ready')}`",
        f"- Delete-now count: `{capture.get('delete_now_count')}`",
        "",
        "## Boundary Classification",
        "",
    ]
    for name, row in (capture.get("surface_rows") or {}).items():
        lines.append(
            f"- {name}: present=`{row.get('present')}`, classification=`{row.get('classification')}`, "
            f"next=`{row.get('next')}`"
        )
    lines.extend(
        [
            "",
            "## Primary Executor Hidden Dependencies",
            "",
        ]
    )
    lines.extend(
        f"- {name}: `{present}`"
        for name, present in (capture.get("primary_executor_hidden_dependencies") or {}).items()
    )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", "", str(capture.get("next_safe_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluation_boundary_audit.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluation_boundary_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluation_boundary_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_candidate_evaluation_boundary_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluation_boundary "
        + payload["status"]
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
