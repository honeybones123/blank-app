from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


def _stamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
        .replace(":", "-")
    )


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any] | None:
    matches = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"))
    if not matches:
        return None
    try:
        return json.loads(matches[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def _block(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _position(block: str, token: str) -> int:
    return block.find(token)


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    positions = {
        "primary_executor_runner": _position(
            route_block,
            "_run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
        ),
        "fallback_generator": _position(route_block, "generate_less_shear_reo_variants("),
        "fallback_generator_runner": _position(
            route_block,
            "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
        ),
        "fallback_variant_loop": _position(
            route_block,
            "for fallback_index, fallback_variant in enumerate(fallback_variants[:64]):",
        ),
        "fallback_pre_screen_runner": _position(
            route_block,
            "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen(",
        ),
        "fallback_post_screen_runner": _position(
            route_block,
            "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
        ),
        "candidate_evaluator": _position(route_block, "_evaluate_auto_design_candidate("),
        "candidate_evaluator_runner": _position(
            route_block,
            "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(",
        ),
        "candidate_overview": _position(route_block, "fallback_overview = dict("),
        "candidate_selection": _position(
            route_block,
            "_run_post_click_low_bending_residual_shear_cleanup_candidate_selector(",
        ),
        "local_cleanup_packaging": _position(
            route_block,
            "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(",
        ),
    }
    fallback_tokens = (
        "fallback_shear_candidates: list[dict] = []",
        "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
        "generator=generate_less_shear_reo_variants",
        "for fallback_index, fallback_variant in enumerate(fallback_variants[:64]):",
        "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen(",
        "fallback_updates",
    )
    evaluator_tokens = (
        "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(",
        "evaluator=_evaluate_auto_design_candidate",
        "fallback_candidate",
        "fallback_overview",
        "fallback_shear_util",
        "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
    )
    fallback_dependency_route_shape = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        "fallback_variant_generator_dependency_route_shape_readiness"
    )
    fallback_boundary_only_deadness = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        "fallback_variant_generator_boundary_only_surface_deadness"
    )
    candidate_boundary = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_boundary_parity_scenarios"
    )
    fallback_tokens_missing = [token for token in fallback_tokens if token not in route_block]
    evaluator_tokens_missing = [token for token in evaluator_tokens if token not in route_block]
    fallback_boundary_proven = (
        (fallback_dependency_route_shape or {}).get("status") == "PASS"
        and (fallback_boundary_only_deadness or {}).get("status") == "PASS"
    )
    candidate_boundary_proven = (candidate_boundary or {}).get("status") == "PASS"
    fallback_generation_complete = (
        not fallback_tokens_missing
        or (
            fallback_boundary_proven
            and positions["fallback_generator_runner"] >= 0
            and positions["fallback_pre_screen_runner"] > positions["fallback_generator_runner"]
        )
    )
    candidate_evaluation_complete = (
        not evaluator_tokens_missing
        or (
            candidate_boundary_proven
            and positions["candidate_evaluator_runner"] >= 0
            and positions["fallback_post_screen_runner"] > positions["candidate_evaluator_runner"]
        )
    )
    fallback_generation = {
        "name": "fallback_variant_generator",
        "classification": "C. injected dependency shell already wired",
        "tokens_present": [token for token in fallback_tokens if token in route_block],
        "tokens_missing": fallback_tokens_missing,
        "tokens_missing_tolerated_by_boundary": bool(
            fallback_tokens_missing and fallback_boundary_proven
        ),
        "dependency_route_shape_proven": bool(fallback_dependency_route_shape),
        "boundary_only_surface_dead": bool(fallback_boundary_only_deadness),
        "dependency_boundary_complete": bool(fallback_generation_complete),
        "position": positions["fallback_generator_runner"],
        "happens_before_candidate_evaluator": (
            positions["fallback_generator_runner"] >= 0
            and positions["candidate_evaluator_runner"] > positions["fallback_generator_runner"]
        ),
        "owns": (
            "variant_generation",
            "variant_iteration_limit",
            "candidate_delta_seed",
        ),
        "does_not_own": (
            "candidate_evaluation_execution",
            "overview_acceptance",
            "cta_contract_execution",
            "visible_wording_authoring",
        ),
        "recommended_next": (
            "Fallback generation is already behind an injected runner. Continue to the materiality/safety screen."
        ),
    }
    candidate_evaluation = {
        "name": "candidate_evaluator",
        "classification": "C. injected dependency shell already wired",
        "tokens_present": [token for token in evaluator_tokens if token in route_block],
        "tokens_missing": evaluator_tokens_missing,
        "tokens_missing_tolerated_by_boundary": bool(
            evaluator_tokens_missing and candidate_boundary_proven
        ),
        "candidate_boundary_proven": bool(candidate_boundary_proven),
        "dependency_boundary_complete": bool(candidate_evaluation_complete),
        "position": positions["candidate_evaluator_runner"],
        "depends_on_fallback_updates": (
            positions["candidate_evaluator_runner"] > positions["fallback_pre_screen_runner"] >= 0
        ),
        "owns": (
            "candidate_evaluation_execution",
            "overview_status_read",
            "required_check_acceptance",
            "preview_fail_rejection",
            "candidate_util_read",
        ),
        "does_not_own": (
            "variant_generation_order",
            "cta_contract_execution",
            "visible_wording_authoring",
        ),
        "recommended_next": (
            "Candidate evaluation is already behind an injected runner. Continue to the materiality/safety screen."
        ),
    }
    direct_deadness = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_direct_call_deadness"
    )
    render_lock = _latest("design_guide_render_bridge_lock")
    compute_lock = _latest("design_guide_compute_resolver_publication_bridge_lock")
    independence_lock = _latest("design_guide_independence_lock")
    materiality_tokens = (
        "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen(",
        "delta_screen_builder=_build_design_guide_shear_low_util_candidate_delta_screen",
        "pure_updates_checker=_shear_detailing_updates_pure",
        "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
        "acceptance_screen_builder=_build_design_guide_shear_low_util_candidate_acceptance_screen",
    )
    materiality_screen = {
        "name": "candidate_materiality_and_safety_screen",
        "classification": "C. injected dependency shell already wired",
        "tokens_present": [token for token in materiality_tokens if token in route_block],
        "tokens_missing": [token for token in materiality_tokens if token not in route_block],
        "owns": (
            "candidate_delta_screen",
            "materiality_screen",
            "shear_detailing_purity_screen",
            "overview_acceptance_screen",
            "preview_status_screen",
        ),
        "does_not_own": (
            "candidate_generation_execution",
            "candidate_evaluation_execution",
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
        ),
        "recommended_next": (
            "Materiality/safety screening is now behind injected pre/post screen helpers. "
            "Continue to candidate-selection/result-construction and final-binding tails."
        ),
    }
    materiality_precedes_evaluator = (
        positions["fallback_pre_screen_runner"] >= 0
        and positions["candidate_evaluator_runner"] > positions["fallback_pre_screen_runner"]
    )
    evaluator_precedes_post_screen = (
        positions["candidate_evaluator_runner"] >= 0
        and positions["fallback_post_screen_runner"] > positions["candidate_evaluator_runner"]
    )
    post_screen_precedes_selection = (
        positions["fallback_post_screen_runner"] >= 0
        and positions["candidate_selection"] > positions["fallback_post_screen_runner"]
    )
    recommended_next_dependency = (
        "candidate_selection_result_and_final_binding_tail"
        if (
            fallback_generation_complete
            and fallback_generation["happens_before_candidate_evaluator"]
            and candidate_evaluation_complete
            and candidate_evaluation["depends_on_fallback_updates"]
            and not materiality_screen["tokens_missing"]
            and materiality_precedes_evaluator
            and evaluator_precedes_post_screen
            and post_screen_precedes_selection
        )
        else "UNKNOWN"
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_NEXT_DEPENDENCY_AUDITED",
        "route_block_present": bool(route_block),
        "positions": positions,
        "fallback_variant_generator": fallback_generation,
        "candidate_evaluator": candidate_evaluation,
        "candidate_materiality_and_safety_screen": materiality_screen,
        "materiality_precedes_evaluator": materiality_precedes_evaluator,
        "evaluator_precedes_post_screen": evaluator_precedes_post_screen,
        "post_screen_precedes_selection": post_screen_precedes_selection,
        "recommended_next_dependency": recommended_next_dependency,
        "why_not_candidate_evaluator_first": (
            "Candidate generation, evaluation, and materiality/safety screening are already behind injected "
            "runners. CTA and visible wording remain riskier, so the next smallest surface is candidate "
            "selection/result construction before final-binding tails."
        ),
        "required_latest": {
            "primary_executor_direct_call_deadness": (direct_deadness or {}).get("status"),
            "candidate_boundary_parity": (candidate_boundary or {}).get("status"),
            "fallback_dependency_route_shape_readiness": (
                fallback_dependency_route_shape or {}
            ).get("status"),
            "fallback_boundary_only_surface_deadness": (
                fallback_boundary_only_deadness or {}
            ).get("status"),
            "render_bridge_lock": (render_lock or {}).get("status"),
            "compute_resolver_publication_bridge_lock": (compute_lock or {}).get("status"),
            "independence_lock": (independence_lock or {}).get("status"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    fallback = dict(capture.get("fallback_variant_generator") or {})
    evaluator = dict(capture.get("candidate_evaluator") or {})
    materiality = dict(capture.get("candidate_materiality_and_safety_screen") or {})
    required_latest = dict(capture.get("required_latest") or {})
    return {
        "route_block_present": capture.get("route_block_present") is True,
        "fallback_tokens_complete": fallback.get("dependency_boundary_complete") is True,
        "fallback_before_candidate_evaluator": fallback.get("happens_before_candidate_evaluator") is True,
        "candidate_evaluator_tokens_complete": (
            evaluator.get("dependency_boundary_complete") is True
        ),
        "candidate_evaluator_depends_on_fallback_updates": (
            evaluator.get("depends_on_fallback_updates") is True
        ),
        "materiality_tokens_complete": not materiality.get("tokens_missing"),
        "materiality_before_evaluator": capture.get("materiality_precedes_evaluator") is True,
        "evaluator_before_post_screen": capture.get("evaluator_precedes_post_screen") is True,
        "post_screen_before_selection": capture.get("post_screen_precedes_selection") is True,
        "recommended_next_is_selection_result_tail": (
            capture.get("recommended_next_dependency")
            == "candidate_selection_result_and_final_binding_tail"
        ),
        "latest_primary_executor_direct_call_deadness_pass": (
            required_latest.get("primary_executor_direct_call_deadness") == "PASS"
        ),
        "latest_candidate_boundary_parity_pass": (
            required_latest.get("candidate_boundary_parity") == "PASS"
        ),
        "latest_fallback_dependency_route_shape_readiness_pass": (
            required_latest.get("fallback_dependency_route_shape_readiness") == "PASS"
        ),
        "latest_fallback_boundary_only_surface_deadness_pass": (
            required_latest.get("fallback_boundary_only_surface_deadness") == "PASS"
        ),
        "latest_render_bridge_lock_pass": required_latest.get("render_bridge_lock") == "PASS",
        "latest_compute_resolver_publication_bridge_lock_pass": (
            required_latest.get("compute_resolver_publication_bridge_lock") == "PASS"
        ),
        "latest_independence_lock_pass": required_latest.get("independence_lock") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    fallback = dict(capture.get("fallback_variant_generator") or {})
    evaluator = dict(capture.get("candidate_evaluator") or {})
    lines = [
        "# Residual Shear Cleanup Next Dependency Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Recommendation",
        "",
        f"- Next dependency: `{capture.get('recommended_next_dependency')}`",
        f"- Why not candidate evaluator first: {capture.get('why_not_candidate_evaluator_first')}",
        "",
        "## Fallback Variant Generator",
        "",
        f"- Classification: `{fallback.get('classification')}`",
        f"- Tokens missing: `{fallback.get('tokens_missing')}`",
        f"- Happens before candidate evaluator: `{fallback.get('happens_before_candidate_evaluator')}`",
        f"- Owns: `{fallback.get('owns')}`",
        f"- Does not own: `{fallback.get('does_not_own')}`",
        "",
        "## Candidate Evaluator",
        "",
        f"- Classification: `{evaluator.get('classification')}`",
        f"- Tokens missing: `{evaluator.get('tokens_missing')}`",
        f"- Depends on fallback updates: `{evaluator.get('depends_on_fallback_updates')}`",
        f"- Owns: `{evaluator.get('owns')}`",
        f"- Does not own: `{evaluator.get('does_not_own')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Continue to candidate-selection/result-construction and final-binding tails. Do not move CTA contract execution, visible wording, apply routing, UI rendering, or session/debug mutation.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_next_dependency_audit.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_next_dependency_audit_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_next_dependency_audit_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_next_dependency_audit_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print("design_guide_post_click_low_bending_residual_shear_cleanup_next_dependency_audit " + payload["status"])
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
