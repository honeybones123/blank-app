"""Focused live-shaped parity scenarios for compute publication handoff proof."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

SCENARIO_NAMES = (
    "normal_efficient_pass_design",
    "bending_fail_repair_accepted",
    "shear_fail_repair_accepted",
    "combined_fail_active_failure_repair",
    "overdesign_cleanup",
    "exact_blocker_no_valid_repair",
    "post_click_state_after_apply",
    "stale_payload_rerun_state",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    matches = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not matches:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = matches[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "snapshot": {}, "passed": False, "error": str(exc)}
    return {
        "found": True,
        "path": str(path),
        "snapshot": snapshot,
        "passed": snapshot.get("status") == "PASS",
    }


def _contract(
    *,
    enabled: bool,
    family: str,
    candidate_id: str,
    updates: dict[str, Any] | None = None,
    blocking_reason: str | None = None,
    stale: bool = False,
) -> dict[str, Any]:
    return {
        "enabled": bool(enabled),
        "actionable": bool(enabled),
        "label": "Apply repair" if enabled else "No direct action",
        "action_type": "apply_resolved_candidate" if enabled else None,
        "family": family,
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "updates": dict(updates or {}),
        "blocking_reason": blocking_reason,
        "disabled_reason": blocking_reason,
        "stale_payload": bool(stale),
    }


def _item(
    *,
    scenario: str,
    family_id: str,
    family: str,
    status: str,
    bucket: str,
    candidate_id: str,
    title: str,
    summary: str,
    button_contract: dict[str, Any],
    candidate_search_evidence: dict[str, Any] | None = None,
    blocking_reason: str | None = None,
    post_click_state: str | None = None,
    terminal_state: str | None = None,
    exact_stop_proof: dict[str, Any] | None = None,
    target_band_proof: dict[str, Any] | None = None,
    stale_fresh_proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item = {
        "published_item_id": f"{scenario}:published",
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "selected_family_id": family_id,
        "published_family_id": family_id,
        "family": family,
        "status": status,
        "bucket": bucket,
        "title": title,
        "title_main": title,
        "summary_line": summary,
        "guidance_intent": "required_fix" if status == "ACTION" else "already_efficient",
        "button_contract": dict(button_contract),
        "action_payload": {
            "action_type": button_contract.get("action_type"),
            "family": family,
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "updates": dict(button_contract.get("updates") or {}),
        },
        "candidate_search_evidence": dict(candidate_search_evidence or {}),
        "display_truth": {"target_low": 0.85, "target_high": 1.0, "displayed_util": 0.92},
    }
    if blocking_reason:
        item["blocking_reason"] = blocking_reason
    if post_click_state:
        item["post_click_design_guide_state"] = post_click_state
    if terminal_state:
        item["design_guide_terminal_state"] = terminal_state
    if exact_stop_proof:
        item["exact_stop_proof"] = dict(exact_stop_proof)
    if target_band_proof:
        item["target_band_proof"] = dict(target_band_proof)
    if stale_fresh_proof:
        item["stale_fresh_proof"] = dict(stale_fresh_proof)
    return item


def _scenarios() -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []

    pass_contract = _contract(enabled=False, family="general", candidate_id="pass-current")
    scenarios.append(
        {
            "name": "normal_efficient_pass_design",
            "item": _item(
                scenario="normal_efficient_pass_design",
                family_id="TARGET_BAND_REACHED",
                family="general",
                status="PASS",
                bucket="pass",
                candidate_id="pass-current",
                title="Design accepted",
                summary="Target band reached.",
                button_contract=pass_contract,
                candidate_search_evidence={"target_low": 0.85, "target_high": 1.0, "displayed_util": 0.91},
                terminal_state="optimal",
                exact_stop_proof={"terminal_state": "optimal", "source": "scenario"},
                target_band_proof={"target_low": 0.85, "target_high": 1.0, "displayed_util": 0.91},
            ),
            "render_reason": "target_band_reached",
            "rebound_contract": pass_contract,
            "late_acceptance": {"late_updates_present": False, "accepted": False},
            "post_core_mismatch": {"post_evidence_updates_present": False, "accepted": False},
        }
    )

    bending_contract = _contract(
        enabled=True,
        family="bending",
        candidate_id="bend-repair-1",
        updates={"bot_dia": 20, "bot_no": 4},
    )
    scenarios.append(
        {
            "name": "bending_fail_repair_accepted",
            "item": _item(
                scenario="bending_fail_repair_accepted",
                family_id="BENDING_FAIL_GOVERNS",
                family="bending",
                status="ACTION",
                bucket="fail",
                candidate_id="bend-repair-1",
                title="Bending repair required",
                summary="Increase bottom reinforcement.",
                button_contract=bending_contract,
                candidate_search_evidence={
                    "family": "bending",
                    "selected_candidate_updates": {"bot_dia": 20, "bot_no": 4},
                    "target_band_candidate_count": 1,
                },
            ),
            "render_reason": "bending_fail_repair_accepted",
            "rebound_contract": bending_contract,
            "late_acceptance": {"late_updates_present": True, "accepted": True},
            "post_core_mismatch": {"post_evidence_updates_present": False, "accepted": False},
        }
    )

    shear_contract = _contract(
        enabled=True,
        family="shear",
        candidate_id="shear-repair-1",
        updates={"lig_spacing": 150, "lig_d": "N12"},
    )
    scenarios.append(
        {
            "name": "shear_fail_repair_accepted",
            "item": _item(
                scenario="shear_fail_repair_accepted",
                family_id="SHEAR_FAIL_GOVERNS",
                family="shear",
                status="ACTION",
                bucket="fail",
                candidate_id="shear-repair-1",
                title="Shear repair required",
                summary="Tighten shear reinforcement.",
                button_contract=shear_contract,
                candidate_search_evidence={
                    "family": "shear",
                    "selected_candidate_updates": {"lig_spacing": 150, "lig_d": "N12"},
                    "candidate_search_exhaustive": True,
                },
            ),
            "render_reason": "shear_fail_repair_accepted",
            "rebound_contract": shear_contract,
            "late_acceptance": {"late_updates_present": True, "accepted": True},
            "post_core_mismatch": {"post_evidence_updates_present": True, "accepted": True},
        }
    )

    combined_contract = _contract(
        enabled=True,
        family="combined",
        candidate_id="combined-repair-1",
        updates={"D": 475, "bot_dia": 20, "lig_spacing": 150},
    )
    scenarios.append(
        {
            "name": "combined_fail_active_failure_repair",
            "item": _item(
                scenario="combined_fail_active_failure_repair",
                family_id="BENDING_AND_SHEAR_FAIL_GOVERN",
                family="combined",
                status="ACTION",
                bucket="fail",
                candidate_id="combined-repair-1",
                title="Bending and shear repair required",
                summary="Apply combined strengthening.",
                button_contract=combined_contract,
                candidate_search_evidence={
                    "family": "combined",
                    "selected_candidate_updates": {"D": 475, "bot_dia": 20, "lig_spacing": 150},
                    "coverage": {"bending": True, "shear": True},
                },
            ),
            "render_reason": "combined_fail_active_failure_repair",
            "rebound_contract": combined_contract,
            "late_acceptance": {"late_updates_present": True, "contract_disabled_or_mismatched": True, "accepted": True},
            "post_core_mismatch": {"post_evidence_updates_present": True, "family": "combined", "accepted": True},
        }
    )

    cleanup_contract = _contract(
        enabled=True,
        family="shear",
        candidate_id="cleanup-1",
        updates={"lig_spacing": 250},
    )
    scenarios.append(
        {
            "name": "overdesign_cleanup",
            "item": _item(
                scenario="overdesign_cleanup",
                family_id="SHEAR_OVERDESIGN_GOVERNS",
                family="shear",
                status="ACTION",
                bucket="pass",
                candidate_id="cleanup-1",
                title="Shear reinforcement can be reduced",
                summary="Increase spacing while preserving capacity.",
                button_contract=cleanup_contract,
                candidate_search_evidence={
                    "family": "shear",
                    "selected_candidate_updates": {"lig_spacing": 250},
                    "cleanup_search_ran": True,
                },
            ),
            "render_reason": "overdesign_cleanup",
            "rebound_contract": cleanup_contract,
            "late_acceptance": {"late_updates_present": True, "accepted": True},
            "post_core_mismatch": {"post_evidence_updates_present": True, "accepted": True},
        }
    )

    blocked_contract = _contract(
        enabled=False,
        family="shear",
        candidate_id="blocked-shear",
        blocking_reason="no_valid_shear_repair",
    )
    blocker_evidence = {
        "family": "shear",
        "candidate_search_exhaustive": True,
        "exact_blockers_by_family": {"shear": {"search_ran": True, "search_exhaustive": True}},
    }
    scenarios.append(
        {
            "name": "exact_blocker_no_valid_repair",
            "item": _item(
                scenario="exact_blocker_no_valid_repair",
                family_id="SHEAR_FAIL_GOVERNS",
                family="shear",
                status="BLOCKED",
                bucket="fail",
                candidate_id="blocked-shear",
                title="Shear repair blocked",
                summary="No valid shear repair remains.",
                button_contract=blocked_contract,
                candidate_search_evidence=blocker_evidence,
                blocking_reason="no_valid_shear_repair",
                post_click_state="BLOCKED",
                exact_stop_proof={"exact_blockers_by_family": blocker_evidence["exact_blockers_by_family"]},
            ),
            "render_reason": "exact_blocker_no_valid_repair",
            "rebound_contract": blocked_contract,
            "late_acceptance": {"late_updates_present": False, "accepted": False},
            "post_core_mismatch": {"post_evidence_updates_present": False, "accepted": False},
            "blocker_relevant": True,
        }
    )

    post_click_contract = _contract(
        enabled=True,
        family="bending",
        candidate_id="post-click-bending",
        updates={"bot_no": 5},
    )
    scenarios.append(
        {
            "name": "post_click_state_after_apply",
            "item": _item(
                scenario="post_click_state_after_apply",
                family_id="BENDING_FAIL_GOVERNS",
                family="bending",
                status="ACTION",
                bucket="fail",
                candidate_id="post-click-bending",
                title="Bending repair applied",
                summary="Post-click state reflects the selected repair.",
                button_contract=post_click_contract,
                candidate_search_evidence={"family": "bending", "selected_candidate_updates": {"bot_no": 5}},
                post_click_state="ACTION",
            ),
            "render_reason": "post_click_state_after_apply",
            "rebound_contract": post_click_contract,
            "late_acceptance": {"late_updates_present": True, "accepted": True},
            "post_core_mismatch": {"post_evidence_updates_present": False, "accepted": False},
            "post_click_relevant": True,
        }
    )

    stale_contract = _contract(
        enabled=False,
        family="bending",
        candidate_id="stale-bending",
        updates={"bot_no": 4},
        blocking_reason="stale_payload_rerun_required",
        stale=True,
    )
    scenarios.append(
        {
            "name": "stale_payload_rerun_state",
            "item": _item(
                scenario="stale_payload_rerun_state",
                family_id="BENDING_FAIL_GOVERNS",
                family="bending",
                status="BLOCKED",
                bucket="fail",
                candidate_id="stale-bending",
                title="Recommendation needs refresh",
                summary="The payload is stale after rerun.",
                button_contract=stale_contract,
                candidate_search_evidence={"family": "bending", "selected_candidate_updates": {"bot_no": 4}},
                blocking_reason="stale_payload_rerun_required",
                stale_fresh_proof={"stale": True, "fresh": False, "source": "scenario"},
            ),
            "render_reason": "stale_payload_rerun_state",
            "rebound_contract": stale_contract,
            "late_acceptance": {"late_updates_present": True, "accepted": False},
            "post_core_mismatch": {"post_evidence_updates_present": True, "accepted": False},
            "stale_relevant": True,
        }
    )
    return scenarios


def _proof_inputs(case: dict[str, Any]) -> dict[str, Any]:
    item = dict(case["item"])
    rebound_contract = dict(case["rebound_contract"])
    updates = dict(rebound_contract.get("updates") or {})
    return {
        "raw_selected_item": dict(item),
        "render_reason": case["render_reason"],
        "state_fingerprint": f"{case['name']}:state-fingerprint",
        "late_evidence_acceptance": dict(case.get("late_acceptance") or {}),
        "rebound_contract": rebound_contract,
        "rebound_update_payload": updates,
        "post_core_evidence_mismatch": dict(case.get("post_core_mismatch") or {}),
        "raw_rebound_item": {**item, "button_contract": rebound_contract},
        "pre_resolver_collapsed_item_mutation": {
            "before_identity": {
                "candidate_id": item.get("candidate_id"),
                "source_candidate_id": item.get("source_candidate_id"),
            },
            "after_identity": {
                "candidate_id": rebound_contract.get("candidate_id") or item.get("candidate_id"),
                "source_candidate_id": rebound_contract.get("source_candidate_id") or item.get("source_candidate_id"),
            },
            "mutation_reason": case["render_reason"],
        },
    }


def _scenario_result(case: dict[str, Any]) -> dict[str, Any]:
    from design_brain.final_publication import (
        build_collapsed_guidance_item_from_final_publication,
        build_final_design_guide_compute_publication_handoff_rebound_decision_proof,
        build_final_design_guide_publication,
        stable_final_publication_hash,
    )

    proof_inputs = _proof_inputs(case)
    proof_a = build_final_design_guide_compute_publication_handoff_rebound_decision_proof(**proof_inputs)
    proof_b = build_final_design_guide_compute_publication_handoff_rebound_decision_proof(**proof_inputs)
    item = dict(case["item"])
    debug = {
        "candidate_search_evidence": dict(item.get("candidate_search_evidence") or {}),
        "post_click_design_guide_state": item.get("post_click_design_guide_state"),
        "stale_fresh_proof": dict(item.get("stale_fresh_proof") or {}),
    }
    publication_a = build_final_design_guide_publication(
        item=item,
        debug=debug,
        publication_reason=case["render_reason"],
    )
    publication_b = build_final_design_guide_publication(
        item=item,
        debug=debug,
        publication_reason=case["render_reason"],
    )
    collapsed = build_collapsed_guidance_item_from_final_publication(
        publication_a,
    )
    proof = proof_a.to_dict()
    evidence = publication_a.evidence.to_dict()
    rebound_contract = proof["rebound_contract"]
    rebound_updates = dict(rebound_contract.get("updates") or {})
    expected_updates = dict(case["rebound_contract"].get("updates") or {})
    identity_matches = bool(
        proof["raw_selected_item_identity"].get("published_item_id") == publication_a.published_item_id
        and proof["raw_selected_item_identity"].get("selected_family") == publication_a.selected_family
        and collapsed.get("published_item_id") == publication_a.published_item_id
    )
    blocker_relevant = bool(case.get("blocker_relevant") or item.get("blocking_reason"))
    blocker_matches = True
    if blocker_relevant:
        blocker_matches = bool(
            publication_a.blocker_reason == item.get("blocking_reason")
            and evidence.get("candidate_search_evidence") == item.get("candidate_search_evidence")
            and stable_final_publication_hash(evidence.get("exact_stop_proof") or {})
            == stable_final_publication_hash(item.get("exact_stop_proof") or {})
        )
    rebound_matches = bool(
        bool(rebound_contract.get("enabled")) == bool(case["rebound_contract"].get("enabled"))
        and rebound_updates == expected_updates
        and proof["rebound_update_payload_summary"].get("update_hash")
        == stable_final_publication_hash(expected_updates)
    )
    post_click_no_contradiction = True
    if case.get("post_click_relevant"):
        post_click_no_contradiction = bool(
            publication_a.post_click_design_guide_state == item.get("post_click_design_guide_state")
            and collapsed.get("post_click_design_guide_state") == publication_a.post_click_design_guide_state
        )
    stale_no_contradiction = True
    if case.get("stale_relevant"):
        stale_no_contradiction = bool(
            publication_a.stale_fresh_proof == item.get("stale_fresh_proof")
            and publication_a.blocker_reason == item.get("blocking_reason")
        )
    mismatches: list[str] = []
    if proof_a.decision_hash != proof_b.decision_hash or proof_a.field_hashes != proof_b.field_hashes:
        mismatches.append("proof_hash_unstable")
    if publication_a.publication_hash != publication_b.publication_hash:
        mismatches.append("publication_hash_unstable")
    if not identity_matches:
        mismatches.append("selected_item_identity")
    if not blocker_matches:
        mismatches.append("blocker_evidence")
    if not rebound_matches:
        mismatches.append("rebound_enabled_or_updates")
    if not post_click_no_contradiction:
        mismatches.append("post_click_state_second_publication")
    if not stale_no_contradiction:
        mismatches.append("stale_payload_second_publication")
    if proof.get("missing_blocking_fields"):
        mismatches.append("missing_blocking_fields")
    return {
        "scenario": case["name"],
        "status": "PASS" if not mismatches else "FAIL",
        "mismatches": mismatches,
        "proof_hash": proof_a.decision_hash,
        "publication_hash": publication_a.publication_hash,
        "proof_hash_stable": proof_a.decision_hash == proof_b.decision_hash,
        "publication_hash_stable": publication_a.publication_hash == publication_b.publication_hash,
        "selected_item_identity_matches_final_publication": identity_matches,
        "blocker_evidence_matches_final_publication": blocker_matches,
        "blocker_relevant": blocker_relevant,
        "rebound_enabled_updates_match_live_compute_outcome": rebound_matches,
        "post_click_state_no_second_publication": post_click_no_contradiction,
        "stale_payload_no_second_publication": stale_no_contradiction,
        "covered_blocking_fields": list(proof.get("covered_blocking_fields") or []),
        "missing_blocking_fields": list(proof.get("missing_blocking_fields") or []),
        "field_hashes": dict(proof.get("field_hashes") or {}),
    }


def _forbidden_token_hits() -> dict[str, bool]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    tokens = {
        "import inputs_page": "import inputs_page",
        "from inputs_page": "from inputs_page",
        "import streamlit": "import streamlit",
        "st.session_state": "st.session_state",
        "session_state": "session_state",
        "render_html": "render_html",
        "route_apply": "route_apply",
    }
    return {name: token in source for name, token in tokens.items()}


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Live Compute Publication Handoff/Rebound Parity Scenarios",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Scenario count: `{len(payload['scenarios'])}`",
        f"- All scenarios passed: `{payload['all_scenarios_passed']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        f"- Compute paths narrowed: `{payload['compute_paths_narrowed']}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Status | Proof stable | Identity | Blocker | Rebound | Post-click | Stale | Mismatches |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["scenarios"]:
        lines.append(
            "| {scenario} | `{status}` | `{proof}` | `{identity}` | `{blocker}` | `{rebound}` | `{post}` | `{stale}` | {mismatch} |".format(
                scenario=row["scenario"],
                status=row["status"],
                proof=row["proof_hash_stable"],
                identity=row["selected_item_identity_matches_final_publication"],
                blocker=row["blocker_evidence_matches_final_publication"],
                rebound=row["rebound_enabled_updates_match_live_compute_outcome"],
                post=row["post_click_state_no_second_publication"],
                stale=row["stale_payload_no_second_publication"],
                mismatch=", ".join(row["mismatches"]) or "none",
            )
        )
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    live_bridge = _latest("design_guide_live_compute_publication_handoff_rebound_decision_bridge")
    scenario_results = [_scenario_result(case) for case in _scenarios()]
    names = [row["scenario"] for row in scenario_results]
    forbidden_hits = _forbidden_token_hits()
    failures: list[str] = []
    if names != list(SCENARIO_NAMES):
        failures.append("scenario_coverage_mismatch")
    if not live_bridge.get("passed"):
        failures.append("live_compute_bridge_snapshot_not_passed")
    if any(row["status"] != "PASS" for row in scenario_results):
        failures.append("scenario_parity_mismatch")
    if any(forbidden_hits.values()):
        failures.append("forbidden_design_brain_ownership_token")
    payload = {
        "schema": "design_guide_live_compute_publication_handoff_rebound_parity_scenarios.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "scenarios": scenario_results,
        "all_scenarios_passed": all(row["status"] == "PASS" for row in scenario_results),
        "source_live_bridge_artifact": live_bridge.get("path"),
        "live_bridge_passed": bool(live_bridge.get("passed")),
        "compute_paths_narrowed": False,
        "product_behavior_changed": False,
        "forbidden_design_brain_token_hits": forbidden_hits,
        "snapshot_hash": _stable_hash(
            {
                "scenario_results": [
                    {
                        "scenario": row["scenario"],
                        "proof_hash": row["proof_hash"],
                        "publication_hash": row["publication_hash"],
                        "mismatches": row["mismatches"],
                    }
                    for row in scenario_results
                ],
                "compute_paths_narrowed": False,
                "product_behavior_changed": False,
            }
        ),
        "recommended_next_slice": (
            "If this remains PASS, narrow only compute debug/restamp metadata rows; keep raw compute "
            "selection, rebound guard, and safety logic live until their own authority move is proven."
        ),
    }
    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_live_compute_publication_handoff_rebound_parity_scenarios_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_live_compute_publication_handoff_rebound_parity_scenarios_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)
    print(f"design_guide_live_compute_publication_handoff_rebound_parity_scenarios {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

