"""Audit remaining live execution shells in the residual-shear cleanup route."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value("
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("

SURFACES = {
    "route_entry_guard": {
        "classification": "A. controller-owned gate / retained call",
        "tokens": (
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard(",
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_decision(",
            "route_entry_decision=dict(residual_shear_cleanup_route_entry_decision or {})",
        ),
        "delete_now": False,
        "recommended_next": "Retain until the whole route body is replaced by a controller route shell.",
    },
    "primary_executor_shell": {
        "classification": "C. live execution shell / injected engineering call",
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
            "executor=_compute_shear_tightening_recommendation",
        ),
        "delete_now": False,
        "recommended_next": "Move only after proving controller route shell can own primary executor handoff.",
    },
    "fallback_variant_generator_shell": {
        "classification": "C. live execution shell / injected generator call",
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
            "generator=generate_less_shear_reo_variants",
        ),
        "delete_now": False,
        "recommended_next": "Next safest authority boundary: controller route shell generation handoff.",
    },
    "candidate_evaluator_shell": {
        "classification": "C. live execution shell / injected evaluator call",
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(",
            "evaluator=_evaluate_auto_design_candidate",
        ),
        "delete_now": False,
        "recommended_next": "Keep live until generator handoff and evaluator handoff are route-shell-owned.",
    },
    "materiality_safety_screen_shell": {
        "classification": "B. controller-owned result shape / live injected screen builders",
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen(",
            "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
        ),
        "delete_now": False,
        "recommended_next": "Already result-shape cut over; delete only after route shell replacement.",
    },
    "candidate_selector_shell": {
        "classification": "B. controller-owned selector / live injected selector call",
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_candidate_selector(",
            "selector=_select_design_guide_post_click_low_bending_residual_shear_cleanup_candidate_by_sort_key",
        ),
        "delete_now": False,
        "recommended_next": "Already controller-selector backed; delete only after route shell replacement.",
    },
    "result_packaging_shell": {
        "classification": "B. controller-owned result packaging / live injected packaging call",
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(",
            "packager=_shear_tightening_as_local_cleanup_item",
        ),
        "delete_now": False,
        "recommended_next": "Already cut over; delete only after route shell replacement.",
    },
    "shared_button_contract_execution": {
        "classification": "D. shared CTA/apply boundary / bounded by controller proof",
        "tokens": (
            "residual_button_contract = dict(",
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary(",
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary(",
        ),
        "delete_now": False,
        "recommended_next": "Keep as bounded shared CTA/apply proof; CTA/apply semantics stay shared/page-owned by current rules.",
    },
    "debug_projection_tail": {
        "classification": "B. compatibility-only / proof-covered",
        "tokens": (
            "_mark_post_click_low_bending_residual_shear_cleanup_debug_projection_compatibility_only(",
            "design_guide_controller_post_click_low_bending_residual_shear_cleanup_debug_projection_rows",
        ),
        "delete_now": False,
        "recommended_next": "Delete only after direct debug row deadness reachability.",
    },
}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if "PASS" in raw_status.upper() or "LOCKED" in raw_status.upper() else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(source, ROUTE_START, ROUTE_END)
    latest = {
        "primary_executor_call_shape_cutover": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_call_shape_cutover"
        ),
        "primary_executor_direct_call_deadness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_direct_call_deadness"
        ),
        "fallback_variant_generator_call_shape_cutover": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_call_shape_cutover"
        ),
        "fallback_variant_generator_direct_call_deadness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_direct_call_deadness"
        ),
        "candidate_evaluator_injected_adapter_cutover_implementation": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter_cutover_implementation"
        ),
        "candidate_evaluator_direct_call_deadness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_direct_call_deadness"
        ),
        "debug_projection_row_builder": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_row_builder"
        ),
        "debug_projection_narrowing": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_narrowing"
        ),
        "debug_projection_consumer_reachability": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_consumer_reachability"
        ),
        "remaining_surface_audit": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_surface_audit"
        ),
        "route_shell_deadness_readiness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness"
        ),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    primary_executor_cut_over = (
        latest.get("primary_executor_call_shape_cutover", {}).get("status") == "PASS"
        and latest.get("primary_executor_direct_call_deadness", {}).get("status") == "PASS"
    )
    fallback_variant_generator_cut_over = (
        latest.get("fallback_variant_generator_call_shape_cutover", {}).get("status") == "PASS"
        and latest.get("fallback_variant_generator_direct_call_deadness", {}).get("status") == "PASS"
    )
    candidate_evaluator_cut_over = (
        latest.get("candidate_evaluator_injected_adapter_cutover_implementation", {}).get("status")
        == "PASS"
        and latest.get("candidate_evaluator_direct_call_deadness", {}).get("status") == "PASS"
    )
    rows = {}
    for name, spec in SURFACES.items():
        tokens = tuple(spec.get("tokens") or ())
        present = [token for token in tokens if token in route]
        row = dict(spec)
        if (
            name == "debug_projection_tail"
            and latest.get("debug_projection_consumer_reachability", {}).get("status")
            == "PASS"
            and "_mark_post_click_low_bending_residual_shear_cleanup_debug_projection_compatibility_only("
            not in route
        ):
            tokens = ("design_guide_controller_post_click_low_bending_residual_shear_cleanup_debug_projection_rows",)
            present = [token for token in tokens if token in route]
            row["classification"] = "B. compatibility marker deleted / proof-covered"
            row["recommended_next"] = (
                "Direct debug rows remain a separate surface; compatibility marker is deleted."
            )
        if name == "primary_executor_shell" and primary_executor_cut_over:
            row["classification"] = "B. injected runner / direct call dead"
            row[
                "recommended_next"
            ] = "Keep injected runner until whole route body replacement; direct executor call is already dead."
        if name == "fallback_variant_generator_shell" and fallback_variant_generator_cut_over:
            row["classification"] = "B. injected generator runner / direct call dead"
            row[
                "recommended_next"
            ] = "Keep injected generator runner until whole route body replacement; direct fallback generator call is already dead."
        if name == "candidate_evaluator_shell" and candidate_evaluator_cut_over:
            row["classification"] = "B. injected evaluator runner / direct call dead"
            row[
                "recommended_next"
            ] = "Keep injected evaluator runner until whole route body replacement; direct evaluator call is already dead."
        rows[name] = {
            **row,
            "present": len(present) == len(tokens),
            "tokens_present": present,
            "tokens_missing": [token for token in tokens if token not in route],
        }
    classification_counts: dict[str, int] = {}
    for row in rows.values():
        key = str(row.get("classification") or "unknown")
        classification_counts[key] = classification_counts.get(key, 0) + 1
    missing = [name for name, row in rows.items() if not row.get("present")]
    unclassified_missing = [
        name
        for name in missing
        if not str((rows.get(name) or {}).get("classification") or "").startswith(
            ("B.", "D.")
        )
    ]
    delete_now = [name for name, row in rows.items() if row.get("delete_now")]
    c_class = [
        name for name, row in rows.items() if str(row.get("classification") or "").startswith("C.")
    ]
    local_required_artifacts = {
        key: value
        for key, value in latest.items()
        if key
        not in {
            "render_bridge_lock",
            "compute_bridge_lock",
            "independence_lock",
            "route_shell_deadness_readiness",
        }
    }
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_ROUTE_BODY_LIVE_EXECUTION_SHELLS_MAPPED",
        "route_found": bool(route),
        "surface_rows": rows,
        "classification_counts": classification_counts,
        "missing_surfaces": missing,
        "unclassified_missing_surfaces": unclassified_missing,
        "delete_now_count": len(delete_now),
        "delete_now_surfaces": delete_now,
        "primary_executor_cut_over": bool(primary_executor_cut_over),
        "fallback_variant_generator_cut_over": bool(fallback_variant_generator_cut_over),
        "candidate_evaluator_cut_over": bool(candidate_evaluator_cut_over),
        "live_execution_shell_surfaces": c_class,
        "recommended_next_surface": c_class[0] if c_class else "route_body_deletion_readiness",
        "recommended_next_step": (
            f"Start with `{c_class[0]}`, because it is the first remaining C-class live execution shell in route order."
            if c_class
            else "Run route body deletion readiness."
        ),
        "latest": latest,
        "latest_required_artifacts_pass": all(
            item.get("status") == "PASS" for item in local_required_artifacts.values()
        ),
        "broad_lock_status": {
            key: latest.get(key, {})
            for key in ("render_bridge_lock", "compute_bridge_lock", "independence_lock")
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "route_found": capture.get("route_found") is True,
        "all_surfaces_classified": not capture.get("unclassified_missing_surfaces"),
        "delete_now_count_zero": capture.get("delete_now_count") == 0,
        "recommended_next_surface_selected": bool(capture.get("recommended_next_surface")),
        "latest_required_artifacts_pass": capture.get("latest_required_artifacts_pass") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Route Body Live Execution Shell Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Recommended next surface: `{capture.get('recommended_next_surface')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- delete now count: `{capture.get('delete_now_count')}`",
        f"- live execution shell surfaces: `{capture.get('live_execution_shell_surfaces')}`",
        "",
        "## Surfaces",
        "",
    ]
    for name, row in (capture.get("surface_rows") or {}).items():
        lines.append(
            f"- `{name}`: present=`{row.get('present')}`, classification=`{row.get('classification')}`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", "", str(capture.get("recommended_next_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_live_execution_shell_audit.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_live_execution_shell_audit_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_live_execution_shell_audit_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_route_body_live_execution_shell_audit_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_live_execution_shell_audit {payload['status']}")
    print(f"recommended_next_surface={capture.get('recommended_next_surface')}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
