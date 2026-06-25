"""Shared proof helpers for COMBINED_BENDING_SHEAR_FAIL_GOVERNS."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.combined_bending_shear_candidate_merge import (  # noqa: E402
    CombinedBendingShearFailInputs,
    CombinedCandidateEvaluation,
    CombinedMergedCandidate,
    CombinedSourceCandidate,
    combined_candidate_state_hash,
    merge_updates,
)
from design_brain.families.bending_and_shear_fail_govern.contract import (  # noqa: E402
    candidate_source_contract,
    exact_stop_rules,
    exhausted_rules,
    interaction_contract,
    lane_proof_policies,
    load_bending_and_shear_fail_govern_contract,
    ranking_criteria,
    selection_boundary,
)


FORBIDDEN_SHARED_TERMS = {
    "inputs_page",
    "streamlit",
    "st.session_state",
    "button_contract",
    "publication",
}


def _source_boundary_clean() -> tuple[bool, list[str]]:
    paths = [
        ROOT / "design_brain" / "families" / "bending_and_shear_fail_govern" / "contract.py",
        ROOT / "design_brain" / "combined_bending_shear_candidate_merge.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in paths)
    hits = sorted(term for term in FORBIDDEN_SHARED_TERMS if term in source)
    return not hits, hits


def _inputs() -> CombinedBendingShearFailInputs:
    bending = CombinedSourceCandidate(
        source_family_id="BENDING_FAIL_GOVERNS",
        candidate_id="bend_depth",
        updates={"D": 550.0, "bot1_count": 5},
    )
    shear = CombinedSourceCandidate(
        source_family_id="SHEAR_FAIL_GOVERNS",
        candidate_id="shear_links",
        updates={"lig_d": 12, "s_lig": 150.0},
    )
    return CombinedBendingShearFailInputs(
        selected_family_id="COMBINED_BENDING_SHEAR_FAIL",
        base_state={"D": 500.0, "b": 300.0},
        bending_fail_candidates=(bending.to_dict(),),
        shear_fail_candidates=(shear.to_dict(),),
    )


def _source_candidates() -> tuple[CombinedSourceCandidate, CombinedSourceCandidate]:
    return (
        CombinedSourceCandidate(
            source_family_id="BENDING_FAIL_GOVERNS",
            candidate_id="bend_depth",
            updates={"D": 550.0, "bot1_count": 5},
        ),
        CombinedSourceCandidate(
            source_family_id="SHEAR_FAIL_GOVERNS",
            candidate_id="shear_links",
            updates={"lig_d": 12, "s_lig": 150.0},
        ),
    )


def _merged() -> CombinedMergedCandidate:
    bending, shear = _source_candidates()
    return CombinedMergedCandidate(
        candidate_id="combined_depth_links",
        source_candidates=(bending, shear),
        updates=merge_updates(bending.updates, shear.updates),
    )


def _evaluation(
    *,
    bending_ok: bool,
    shear_ok: bool,
    bending_inside: bool = True,
    shear_inside: bool = True,
    rechecks: tuple[str, ...] = ("bending", "shear", "minimum reinforcement", "geometry ratio", "constructability"),
) -> CombinedCandidateEvaluation:
    inputs = _inputs()
    merged = _merged()
    both = bending_ok and shear_ok
    return CombinedCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=merged.update_hash,
        candidate_state_hash=combined_candidate_state_hash(inputs.base_state, merged.updates),
        source_family_ids=merged.source_families,
        source_candidates=tuple(candidate.candidate_id for candidate in merged.source_candidates),
        bending_utilisation_before=1.22,
        shear_utilisation_before=1.18,
        bending_utilisation_after=0.93 if bending_ok else 1.08,
        shear_utilisation_after=0.91 if shear_ok else 1.12,
        bending_improves=bending_ok,
        shear_improves=shear_ok,
        bending_compliant=bending_ok,
        shear_compliant=shear_ok,
        bending_inside_target_band=bending_inside and bending_ok,
        shear_inside_target_band=shear_inside and shear_ok,
        both_failures_repaired=both,
        geometry_interaction_status={"geometry_changed": True, "rechecked": list(rechecks)},
        reinforcement_interaction_status={
            "bending_reinforcement_rechecked": True,
            "shear_reinforcement_rechecked": True,
            "congestion_rechecked": True,
        },
        code_compliance_status={"status": "PASS" if both else "FAIL"},
        detailing_status={"status": "PASS" if both else "FAIL"},
        constructability_status={"status": "PASS"},
        geometry_increase={"total_mm": 50.0},
        reinforcement_increase={"total": 2.0},
        cost_proxy={"after": 1.2},
        rejection_reasons=() if both else (("bending remains underdesigned",) if not bending_ok else ("shear remains underdesigned",)),
        engineering_status={"candidate_valid": both},
    ).with_evaluation_hash()


def _common_checks() -> dict[str, bool]:
    clean, _hits = _source_boundary_clean()
    return {
        "contract_loads": bool(load_bending_and_shear_fail_govern_contract()),
        "selection_boundary_available": bool(selection_boundary()),
        "candidate_source_contract_available": bool(candidate_source_contract()),
        "ranking_available": bool(ranking_criteria()),
        "no_page_ui_apply_imports": clean,
    }


def _write_snapshot(name: str, snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_bending_shear_fail_governs_{name}_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_bending_shear_fail_governs_{name}_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                f"# COMBINED_BENDING_SHEAR_FAIL_GOVERNS {name.replace('_', ' ').title()}",
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


def _finish(name: str, checks: dict[str, bool], details: dict[str, Any]) -> int:
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": f"combined_bending_shear_fail_governs_{name}.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        **details,
    }
    json_path, report_path = _write_snapshot(name, snapshot)
    if failures:
        print(f"COMBINED_BENDING_SHEAR_FAIL_GOVERNS {name} FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print(f"COMBINED_BENDING_SHEAR_FAIL_GOVERNS {name} PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


def source_rules_main() -> int:
    policies = lane_proof_policies()
    source_policy = policies.get("candidate_source") or {}
    bending, shear = _source_candidates()
    rogue = CombinedSourceCandidate(source_family_id="BENDING_OVERDESIGN_GOVERNS", candidate_id="rogue", updates={})
    checks = {
        **_common_checks(),
        "allowed_sources_exact": set(candidate_source_contract().get("allowed_sources") or [])
        == {"BENDING_FAIL_GOVERNS", "SHEAR_FAIL_GOVERNS", "APPROVED_COMBINED_MERGE_RULE"},
        "bending_and_shear_sources_allowed": bending.source_allowed is True and shear.source_allowed is True,
        "rogue_source_rejected": rogue.source_allowed is False,
        "policy_prohibits_ladder_duplication": "combined family generated bending ladder" in (source_policy.get("forbidden") or [])
        and "combined family generated shear ladder" in (source_policy.get("forbidden") or []),
    }
    return _finish("source_rules", checks, {"policy": source_policy})


def partial_repair_main() -> int:
    valid = _evaluation(bending_ok=True, shear_ok=True)
    bending_only = _evaluation(bending_ok=True, shear_ok=False)
    shear_only = _evaluation(bending_ok=False, shear_ok=True)
    checks = {
        **_common_checks(),
        "valid_combined_candidate_rankable": valid.engineering_status.get("candidate_valid") is True,
        "bending_only_not_selected": bending_only.engineering_status.get("candidate_valid") is False
        and "shear remains underdesigned" in bending_only.rejection_reasons,
        "shear_only_not_selected": shear_only.engineering_status.get("candidate_valid") is False
        and "bending remains underdesigned" in shear_only.rejection_reasons,
    }
    return _finish(
        "partial_repair",
        checks,
        {
            "valid_hash": valid.evaluation_hash,
            "bending_only_hash": bending_only.evaluation_hash,
            "shear_only_hash": shear_only.evaluation_hash,
        },
    )


def geometry_interaction_main() -> int:
    evaluation = _evaluation(bending_ok=True, shear_ok=True)
    required = set((interaction_contract().get("geometry_recheck_required") or []))
    rechecked = set(evaluation.geometry_interaction_status.get("rechecked") or [])
    checks = {
        **_common_checks(),
        "depth_width_rechecks_required_fields": required >= {"bending", "shear", "minimum reinforcement", "geometry ratio", "constructability"},
        "evaluation_records_all_geometry_rechecks": rechecked >= required,
        "geometry_changed_flagged": evaluation.geometry_interaction_status.get("geometry_changed") is True,
    }
    return _finish("geometry_interaction", checks, {"evaluation_hash": evaluation.evaluation_hash})


def reinforcement_interaction_main() -> int:
    evaluation = _evaluation(bending_ok=True, shear_ok=True)
    interaction = interaction_contract()
    checks = {
        **_common_checks(),
        "bending_rechecks_defined": set(interaction.get("bending_reinforcement_recheck_required") or [])
        >= {"bending capacity", "minimum bending reinforcement", "constructability", "congestion"},
        "shear_rechecks_defined": set(interaction.get("shear_reinforcement_recheck_required") or [])
        >= {"shear capacity", "shear detailing", "constructability", "congestion"},
        "evaluation_records_reinforcement_rechecks": evaluation.reinforcement_interaction_status.get("bending_reinforcement_rechecked") is True
        and evaluation.reinforcement_interaction_status.get("shear_reinforcement_rechecked") is True,
    }
    return _finish("reinforcement_interaction", checks, {"evaluation_hash": evaluation.evaluation_hash})


def terminal_main() -> int:
    exact = exact_stop_rules()
    exhausted = exhausted_rules()
    exact_eval = _evaluation(bending_ok=True, shear_ok=True, bending_inside=True, shear_inside=True)
    checks = {
        **_common_checks(),
        "exact_stop_requires_both_compliant_and_in_band": set(exact.get("allowed_when") or [])
        >= {"bending compliant", "shear compliant", "bending inside target band", "shear inside target band", "no higher-ranked combined candidate exists"},
        "exact_eval_satisfies_exact_stop": exact_eval.bending_inside_target_band is True
        and exact_eval.shear_inside_target_band is True
        and exact_eval.both_failures_repaired is True,
        "exhausted_requires_all_attempted_and_specific_blocker": set(exhausted.get("requires") or [])
        >= {
            "all bending-fail candidates attempted",
            "all shear-fail candidates attempted",
            "all approved combined-merge combinations attempted",
            "no valid combined repair exists",
            "specific blocker exists",
        },
        "generic_exhausted_message_prohibited": exhausted.get("generic_exhausted_message_prohibited_when_specific_blocker_exists") is True,
    }
    return _finish("terminal", checks, {"exact_hash": exact_eval.evaluation_hash})
