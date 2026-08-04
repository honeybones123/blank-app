"""Current-live replacement audit for BENDING_FAIL_GOVERNS.

The contract runtime is authoritative. Old live behaviour is recorded only as
replacement-impact evidence and is not used as a test oracle.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import fields
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.candidate_evaluation import (  # noqa: E402
    BeamCandidateEvaluation,
    BeamCandidateInput,
    BeamCandidateUpdate,
    build_candidate_state_hash,
)
from design_brain.families.bending_fail import BendingFailFamily  # noqa: E402
from design_brain.families.bending_fail_governs.contract import (  # noqa: E402
    load_bending_fail_governs_contract,
)
from design_brain.families.bending_fail_governs.runtime import (  # noqa: E402
    BendingFailGovernsResult,
    bending_fail_governs_contract_lane_order,
    run_bending_fail_governs_ladder_runtime,
)


EXPECTED_CONTRACT_ORDER = (
    "GEOMETRY_SANITY",
    "SINGLE_LAYER_BOTTOM_REO",
    "LARGER_BAR",
    "MULTI_LAYER_REO",
    "DEPTH_INCREASE",
    "WIDTH_INCREASE",
    "EXACT_STOP",
    "NO_VALID_STRATEGY",
)

DIFFERENCE_CLASSES = {
    "EXPECTED_CONTRACT_REPLACEMENT",
    "MISSING_NEW_EVIDENCE_BLOCKER",
    "UNEXPLAINED_REPLACEMENT_RISK",
    "NO_OLD_EQUIVALENT_NEEDED",
}

REQUIRED_RESULT_FIELDS = {
    "selected_strategy_lane",
    "ladder_trace",
    "selected_recommendation",
    "accepted_lane_evidence",
    "rejected_lane_evidence",
    "repair_reason_proof",
    "blocked_reason",
    "cta_intent_proof",
    "ladder_hash",
}

FORBIDDEN_KEYS = {
    "apply_routing",
    "button_contract",
    "button_label",
    "publication",
    "published_item",
    "rendered_button",
    "rendered_html",
    "session",
    "session_state",
    "source_precedence",
    "ui",
    "visible_wording",
}


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_fail_governs_replacement_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_replacement_audit_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_FAIL_GOVERNS Replacement Audit",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "Authority rule: the new contract runtime is authoritative.",
                "Old live behaviour is replacement-impact evidence only.",
                "",
                "## Checks",
                "",
                f"- contract order unchanged: `{snapshot['checks']['contract_order_unchanged']}`",
                f"- required result fields exist: `{snapshot['checks']['required_result_fields_exist']}`",
                f"- new runtime evidence sufficient: `{snapshot['checks']['new_runtime_evidence_sufficient']}`",
                f"- missing evidence blockers absent: `{snapshot['checks']['missing_evidence_blockers_absent']}`",
                f"- unexplained replacement risks absent: `{snapshot['checks']['unexplained_replacement_risks_absent']}`",
                f"- old behaviour did not alter runtime: `{snapshot['checks']['old_behavior_did_not_alter_runtime']}`",
                f"- forbidden shared/page fields absent: `{snapshot['checks']['forbidden_fields_absent']}`",
                "",
                "## Contract Runtime Order",
                "",
                "```text",
                " -> ".join(snapshot["new_runtime"]["contract_order"]),
                "```",
                "",
                "## Current Live Impact Evidence",
                "",
                "```text",
                " -> ".join(snapshot["old_live_evidence"]["observed_lane_order"]),
                "```",
                "",
                "## Difference Classification",
                "",
                *[
                    f"- `{entry['item']}`: `{entry['class']}` - {entry['reason']}"
                    for entry in snapshot["difference_classification"]
                ],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def _walk_forbidden(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in FORBIDDEN_KEYS:
                found.add(str(key))
            found.update(_walk_forbidden(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(_walk_forbidden(child))
    return found


def _base_state() -> dict[str, Any]:
    return {
        "b": 300.0,
        "D": 350.0,
        "bot1_count": 2,
        "db_bot_1": 10,
        "bot_row_1_bars": 2,
        "bot_row_1_dia": 10,
        "cover_side": 40.0,
        "lig_d": 0,
    }


def _runtime_updates() -> dict[str, dict[str, Any]]:
    return {
        "GEOMETRY_SANITY": {},
        "DEPTH_INCREASE": {"D": 375.0},
        "SINGLE_LAYER_BOTTOM_REO": {"bot_row_1_bars": 3},
        "LARGER_BAR": {"bot_row_1_dia": 12},
        "WIDTH_INCREASE": {"b": 350.0},
        "MULTI_LAYER_REO": {"bot_row_2_bars": 2},
        "EXACT_STOP": {},
        "NO_VALID_STRATEGY": {},
    }


def _evaluation(
    *,
    candidate_input: BeamCandidateInput,
    candidate_update: BeamCandidateUpdate,
    accepted: bool,
    lane: str,
    reason: str,
) -> BeamCandidateEvaluation:
    return BeamCandidateEvaluation(
        input_hash=candidate_input.state_hash,
        candidate_state_hash=build_candidate_state_hash(candidate_input.base_state, candidate_update.updates),
        update_hash=candidate_update.update_hash,
        bending_utilisation=0.93 if accepted else 1.16,
        shear_utilisation=0.71,
        serviceability_status={"status": "PASS"},
        geometry_status={"status": "CHECKED"},
        detailing_status={"status": "CHECKED"},
        spacing_status={"status": "CHECKED"},
        capacity_summary={"boundary": "candidate_evaluation_api_shape"},
        failure_flags={"bending_fail": not accepted},
        engineering_status={
            "accepted": accepted,
            "lane_result": reason,
            "terminal_status": reason if lane in {"EXACT_STOP", "NO_VALID_STRATEGY"} and accepted else None,
            "blocked_reason": reason if lane == "NO_VALID_STRATEGY" and accepted else None,
        },
    ).with_evaluation_hash()


def _run_authoritative_runtime() -> dict[str, Any]:
    call_order = list(EXPECTED_CONTRACT_ORDER)
    calls: list[str] = []

    def evaluator(candidate_input: BeamCandidateInput, candidate_update: BeamCandidateUpdate) -> BeamCandidateEvaluation:
        lane = call_order[len(calls)]
        calls.append(lane)
        accepted = lane == "DEPTH_INCREASE"
        return _evaluation(
            candidate_input=candidate_input,
            candidate_update=candidate_update,
            accepted=accepted,
            lane=lane,
            reason="ACCEPTED" if accepted else "REJECTED",
        )

    result = run_bending_fail_governs_ladder_runtime(
        base_state=_base_state(),
        lane_candidate_updates=_runtime_updates(),
        evaluate_candidate=evaluator,
    )
    return {
        "result": result,
        "calls": calls,
        "payload": result.to_dict(),
    }


def _infer_old_lane(spec: dict[str, Any]) -> str:
    stage = str(spec.get("stage_name") or "")
    strategy = str(spec.get("strategy") or "").lower()
    updates = dict(spec.get("updates") or {})
    if stage == "stage_1_reo_only_same_geometry":
        if "split bottom reinforcement" in strategy or bool(spec.get("split_row")):
            return "MULTI_LAYER_REO"
        if "diameter" in strategy or "db_bot_1" in updates or "bot_row_1_dia" in updates:
            return "LARGER_BAR"
        return "SINGLE_LAYER_BOTTOM_REO"
    if stage == "stage_2_depth_increments_same_width":
        return "DEPTH_INCREASE"
    if stage == "stage_3_width_increments_for_reo_fit":
        return "WIDTH_INCREASE"
    if stage == "stage_4_combined_rescue":
        return "WIDTH_INCREASE"
    return f"UNKNOWN:{stage or 'missing_stage'}"


def _current_live_evidence() -> dict[str, Any]:
    family = BendingFailFamily()
    result = family.contracted_repair_ladder_specs(_base_state(), geometry_locked=False)
    specs = [dict(spec) for spec in result.get("specs") or []]
    lane_sequence = [_infer_old_lane(spec) for spec in specs]
    observed_order: list[str] = []
    for lane in lane_sequence:
        if lane not in observed_order:
            observed_order.append(lane)
    return {
        "source": "BendingFailFamily.contracted_repair_ladder_specs",
        "used_as_authority": False,
        "candidate_count": len(specs),
        "observed_lane_order": observed_order,
        "candidate_lane_sequence": lane_sequence,
    }


def _classify_differences(
    *,
    new_order: tuple[str, ...],
    old_order: list[str],
    runtime_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if tuple(old_order) != new_order:
        rows.append(
            {
                "item": "old_live_order_differs_from_contract_runtime",
                "class": "EXPECTED_CONTRACT_REPLACEMENT",
                "reason": "The contract runtime order is authoritative; old lane ordering is replacement impact evidence only.",
                "old_order": old_order,
                "new_order": list(new_order),
            }
        )
    else:
        rows.append(
            {
                "item": "old_live_order_matches_contract_runtime",
                "class": "NO_OLD_EQUIVALENT_NEEDED",
                "reason": "No replacement order difference was observed for this fixture.",
            }
        )

    old_missing = [lane for lane in new_order if lane not in old_order]
    if old_missing:
        rows.append(
            {
                "item": "contract_lanes_without_old_live_equivalent",
                "class": "NO_OLD_EQUIVALENT_NEEDED",
                "reason": "The contract owns terminal and sanity lanes even where the old repair-ladder trace did not expose equivalent lanes.",
                "lanes": old_missing,
            }
        )

    missing_evidence = []
    if not runtime_payload.get("ladder_trace"):
        missing_evidence.append("ladder_trace")
    if not runtime_payload.get("accepted_lane_evidence"):
        missing_evidence.append("accepted_lane_evidence")
    if runtime_payload.get("repair_reason_proof") is None:
        missing_evidence.append("repair_reason_proof")
    if runtime_payload.get("cta_intent_proof") is None:
        missing_evidence.append("cta_intent_proof")
    if missing_evidence:
        rows.append(
            {
                "item": "new_runtime_missing_required_evidence",
                "class": "MISSING_NEW_EVIDENCE_BLOCKER",
                "reason": "Cutover cannot proceed until the new runtime emits these proof surfaces.",
                "missing": missing_evidence,
            }
        )
    else:
        rows.append(
            {
                "item": "new_runtime_evidence_surface",
                "class": "EXPECTED_CONTRACT_REPLACEMENT",
                "reason": "The new runtime emits trace, accepted/rejected evidence, repair proof, CTA proof, and stable ladder hash.",
            }
        )
    return rows


def main() -> int:
    contract = load_bending_fail_governs_contract()
    new_order = bending_fail_governs_contract_lane_order()
    before_old = _run_authoritative_runtime()
    old_evidence = _current_live_evidence()
    after_old = _run_authoritative_runtime()
    runtime_payload = before_old["payload"]
    difference_rows = _classify_differences(
        new_order=new_order,
        old_order=list(old_evidence["observed_lane_order"]),
        runtime_payload=runtime_payload,
    )
    classes = {str(row.get("class")) for row in difference_rows}
    unknown_classes = sorted(classes - DIFFERENCE_CLASSES)
    blocker_rows = [
        row for row in difference_rows if row.get("class") == "MISSING_NEW_EVIDENCE_BLOCKER"
    ]
    risk_rows = [
        row for row in difference_rows if row.get("class") == "UNEXPLAINED_REPLACEMENT_RISK"
    ]
    forbidden_fields = sorted(_walk_forbidden(runtime_payload))
    required_fields = {field.name for field in fields(BendingFailGovernsResult)}

    checks = {
        "contract_order_unchanged": new_order == EXPECTED_CONTRACT_ORDER,
        "required_result_fields_exist": REQUIRED_RESULT_FIELDS.issubset(required_fields),
        "new_runtime_evidence_sufficient": bool(runtime_payload.get("ladder_trace"))
        and bool(runtime_payload.get("accepted_lane_evidence"))
        and runtime_payload.get("repair_reason_proof") is not None
        and runtime_payload.get("cta_intent_proof") is not None
        and bool(runtime_payload.get("ladder_hash")),
        "missing_evidence_blockers_absent": not blocker_rows,
        "unexplained_replacement_risks_absent": not risk_rows and not unknown_classes,
        "old_behavior_did_not_alter_runtime": before_old["result"].ladder_hash == after_old["result"].ladder_hash
        and before_old["calls"] == after_old["calls"],
        "forbidden_fields_absent": not forbidden_fields,
    }

    snapshot = {
        "schema": "bending_fail_governs_replacement_audit.v1",
        "result": "PASS" if all(checks.values()) else "FAIL",
        "authority_rule": "new_contract_runtime_is_authoritative",
        "contract_schema": contract.get("schema"),
        "checks": checks,
        "new_runtime": {
            "contract_order": list(new_order),
            "selected_strategy_lane": runtime_payload.get("selected_strategy_lane"),
            "called_lanes": before_old["calls"],
            "required_result_fields": sorted(REQUIRED_RESULT_FIELDS),
            "actual_result_fields": sorted(required_fields),
            "ladder_hash": runtime_payload.get("ladder_hash"),
            "evidence_summary": {
                "ladder_trace_count": len(runtime_payload.get("ladder_trace") or []),
                "accepted_lane_count": len(runtime_payload.get("accepted_lane_evidence") or []),
                "rejected_lane_count": len(runtime_payload.get("rejected_lane_evidence") or []),
                "has_repair_reason_proof": runtime_payload.get("repair_reason_proof") is not None,
                "has_cta_intent_proof": runtime_payload.get("cta_intent_proof") is not None,
            },
        },
        "old_live_evidence": old_evidence,
        "difference_classification": difference_rows,
        "forbidden_fields": forbidden_fields,
        "scope_limits": {
            "contract_changed": False,
            "runtime_order_changed": False,
            "compatibility_branches_added": False,
            "old_implementation_used_as_oracle": False,
            "cutover_enabled": False,
            "cta_publication_apply_ui_moved": False,
        },
    }
    json_path, report_path = _write_artifacts(snapshot)

    if snapshot["result"] != "PASS":
        print("replacement audit FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1

    print("replacement audit PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
