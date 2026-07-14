"""Proof snapshot for the COMBINED_BENDING_SHEAR_FAIL_GOVERNS merge runtime."""

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
RUNTIME_PATH = ROOT / "design_brain" / "families" / "bending_and_shear_fail_govern" / "runtime.py"

from design_brain.combined_bending_shear_candidate_merge import (  # noqa: E402
    CombinedBendingShearFailInputs,
    CombinedCandidateEvaluation,
    CombinedMergedCandidate,
    combined_candidate_state_hash,
)
from design_brain.families.bending_and_shear_fail_govern.contract import ranking_criteria  # noqa: E402
from design_brain.families.bending_and_shear_fail_govern.runtime import (  # noqa: E402
    CombinedBendingShearFailResult,
    run_combined_bending_shear_fail_runtime,
)


REQUIRED_RESULT_FIELDS = {
    "status",
    "selected_strategy_lane",
    "combined_merge_trace",
    "candidate_repairs",
    "selected_recommendation",
    "accepted_candidate_evidence",
    "rejected_candidate_evidence",
    "ranking_evidence",
    "exact_stop_proof",
    "exhausted_reason",
    "exhausted_proof",
    "candidate_source_proof",
    "ownership_proof",
    "selection_boundary_proof",
    "cta_intent_proof",
    "contract_hash",
    "runtime_hash",
}

LEGACY_BOTTOM_KEYS = {"bot1_count", "db_bot_1", "bot2_count", "db_bot_2"}

FORBIDDEN_RUNTIME_TERMS = {
    "inputs_page",
    "streamlit",
    "st.session_state",
    "session_state",
    "publication",
    "button_contract",
    "visible_wording",
    "family_chooser",
    "classify_governing_state",
    "DEFAULT_DEPTH_STEPS_MM",
    "DEFAULT_WIDTH_STEPS_MM",
}


def _inputs() -> CombinedBendingShearFailInputs:
    return CombinedBendingShearFailInputs(
        selected_family_id="COMBINED_BENDING_SHEAR_FAIL",
        base_state={"D": 500.0, "b": 300.0},
        bending_fail_candidates=(
            {
                "source_family_id": "BENDING_FAIL_GOVERNS",
                "candidate_id": "bend_depth",
                "updates": {"D": 550.0, "bot_row_1_bars": 5},
            },
            {
                "source_family_id": "BENDING_FAIL_GOVERNS",
                "candidate_id": "bend_only",
                "updates": {"bot_row_1_bars": 6},
            },
        ),
        shear_fail_candidates=(
            {
                "source_family_id": "SHEAR_FAIL_GOVERNS",
                "candidate_id": "shear_links",
                "updates": {"lig_d": 12, "s_lig": 150.0},
            },
        ),
    )


def _evaluation(
    inputs: CombinedBendingShearFailInputs,
    candidate: CombinedMergedCandidate,
) -> CombinedCandidateEvaluation:
    updates = dict(candidate.updates)
    repairs_both = updates.get("D") == 550.0 and updates.get("lig_d") == 12
    bending_ok = bool(repairs_both or updates.get("bot_row_1_bars") == 6)
    shear_ok = bool(repairs_both)
    return CombinedCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=candidate.update_hash,
        candidate_state_hash=combined_candidate_state_hash(inputs.base_state, candidate.updates),
        source_family_ids=candidate.source_families,
        source_candidates=tuple(source.candidate_id for source in candidate.source_candidates),
        bending_utilisation_before=1.22,
        shear_utilisation_before=1.18,
        bending_utilisation_after=0.93 if bending_ok else 1.08,
        shear_utilisation_after=0.91 if shear_ok else 1.12,
        bending_improves=bending_ok,
        shear_improves=shear_ok,
        bending_compliant=bending_ok,
        shear_compliant=shear_ok,
        bending_inside_target_band=repairs_both,
        shear_inside_target_band=repairs_both,
        both_failures_repaired=repairs_both,
        geometry_interaction_status={"geometry_changed": "D" in updates, "rechecked": ["bending", "shear", "minimum reinforcement", "geometry ratio", "constructability"]},
        reinforcement_interaction_status={"bending_reinforcement_rechecked": True, "shear_reinforcement_rechecked": True},
        code_compliance_status={"status": "PASS" if repairs_both else "FAIL"},
        detailing_status={"status": "PASS" if repairs_both else "FAIL"},
        constructability_status={"status": "PASS"},
        geometry_increase={"total_mm": 50.0 if "D" in updates else 0.0},
        reinforcement_increase={"total": 2.0},
        cost_proxy={"after": 1.2 if repairs_both else 1.0},
        rejection_reasons=() if repairs_both else ("partial repair",),
        engineering_status={"candidate_valid": repairs_both},
    ).with_evaluation_hash()


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_bending_shear_fail_governs_runtime_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_bending_shear_fail_governs_runtime_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# COMBINED_BENDING_SHEAR_FAIL_GOVERNS Runtime Snapshot",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    result = run_combined_bending_shear_fail_runtime(inputs=_inputs(), evaluate_candidate=_evaluation)
    repeat = run_combined_bending_shear_fail_runtime(inputs=_inputs(), evaluate_candidate=_evaluation)
    empty = run_combined_bending_shear_fail_runtime(
        inputs=CombinedBendingShearFailInputs(selected_family_id="COMBINED_BENDING_SHEAR_FAIL"),
        evaluate_candidate=_evaluation,
    )
    fields_present = {field.name for field in fields(CombinedBendingShearFailResult)}
    runtime_source = RUNTIME_PATH.read_text(encoding="utf-8", errors="replace")
    forbidden_hits = sorted(term for term in FORBIDDEN_RUNTIME_TERMS if term in runtime_source)
    payload = result.to_dict()
    selected_updates = dict((payload.get("selected_recommendation") or {}).get("updates") or {})
    checks = {
        "required_result_fields_exist": REQUIRED_RESULT_FIELDS.issubset(fields_present),
        "source_merge_candidates_created": payload["candidate_source_proof"].get("merged_candidate_count") == 2,
        "sources_are_only_bending_and_shear": set(payload["selected_recommendation"].get("source_family_ids") or [])
        == {"BENDING_FAIL_GOVERNS", "SHEAR_FAIL_GOVERNS"},
        "partial_repairs_rejected_before_ranking": payload["ranking_evidence"].get("partial_repairs_ranked") is False
        and len(payload["rejected_candidate_evidence"]) >= 1,
        "selected_repairs_both": payload["selected_recommendation"].get("both_failures_repaired") is True,
        "exact_stop_proven": payload["exact_stop_proof"].get("exact_stop") is True,
        "exhausted_proven_for_missing_candidates": empty.status == "EXHAUSTED"
        and empty.exhausted_proof.get("specific_blocker") == "bending repair exhausted",
        "ranking_criteria_match_contract": tuple(payload["ranking_evidence"].get("criteria") or ()) == tuple(ranking_criteria()),
        "selection_boundary_no_reclassification": payload["selection_boundary_proof"].get("runtime_performed_classification") is False,
        "ownership_proof_shared_systems_outside": payload["ownership_proof"].get("shared_output_apply_render_state_owned_outside_runtime") is True,
        "cta_intent_proof_only": payload["cta_intent_proof"].get("proof_only") is True
        and payload["cta_intent_proof"].get("rendered") is False,
        "runtime_selected_updates_are_canonical_only": not bool(LEGACY_BOTTOM_KEYS & set(selected_updates)),
        "runtime_hash_stable": result.runtime_hash == repeat.runtime_hash,
        "runtime_has_no_page_ui_chooser_or_ladder_imports": not forbidden_hits,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    if forbidden_hits:
        failures.append(f"forbidden_runtime_terms:{forbidden_hits}")
    snapshot = {
        "schema": "combined_bending_shear_fail_governs_runtime_snapshot.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "runtime": {
            "status": result.status,
            "selected_strategy_lane": result.selected_strategy_lane,
            "candidate_count": len(result.candidate_repairs),
            "accepted_count": len(result.accepted_candidate_evidence),
            "rejected_count": len(result.rejected_candidate_evidence),
            "selected_updates": selected_updates,
            "runtime_hash": result.runtime_hash,
            "repeat_runtime_hash": repeat.runtime_hash,
        },
        "forbidden_runtime_terms": forbidden_hits,
    }
    json_path, report_path = _write_artifacts(snapshot)
    if failures:
        print("COMBINED_BENDING_SHEAR_FAIL_GOVERNS runtime FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("COMBINED_BENDING_SHEAR_FAIL_GOVERNS runtime PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
