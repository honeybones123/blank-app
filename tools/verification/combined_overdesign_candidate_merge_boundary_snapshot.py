"""Boundary proof for combined overdesign candidate merge shapes."""

from __future__ import annotations

import importlib
import json
import sys
import time
from dataclasses import fields
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
MODULE_PATH = ROOT / "design_brain" / "combined_overdesign_candidate_merge.py"


REQUIRED_EVALUATION_FIELDS = {
    "input_hash",
    "update_hash",
    "candidate_state_hash",
    "source_family_ids",
    "source_candidates",
    "bending_utilisation_before",
    "shear_utilisation_before",
    "bending_utilisation_after",
    "shear_utilisation_after",
    "bending_moves_toward_target",
    "shear_moves_toward_target",
    "bending_compliant",
    "shear_compliant",
    "bending_inside_target_band",
    "shear_inside_target_band",
    "creates_bending_underdesign",
    "creates_shear_underdesign",
    "minimum_reinforcement_status",
    "zero_shear_status",
    "geometry_interaction_status",
    "reinforcement_interaction_status",
    "code_compliance_status",
    "detailing_status",
    "constructability_status",
    "reinforcement_quantity",
    "beam_volume",
    "cost_proxy",
    "rejection_reasons",
    "engineering_status",
    "evaluation_hash",
}

FORBIDDEN_SOURCE_TERMS = {
    "inputs_page",
    "streamlit",
    "st.session_state",
    "session_state",
    "publication",
    "button_contract",
    "cta_contract",
    "visible_wording",
    "family_chooser",
    "classify_governing_state",
    "contracted_optimisation_ladder_specs",
    "run_bending_overdesign_governs_runtime",
    "run_shear_overdesign_governs_runtime",
}


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_overdesign_candidate_merge_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_overdesign_candidate_merge_boundary_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Combined Overdesign Candidate Merge Boundary",
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
    module = importlib.import_module("design_brain.combined_overdesign_candidate_merge")
    source = MODULE_PATH.read_text(encoding="utf-8", errors="replace")
    bending = module.CombinedOverdesignSourceCandidate(
        source_family_id="BENDING_OVERDESIGN_GOVERNS",
        candidate_id="bend_reduce_bottom_reo",
        updates={"bot1_count": 4, "db_bot_1": 20},
    )
    shear = module.CombinedOverdesignSourceCandidate(
        source_family_id="SHEAR_OVERDESIGN_GOVERNS",
        candidate_id="shear_increase_spacing",
        updates={"s_lig": 300.0},
    )
    rogue = module.CombinedOverdesignSourceCandidate(
        source_family_id="BENDING_FAIL_GOVERNS",
        candidate_id="rogue_underdesign_source",
        updates={"D": 550.0},
    )
    merged_updates = module.merge_updates(bending.updates, shear.updates)
    merged = module.CombinedOverdesignMergedCandidate(
        candidate_id="combined_cleanup_bottom_reo_and_spacing",
        source_candidates=(bending, shear),
        updates=merged_updates,
    )
    inputs = module.CombinedOverdesignInputs(
        selected_family_id="COMBINED_OVERDESIGN_GOVERNS",
        base_state={"D": 500.0, "b": 300.0, "As": 2260.0, "As_min": 950.0},
        bending_overdesign_candidates=(bending.to_dict(),),
        shear_overdesign_candidates=(shear.to_dict(),),
    )
    evaluation = module.CombinedOverdesignCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=merged.update_hash,
        candidate_state_hash=module.combined_overdesign_candidate_state_hash(inputs.base_state, merged.updates),
        source_family_ids=merged.source_families,
        source_candidates=(bending.candidate_id, shear.candidate_id),
        bending_utilisation_before=0.62,
        shear_utilisation_before=0.41,
        bending_utilisation_after=0.91,
        shear_utilisation_after=0.88,
        bending_moves_toward_target=True,
        shear_moves_toward_target=True,
        bending_compliant=True,
        shear_compliant=True,
        bending_inside_target_band=True,
        shear_inside_target_band=True,
        creates_bending_underdesign=False,
        creates_shear_underdesign=False,
        minimum_reinforcement_status={"As": 1256.0, "As_min": 950.0, "status": "PASS"},
        zero_shear_status={"zero_shear": False, "ligature_removal_preferred": False},
        geometry_interaction_status={
            "geometry_changed": merged.interaction_flags["geometry_changed"],
            "rechecked": ["bending", "shear", "minimum reinforcement", "geometry limits", "constructability"],
        },
        reinforcement_interaction_status={
            "bending_reinforcement_changed": merged.interaction_flags["bending_reinforcement_changed"],
            "shear_reinforcement_changed": merged.interaction_flags["shear_reinforcement_changed"],
        },
        code_compliance_status={"status": "PASS"},
        detailing_status={"status": "PASS"},
        constructability_status={"status": "PASS"},
        reinforcement_quantity={"after": 2.0},
        beam_volume={"after": 150000.0},
        cost_proxy={"after": 0.72},
        engineering_status={"candidate_valid": True},
    ).with_evaluation_hash()
    underdesign = module.CombinedOverdesignCandidateEvaluation(
        **{
            **evaluation.to_dict(),
            "bending_utilisation_after": 1.06,
            "bending_compliant": False,
            "creates_bending_underdesign": True,
            "rejection_reasons": ("candidate creates bending underdesign",),
            "engineering_status": {"candidate_valid": False},
            "evaluation_hash": None,
        }
    ).with_evaluation_hash()
    repeat = module.CombinedOverdesignCandidateEvaluation(
        **{**evaluation.to_dict(), "evaluation_hash": None}
    ).with_evaluation_hash()
    evaluation_fields = {field.name for field in fields(module.CombinedOverdesignCandidateEvaluation)}
    missing_fields = sorted(REQUIRED_EVALUATION_FIELDS - evaluation_fields)
    forbidden_hits = sorted(term for term in FORBIDDEN_SOURCE_TERMS if term in source)
    checks = {
        "module_imports_cleanly": module is not None,
        "required_fields_present": not missing_fields,
        "selection_boundary_explicit": inputs.selection_boundary_satisfied is True,
        "allowed_sources_pass": bending.source_allowed is True and shear.source_allowed is True and merged.sources_allowed is True,
        "rogue_underdesign_source_rejected": rogue.source_allowed is False,
        "merge_hashes_stable": evaluation.evaluation_hash == repeat.evaluation_hash,
        "bending_and_shear_reinforcement_flags_set": merged.interaction_flags["bending_reinforcement_changed"] is True
        and merged.interaction_flags["shear_reinforcement_changed"] is True,
        "underdesign_can_be_represented_as_invalid": underdesign.creates_bending_underdesign is True
        and underdesign.engineering_status.get("candidate_valid") is False,
        "no_page_ui_publication_chooser_or_ladder_coupling": not forbidden_hits,
    }
    failures: list[str] = []
    if missing_fields:
        failures.append(f"missing_required_fields:{missing_fields}")
    if forbidden_hits:
        failures.append(f"forbidden_source_terms:{forbidden_hits}")
    failures.extend(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "combined_overdesign_candidate_merge_boundary.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "evaluation_fields": sorted(evaluation_fields),
        "allowed_source_families": sorted(module.ALLOWED_COMBINED_OVERDESIGN_SOURCE_FAMILIES),
        "hashes": {
            "input_hash": inputs.input_hash,
            "update_hash": merged.update_hash,
            "candidate_state_hash": evaluation.candidate_state_hash,
            "evaluation_hash": evaluation.evaluation_hash,
        },
        "sample_evaluation": evaluation.to_dict(),
        "underdesign_rejection": underdesign.to_dict(),
    }
    json_path, report_path = _write_artifacts(snapshot)
    if failures:
        print("combined overdesign candidate merge boundary FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("combined overdesign candidate merge boundary PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
