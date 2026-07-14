from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


SHARED_COMPONENTS: tuple[dict[str, Any], ...] = (
    {
        "component": "family registry/contracts",
        "owner": "design_brain.families.registry + family contract manifests",
        "consumers": [
            "family_strategy_for(...)",
            "locked family live wiring",
            "family runtime lock gates",
        ],
        "focused_verifiers": [
            "family_lock_contract_v2_inventory",
            "locked_family_live_wiring_snapshot",
        ],
        "live_required": False,
        "status_rule": "defer_if_v2_inventory_not_pass",
    },
    {
        "component": "family chooser/classification",
        "owner": "design_brain.family_chooser + design_brain.family_classification_runtime",
        "consumers": [
            "DesignGuideController",
            "family runtime dispatch",
            "FinalDesignGuidePublication family identity inputs",
        ],
        "focused_verifiers": [
            "family_classification_contract_check",
            "family_chooser_classification_regression",
            "family_classification_lock_verifier",
            "locked_family_live_wiring_snapshot",
        ],
        "live_required": True,
        "status_rule": "lock_if_all_focused_pass",
    },
    {
        "component": "controller input snapshot",
        "owner": "design_brain.design_guide_controller",
        "consumers": ["Design Guide controller orchestration", "publication assembly"],
        "focused_verifiers": ["design_brain_shared_controller_input_snapshot_lock"],
        "live_required": False,
        "status_rule": "lock_if_all_focused_pass",
    },
    {
        "component": "candidate evaluation",
        "owner": "design_brain.candidate_evaluation",
        "consumers": ["family candidate search", "target-band cleanup", "active-fail repair"],
        "focused_verifiers": ["candidate_evaluation_boundary", "design_brain_shared_candidate_evaluation_lock"],
        "live_required": False,
        "status_rule": "lock_if_all_focused_pass",
    },
    {
        "component": "filtering",
        "owner": "family runtimes + shared safety filters",
        "consumers": ["candidate evaluation", "family ranking"],
        "focused_verifiers": [
            "design_brain_shared_filtering_lock",
            "design_guide_auto_design_row_layout_filter_service_extraction",
            "design_guide_direct_target_ladder_filter_extraction",
            "design_guide_active_fail_executor_safe_candidate_filter_adapter",
            "design_guide_bottom_reo_recommendation_filter_policy_extraction",
            "bottom_reo_evaluated_candidate_filter_boundary",
        ],
        "live_required": False,
        "status_rule": "lock_if_all_focused_pass",
    },
    {
        "component": "ranking",
        "owner": "family runtimes + shared ranking helpers",
        "consumers": ["recommendation selection", "target-band cleanup"],
        "focused_verifiers": [
            "design_brain_shared_ranking_lock",
            "bottom_reo_ranking_input_boundary",
            "bottom_reo_ranking_score_source",
            "bottom_reo_ranking_policy_input",
            "bottom_reo_ranking_sort",
            "bending_bottom_reo_recommendation_lock",
            "design_guide_bending_only_target_band_ranking_selector_extraction",
            "design_guide_probe_equivalent_bending_ranking_selector_extraction",
            "design_guide_zero_bending_demand_ranking_selector_extraction",
        ],
        "live_required": False,
        "status_rule": "lock_if_all_focused_pass",
    },
    {
        "component": "target-band/exact-stop/blocker proof",
        "owner": "family runtimes + design_brain evidence/proof helpers",
        "consumers": ["publication assembly", "blocked/final cards"],
        "focused_verifiers": [
            "design_brain_shared_target_band_exact_stop_blocker_proof_lock",
            "design_brain_family_contract_compliance_target_band_reached",
            "design_brain_family_contract_compliance_exact_stop_proven",
            "target_band_candidate_lane_coverage",
            "target_band_candidate_lane_detailed_audit",
        ],
        "live_required": False,
        "status_rule": "lock_if_all_focused_pass",
    },
    {
        "component": "publication assembly",
        "owner": "design_brain.final_publication + design_brain.publication",
        "consumers": ["render bridge", "CTA binding", "debug/evidence surfaces"],
        "focused_verifiers": [
            "design_brain_shared_publication_assembly_lock",
            "design_guide_final_publication_object",
            "design_guide_final_publication_boundary",
            "design_guide_independence_lock",
            "design_brain_shared_final_publication_cta_source_precedence_lock",
        ],
        "live_required": True,
        "status_rule": "lock_if_all_focused_pass",
    },
    {
        "component": "controller orchestration",
        "owner": "design_brain.design_guide_controller",
        "consumers": ["inputs_page shell", "publication assembly"],
        "focused_verifiers": [
            "design_brain_shared_controller_orchestration_lock",
            "design_brain_shared_controller_input_snapshot_lock",
            "design_guide_controller_trace_only_parity",
            "design_guide_controller_publication_authority_cutover",
            "design_guide_controller_compute_handoff_object",
            "design_guide_controller_compute_selector_object",
        ],
        "live_required": False,
        "status_rule": "lock_if_all_focused_pass",
    },
    {
        "component": "CTA binding",
        "owner": "design_brain.publication + FinalDesignGuidePublication.cta",
        "consumers": ["Apply payload", "render-only CTA"],
        "focused_verifiers": [
            "design_brain_shared_cta_binding_lock",
            "cta_button_contract_check",
            "design_guide_cta_authority_readiness",
            "design_guide_cta_adapter_parity",
            "design_guide_live_cta_wiring",
            "design_guide_live_cta_authority_cutover",
            "design_guide_button_contract_shell_deadness",
            "design_brain_shared_final_publication_cta_source_precedence_lock",
            "design_guide_independence_lock",
        ],
        "live_required": True,
        "status_rule": "lock_if_all_focused_pass",
    },
    {
        "component": "Apply payload",
        "owner": "shared apply payload contracts + page apply routing",
        "consumers": ["post-Apply readiness", "Design Guide CTA"],
        "focused_verifiers": [
            "design_brain_shared_apply_payload_lock",
            "design_guide_apply_current_state_safety",
            "design_guide_primary_apply_payload_projection_adapter",
            "design_guide_primary_apply_payload_projection_cutover",
            "design_guide_primary_button_apply_session_shell_boundary",
            "design_guide_cta_apply_binding_bypass_readiness",
            "design_guide_cta_apply_binding_bypass_implementation",
            "design_guide_cta_apply_binding_bypass_live_impact",
        ],
        "live_required": True,
        "status_rule": "lock_if_all_focused_pass",
    },
    {
        "component": "post-Apply readiness",
        "owner": "controller/publication readiness gates",
        "consumers": ["browser/live settled card", "rerun state"],
        "focused_verifiers": [
            "design_brain_shared_post_apply_readiness_lock",
            "design_brain_shared_apply_payload_lock",
            "design_guide_apply_current_state_safety",
            "family_architecture_end_to_end_audit",
        ],
        "live_required": True,
        "status_rule": "lock_if_all_focused_pass",
    },
    {
        "component": "renderer/view models",
        "owner": "render bridge + UI render-only layer",
        "consumers": ["visible Design Guide card", "browser/live visual checks"],
        "focused_verifiers": [
            "design_brain_shared_renderer_view_model_lock",
            "design_guide_render_bridge_lock",
            "design_guide_browser_live_visual_consistency",
            "design_guide_family_browser_live_visual_consistency",
        ],
        "live_required": True,
        "status_rule": "lock_if_all_focused_pass",
    },
    {
        "component": "publication hashes/cache reuse",
        "owner": "FinalDesignGuidePublication hashes + guarded reuse helpers",
        "consumers": ["smooth stable reruns", "render model reuse"],
        "focused_verifiers": [
            "design_brain_shared_publication_hash_cache_reuse_lock",
            "design_guide_cta_apply_binding_bypass_live_impact",
            "design_guide_duplicate_publication_stamp_bypass_live_impact",
            "design_guide_card_render_model_bypass_live_impact",
            "design_guide_stable_publication_summary_render_reuse_implementation",
        ],
        "live_required": True,
        "status_rule": "lock_if_all_focused_pass",
    },
    {
        "component": "evidence/debug surfaces",
        "owner": "design_brain proof objects + non-authoritative debug storage",
        "consumers": ["verifiers", "browser debug probes"],
        "focused_verifiers": [
            "design_brain_shared_evidence_debug_surface_lock",
            "design_brain_inputs_page_zero_authority_inventory_lock",
            "design_guide_verifier_debug_same_object",
            "design_guide_compute_invalid_state_debug_payload_extraction",
            "design_guide_compatibility_debug_projection_extraction",
            "design_brain_compute_rebound_debug_compatibility_payload_deletion",
        ],
        "live_required": False,
        "status_rule": "lock_if_all_focused_pass",
    },
    {
        "component": "compatibility bridges/fallbacks",
        "owner": "bounded non-authoritative shell/adapters",
        "consumers": ["legacy render/debug consumers", "fallback safety"],
        "focused_verifiers": [
            "design_brain_shared_compatibility_bridge_fallback_lock",
            "design_brain_render_fallback_shell_helper_deletion",
            "design_brain_render_fallback_shell_callsite_classification",
            "design_brain_inputs_page_zero_authority_inventory_lock",
        ],
        "live_required": False,
        "status_rule": "lock_if_all_focused_pass",
    },
)


def _status_from_payload(payload: dict[str, Any]) -> str:
    for key in ("status", "result", "lock_status"):
        value = payload.get(key)
        if isinstance(value, str):
            upper = value.upper()
            if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
                return "PASS"
            if "PARTIAL" in upper:
                return "PARTIAL"
            if "FAIL" in upper or "BLOCKED" in upper:
                return "FAIL"
            return upper
    if payload.get("passed") is True:
        return "PASS"
    if payload.get("passed") is False:
        return "FAIL"
    return "UNKNOWN"


def _latest_artifact(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {
            "prefix": prefix,
            "found": False,
            "status": "MISSING",
            "path": None,
        }
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "prefix": prefix,
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": str(exc),
        }
    return {
        "prefix": prefix,
        "found": True,
        "status": _status_from_payload(payload),
        "path": str(path),
    }


def _component_status(component: dict[str, Any], artifacts: list[dict[str, Any]]) -> tuple[str, str]:
    rule = component["status_rule"]
    by_prefix = {row["prefix"]: row for row in artifacts}
    if rule == "pending_audit":
        return "PENDING_AUDIT", "component has not yet had a shared-lock ownership audit in this matrix"
    if rule == "defer_if_v2_inventory_not_pass":
        inventory = by_prefix.get("family_lock_contract_v2_inventory", {})
        wiring = by_prefix.get("locked_family_live_wiring_snapshot", {})
        if inventory.get("status") == "PASS" and wiring.get("status") == "PASS":
            return "LOCKED", "family registry and v2 family contract inventory are green"
        blocker = "family_lock_contract_v2_inventory is not PASS"
        if wiring.get("status") != "PASS":
            blocker += "; locked_family_live_wiring_snapshot is not PASS"
        return "DEFERRED_WITH_BLOCKER", blocker
    if rule == "lock_if_all_focused_pass":
        missing_or_bad = [
            row["prefix"]
            for row in artifacts
            if row.get("status") != "PASS"
        ]
        if not missing_or_bad:
            return "LOCKED", "all focused chooser/classification gates are PASS"
        return "DEFERRED_WITH_BLOCKER", "focused gates not PASS: " + ", ".join(missing_or_bad)
    return "PENDING_AUDIT", f"unknown status rule: {rule}"


def _build_matrix() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for component in SHARED_COMPONENTS:
        artifact_rows = [_latest_artifact(prefix) for prefix in component["focused_verifiers"]]
        status, blocker = _component_status(component, artifact_rows)
        rows.append(
            {
                "component": component["component"],
                "owner": component["owner"],
                "consumers": list(component["consumers"]),
                "status": status,
                "blocker": "" if status == "LOCKED" else blocker,
                "focused_verifiers": list(component["focused_verifiers"]),
                "live_proof_required": bool(component["live_required"]),
                "live_proof": (
                    "REQUIRED_AND_PRESENT"
                    if component["live_required"] and any(row.get("status") == "PASS" for row in artifact_rows)
                    else ("REQUIRED_PENDING" if component["live_required"] else "NOT_REQUIRED_FOR_MATRIX_ROW")
                ),
                "artifacts": artifact_rows,
            }
        )
    summary = {
        "component_count": len(rows),
        "locked_count": sum(1 for row in rows if row["status"] == "LOCKED"),
        "deferred_with_blocker_count": sum(1 for row in rows if row["status"] == "DEFERRED_WITH_BLOCKER"),
        "pending_audit_count": sum(1 for row in rows if row["status"] == "PENDING_AUDIT"),
    }
    result = "PASS" if summary["component_count"] == summary["locked_count"] else "PARTIAL"
    return {
        "schema": "design_brain_shared_component_lock_matrix.v1",
        "result": result,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": summary,
        "components": rows,
    }


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Design Brain Shared Component Lock Matrix",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "## Summary",
        "",
        f"- Components: `{snapshot['summary']['component_count']}`",
        f"- Locked: `{snapshot['summary']['locked_count']}`",
        f"- Deferred with blocker: `{snapshot['summary']['deferred_with_blocker_count']}`",
        f"- Pending audit: `{snapshot['summary']['pending_audit_count']}`",
        "",
        "## Matrix",
        "",
        "| Component | Owner | Consumers | Status | Blocker | Verifier | Live Proof | Artifacts |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in snapshot["components"]:
        consumers = "<br>".join(row["consumers"])
        verifiers = "<br>".join(row["focused_verifiers"]) or "-"
        artifacts = "<br>".join(
            f"{artifact['prefix']}: {artifact['status']}"
            for artifact in row["artifacts"]
        ) or "-"
        lines.append(
            "| {component} | {owner} | {consumers} | `{status}` | {blocker} | {verifiers} | {live} | {artifacts} |".format(
                component=row["component"],
                owner=row["owner"],
                consumers=consumers,
                status=row["status"],
                blocker=row["blocker"] or "-",
                verifiers=verifiers,
                live=row["live_proof"],
                artifacts=artifacts,
            )
        )
    lines.extend(
        [
            "",
            "## Next Lock Target",
            "",
            "Start with the first `PENDING_AUDIT` component in the matrix. If a row is `DEFERRED_WITH_BLOCKER`, resolve its exact blocker before marking it locked.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_matrix()
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_brain_shared_component_lock_matrix_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_component_lock_matrix_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"{snapshot['result']}: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
