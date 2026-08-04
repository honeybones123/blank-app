from __future__ import annotations

import json
import sys
import time
import argparse
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from tools.verification.source_fingerprint import (  # noqa: E402
    CORRECTNESS_FINGERPRINT_FILES,
    compare_report_correctness_fingerprint,
    compute_source_fingerprint,
)


CURRENT_CODE_REQUIRED_DEFAULT = True


def _newest_current_source_mtime() -> float:
    mtimes: list[float] = []
    for rel_path in CORRECTNESS_FINGERPRINT_FILES:
        path = ROOT / rel_path
        if path.exists():
            mtimes.append(path.stat().st_mtime)
    return max(mtimes) if mtimes else 0.0


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
            "family_classification_lock_verifier",
            "locked_family_live_wiring_snapshot",
        ],
        "live_required": False,
        "status_rule": "lock_if_all_focused_pass",
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
            "bottom_reo_ranking_policy_input",
            "bottom_reo_ranking_sort",
            "bottom_reo_selected_recommendation_parity_snapshot",
        ],
        "live_required": False,
        "status_rule": "lock_if_all_focused_pass",
    },
    {
        "component": "target-band/exact-stop/blocker proof",
        "owner": "family runtimes + design_brain evidence/proof helpers",
        "consumers": ["publication assembly", "blocked/final cards"],
        "focused_verifiers": [
            "design_brain_family_contract_compliance_target_band_reached",
            "design_brain_family_contract_compliance_exact_stop_proven",
            "target_band_candidate_lane_coverage",
            "bottom_reo_recommendation_readiness_snapshot",
        ],
        "live_required": False,
        "status_rule": "lock_if_all_focused_pass",
    },
    {
        "component": "publication assembly",
        "owner": "design_brain.final_publication + design_brain.publication",
        "consumers": ["render bridge", "CTA binding", "debug/evidence surfaces"],
        "focused_verifiers": [
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
            "design_brain_shared_controller_input_snapshot_lock",
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
            "cta_button_contract_check",
            "design_guide_cta_authority_readiness",
            "design_guide_cta_adapter_parity",
            "design_guide_live_cta_wiring",
            "design_guide_live_cta_authority_cutover",
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
            "app_stability_inputs_apply_10x_workflow_lock",
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
            "design_brain_publication_hash_cache_behavior_snapshot",
            "design_guide_browser_live_visual_consistency",
            "app_stability_inputs_apply_10x_workflow_lock",
        ],
        "live_required": True,
        "status_rule": "lock_if_all_focused_pass",
    },
    {
        "component": "evidence/debug surfaces",
        "owner": "design_brain proof objects + non-authoritative debug storage",
        "consumers": ["verifiers", "browser debug probes"],
        "focused_verifiers": [
            "design_guide_browser_live_visual_consistency",
            "design_brain_shared_compatibility_bridge_fallback_lock",
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


def _latest_artifact(
    prefix: str,
    *,
    require_current_code: bool,
    newest_current_source_mtime: float,
) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {
            "prefix": prefix,
            "found": False,
            "status": "MISSING",
            "artifact_status": "MISSING",
            "path": None,
            "current_code_status": "MISSING",
        }
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "prefix": prefix,
            "found": True,
            "status": "UNREADABLE",
            "artifact_status": "UNREADABLE",
            "path": str(path),
            "error": str(exc),
            "current_code_status": "UNREADABLE",
        }
    artifact_status = _status_from_payload(payload)
    fingerprint_comparison = compare_report_correctness_fingerprint(payload, repo=ROOT)
    invalidation_reason = str(fingerprint_comparison.get("invalidation_reason") or "")
    artifact_mtime = path.stat().st_mtime
    current_code_matches = bool(fingerprint_comparison.get("matches"))
    current_by_mtime_fallback = (
        invalidation_reason == "report_missing_correctness_fingerprint"
        and artifact_mtime >= newest_current_source_mtime
    )
    current_code_accepted = current_code_matches or current_by_mtime_fallback
    if current_code_matches:
        current_code_status = "CURRENT_FINGERPRINT"
    elif current_by_mtime_fallback:
        current_code_status = "CURRENT_MTIME_FALLBACK"
    else:
        current_code_status = (
            invalidation_reason.upper() if invalidation_reason else "CURRENT_CODE_UNKNOWN"
        )
    effective_status = artifact_status
    if require_current_code and artifact_status == "PASS" and not current_code_accepted:
        effective_status = "STALE"
    return {
        "prefix": prefix,
        "found": True,
        "status": effective_status,
        "artifact_status": artifact_status,
        "path": str(path),
        "mtime": artifact_mtime,
        "current_code_status": current_code_status,
        "current_code_matches": current_code_matches,
        "current_code_accepted": current_code_accepted,
        "fingerprint_comparison": {
            "matches": current_code_matches,
            "invalidation_reason": fingerprint_comparison.get("invalidation_reason"),
            "full_gate_required": fingerprint_comparison.get("full_gate_required"),
            "report_correctness_fingerprint": (
                fingerprint_comparison.get("report_correctness_fingerprint") or {}
            ).get("fingerprint"),
            "current_correctness_fingerprint": (
                fingerprint_comparison.get("current_correctness_fingerprint") or {}
            ).get("fingerprint"),
        },
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
    if rule == "performance_deferred_after_correctness":
        return (
            "PERFORMANCE_DEFERRED",
            "publication hash primitives are covered by publication assembly; cache/reuse bypass gates are deferred until correctness certification is complete",
        )
    return "PENDING_AUDIT", f"unknown status rule: {rule}"


def _build_matrix(*, require_current_code: bool) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    newest_current_source_mtime = _newest_current_source_mtime()
    for component in SHARED_COMPONENTS:
        artifact_rows = [
            _latest_artifact(
                prefix,
                require_current_code=require_current_code,
                newest_current_source_mtime=newest_current_source_mtime,
            )
            for prefix in component["focused_verifiers"]
        ]
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
        "performance_deferred_count": sum(1 for row in rows if row["status"] == "PERFORMANCE_DEFERRED"),
        "pending_audit_count": sum(1 for row in rows if row["status"] == "PENDING_AUDIT"),
    }
    result = (
        "PASS"
        if summary["component_count"]
        == summary["locked_count"] + summary["performance_deferred_count"]
        and summary["deferred_with_blocker_count"] == 0
        and summary["pending_audit_count"] == 0
        else "PARTIAL"
    )
    return {
        "schema": "design_brain_shared_component_lock_matrix.v1",
        "result": result,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "current_code_required": require_current_code,
        "current_code_freshness_rule": (
            "PASS artifacts must either carry a matching correctness fingerprint "
            "or be newer than the current correctness source-file mtimes."
        ),
        "newest_current_source_mtime": newest_current_source_mtime,
        "current_source_fingerprint": compute_source_fingerprint(repo=ROOT),
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
        f"- Performance deferred: `{snapshot['summary']['performance_deferred_count']}`",
        f"- Deferred with blocker: `{snapshot['summary']['deferred_with_blocker_count']}`",
        f"- Pending audit: `{snapshot['summary']['pending_audit_count']}`",
        f"- Current-code artifacts required: `{snapshot.get('current_code_required')}`",
        "",
        "## Matrix",
        "",
        "| Component | Owner | Consumers | Status | Blocker | Verifier | Live Proof | Artifacts | Current Code |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in snapshot["components"]:
        consumers = "<br>".join(row["consumers"])
        verifiers = "<br>".join(row["focused_verifiers"]) or "-"
        artifacts = "<br>".join(
            (
                f"{artifact['prefix']}: {artifact['status']}"
                if artifact.get("status") == artifact.get("artifact_status")
                else f"{artifact['prefix']}: {artifact['status']} "
                f"(artifact {artifact.get('artifact_status')})"
            )
            for artifact in row["artifacts"]
        ) or "-"
        current_code = "<br>".join(
            f"{artifact['prefix']}: {artifact.get('current_code_status')}"
            for artifact in row["artifacts"]
        ) or "-"
        lines.append(
            "| {component} | {owner} | {consumers} | `{status}` | {blocker} | {verifiers} | {live} | {artifacts} | {current_code} |".format(
                component=row["component"],
                owner=row["owner"],
                consumers=consumers,
                status=row["status"],
                blocker=row["blocker"] or "-",
                verifiers=verifiers,
                live=row["live_proof"],
                artifacts=artifacts,
                current_code=current_code,
            )
        )
    lines.extend(
        [
            "",
            "## Next Lock Target",
            "",
            "Start with the first `PENDING_AUDIT` component in the matrix. If a row is `DEFERRED_WITH_BLOCKER`, resolve its exact blocker before marking it locked. `PERFORMANCE_DEFERRED` rows are intentionally outside correctness certification and must not be used to claim runtime speed work is complete.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-stale-artifacts",
        action="store_true",
        help="Use historical matrix behavior: PASS artifacts can lock rows even without a current-code fingerprint match.",
    )
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_matrix(require_current_code=not bool(args.allow_stale_artifacts))
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
