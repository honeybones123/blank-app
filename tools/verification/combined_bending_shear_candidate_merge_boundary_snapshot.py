"""Boundary proof for combined bending/shear candidate merge shapes."""

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
MODULE_PATH = ROOT / "design_brain" / "combined_bending_shear_candidate_merge.py"


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
    "bending_improves",
    "shear_improves",
    "bending_compliant",
    "shear_compliant",
    "bending_inside_target_band",
    "shear_inside_target_band",
    "both_failures_repaired",
    "geometry_interaction_status",
    "reinforcement_interaction_status",
    "code_compliance_status",
    "detailing_status",
    "constructability_status",
    "geometry_increase",
    "reinforcement_increase",
    "cost_proxy",
    "rejection_reasons",
    "engineering_status",
    "evaluation_hash",
}

LEGACY_BOTTOM_KEYS = {"bot1_count", "db_bot_1", "bot2_count", "db_bot_2"}
CANONICAL_BOTTOM_KEYS = {"bot_row_count", "bot_row_1_bars", "bot_row_1_dia", "bot_row_2_bars", "bot_row_2_dia"}

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
    "contracted_repair_ladder_specs",
}


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_bending_shear_candidate_merge_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_bending_shear_candidate_merge_boundary_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Combined Bending/Shear Candidate Merge Boundary",
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
    module = importlib.import_module("design_brain.combined_bending_shear_candidate_merge")
    source = MODULE_PATH.read_text(encoding="utf-8", errors="replace")
    bending = module.CombinedSourceCandidate(
        source_family_id="BENDING_FAIL_GOVERNS",
        candidate_id="bend_depth",
        updates={"D": 550.0, "bot1_count": 5, "db_bot_1": 20},
    )
    shear = module.CombinedSourceCandidate(
        source_family_id="SHEAR_FAIL_GOVERNS",
        candidate_id="shear_links",
        updates={"lig_d": 12, "s_lig": 150.0},
    )
    rogue = module.CombinedSourceCandidate(
        source_family_id="BENDING_OVERDESIGN_GOVERNS",
        candidate_id="rogue_cleanup",
        updates={"bot1_count": 2},
    )
    merged_updates = module.merge_updates(bending.updates, shear.updates)
    merged = module.CombinedMergedCandidate(
        candidate_id="combined_depth_links",
        source_candidates=(bending, shear),
        updates=merged_updates,
    )
    inputs = module.CombinedBendingShearFailInputs(
        selected_family_id="COMBINED_BENDING_SHEAR_FAIL",
        base_state={"D": 500.0, "b": 300.0},
        bending_fail_candidates=(bending.to_dict(),),
        shear_fail_candidates=(shear.to_dict(),),
    )
    evaluation = module.CombinedCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=merged.update_hash,
        candidate_state_hash=module.combined_candidate_state_hash(inputs.base_state, merged.updates),
        source_family_ids=merged.source_families,
        source_candidates=(bending.candidate_id, shear.candidate_id),
        bending_utilisation_before=1.22,
        shear_utilisation_before=1.18,
        bending_utilisation_after=0.93,
        shear_utilisation_after=0.91,
        bending_improves=True,
        shear_improves=True,
        bending_compliant=True,
        shear_compliant=True,
        bending_inside_target_band=True,
        shear_inside_target_band=True,
        both_failures_repaired=True,
        geometry_interaction_status={
            "geometry_changed": merged.interaction_flags["geometry_changed"],
            "rechecked": ["bending", "shear", "minimum reinforcement", "geometry ratio", "constructability"],
        },
        reinforcement_interaction_status={
            "bending_reinforcement_changed": merged.interaction_flags["bending_reinforcement_changed"],
            "shear_reinforcement_changed": merged.interaction_flags["shear_reinforcement_changed"],
        },
        code_compliance_status={"status": "PASS"},
        detailing_status={"status": "PASS"},
        constructability_status={"status": "PASS"},
        geometry_increase={"depth": 50.0, "width": 0.0},
        reinforcement_increase={"bending": 1.0, "shear": 1.0},
        cost_proxy={"after": 1.2},
        engineering_status={"candidate_valid": True},
    ).with_evaluation_hash()
    partial = module.CombinedCandidateEvaluation(
        **{
            **evaluation.to_dict(),
            "shear_utilisation_after": 1.12,
            "shear_compliant": False,
            "shear_inside_target_band": False,
            "both_failures_repaired": False,
            "rejection_reasons": ("shear remains underdesigned",),
            "engineering_status": {"candidate_valid": False},
            "evaluation_hash": None,
        }
    ).with_evaluation_hash()
    repeat = module.CombinedCandidateEvaluation(**{**evaluation.to_dict(), "evaluation_hash": None}).with_evaluation_hash()
    evaluation_fields = {field.name for field in fields(module.CombinedCandidateEvaluation)}
    missing_fields = sorted(REQUIRED_EVALUATION_FIELDS - evaluation_fields)
    forbidden_hits = sorted(term for term in FORBIDDEN_SOURCE_TERMS if term in source)
    checks = {
        "module_imports_cleanly": module is not None,
        "required_fields_present": not missing_fields,
        "selection_boundary_explicit": inputs.selection_boundary_satisfied is True,
        "allowed_sources_pass": bending.source_allowed is True and shear.source_allowed is True and merged.sources_allowed is True,
        "rogue_source_rejected": rogue.source_allowed is False,
        "merge_hashes_stable": evaluation.evaluation_hash == repeat.evaluation_hash,
        "merged_updates_are_canonical_only": bool(CANONICAL_BOTTOM_KEYS & set(merged_updates))
        and not bool(LEGACY_BOTTOM_KEYS & set(merged_updates)),
        "compatibility_projection_removed": not hasattr(
            module,
            "project_combined_reinforcement_update_compatibility_mirrors",
        ),
        "geometry_interaction_flagged": merged.interaction_flags["geometry_changed"] is True,
        "partial_repair_can_be_represented_as_invalid": partial.both_failures_repaired is False
        and partial.engineering_status.get("candidate_valid") is False,
        "no_page_ui_publication_chooser_or_ladder_coupling": not forbidden_hits,
    }
    failures = []
    if missing_fields:
        failures.append(f"missing_required_fields:{missing_fields}")
    if forbidden_hits:
        failures.append(f"forbidden_source_terms:{forbidden_hits}")
    failures.extend(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "combined_bending_shear_candidate_merge_boundary.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "evaluation_fields": sorted(evaluation_fields),
        "allowed_source_families": sorted(module.ALLOWED_COMBINED_SOURCE_FAMILIES),
        "hashes": {
            "input_hash": inputs.input_hash,
            "update_hash": merged.update_hash,
            "candidate_state_hash": evaluation.candidate_state_hash,
            "evaluation_hash": evaluation.evaluation_hash,
        },
        "merged_updates": merged_updates,
        "sample_evaluation": evaluation.to_dict(),
        "partial_repair_rejection": partial.to_dict(),
    }
    json_path, report_path = _write_artifacts(snapshot)
    if failures:
        print("combined bending/shear candidate merge boundary FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("combined bending/shear candidate merge boundary PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
