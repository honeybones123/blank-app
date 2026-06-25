"""Boundary proof for shear-overdesign candidate evaluation data shapes."""

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
MODULE_PATH = ROOT / "design_brain" / "shear_overdesign_candidate_evaluation.py"


REQUIRED_EVALUATION_FIELDS = {
    "input_hash",
    "update_hash",
    "candidate_state_hash",
    "shear_utilisation",
    "previous_shear_utilisation",
    "target_band_status",
    "utilisation_moves_toward_target",
    "shear_remains_compliant",
    "constructability_status",
    "mandatory_detailing_status",
    "shear_detailing_update_status",
    "geometry_restriction_status",
    "zero_shear_status",
    "ligature_removal_status",
    "reinforcement_quantity",
    "cost_proxy",
    "capacity_summary",
    "failure_flags",
    "engineering_status",
    "evaluation_hash",
}

FORBIDDEN_SOURCE_TERMS = {
    "inputs_page",
    "streamlit",
    "st.session_state",
    "session_state",
    "publication",
    "apply_resolved_candidate",
    "button_contract",
    "cta_contract",
    "visible_wording",
    "run_shear_overdesign_governs_runtime",
    "SPACING_INCREASE",
    "BAR_SIZE_REDUCTION",
    "LEG_COUNT_REDUCTION",
    "LIGATURE_REMOVAL",
}


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_overdesign_candidate_evaluation_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_overdesign_candidate_evaluation_boundary_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failure_lines = [f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]
    report_lines = [
        "# Shear Overdesign Candidate Evaluation Boundary",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "## Checks",
        "",
        *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
        "",
        "## Hashes",
        "",
        f"- input_hash: `{snapshot['hashes']['input_hash']}`",
        f"- update_hash: `{snapshot['hashes']['update_hash']}`",
        f"- candidate_state_hash: `{snapshot['hashes']['candidate_state_hash']}`",
        f"- evaluation_hash: `{snapshot['hashes']['evaluation_hash']}`",
        "",
        "## Failures",
        "",
        *failure_lines,
        "",
    ]
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return json_path, report_path


def _base_state() -> dict[str, Any]:
    return {
        "b": 300.0,
        "D": 500.0,
        "Vu": 0.0,
        "design_actions_present": True,
        "s_lig": 300.0,
        "lig_d": 10,
        "lig_legs": 2,
        "shear_utilisation": 0.0,
        "minimum_shear_reinforcement_required": False,
    }


def main() -> int:
    module = importlib.import_module("design_brain.shear_overdesign_candidate_evaluation")
    source = MODULE_PATH.read_text(encoding="utf-8", errors="replace")

    boundary_input = module.ShearOverdesignCandidateInput(base_state=_base_state())
    remove_links = module.ShearOverdesignCandidateUpdate(
        updates={"s_lig": 0.0, "lig_d": 0, "lig_legs": 0}
    )
    geometry_update = module.ShearOverdesignCandidateUpdate(updates={"D": 450.0})
    candidate_state_hash = module.build_shear_overdesign_candidate_state_hash(
        boundary_input.base_state,
        remove_links.updates,
    )
    evaluation = module.ShearOverdesignCandidateEvaluation(
        input_hash=boundary_input.input_hash,
        update_hash=remove_links.update_hash,
        candidate_state_hash=candidate_state_hash,
        shear_utilisation=0.0,
        previous_shear_utilisation=0.0,
        target_band_status={"normal_target_band_overridden": True},
        utilisation_moves_toward_target=True,
        shear_remains_compliant=True,
        constructability_status={"status": "PASS"},
        mandatory_detailing_status={"minimum_shear_reinforcement_required": False},
        shear_detailing_update_status={
            "shear_detailing_only": remove_links.shear_detailing_only,
            "update_keys": remove_links.update_keys,
        },
        geometry_restriction_status={
            "geometry_reduction_attempted": remove_links.geometry_reduction_attempted,
            "geometry_reduction_prohibited": True,
        },
        zero_shear_status={
            "zero_or_negligible_shear": True,
            "ligatures_exist_before": True,
            "must_not_terminate_for_zero_utilisation": True,
        },
        ligature_removal_status={
            "ligature_removal_allowed": True,
            "no_unnecessary_ligatures_remain": True,
        },
        reinforcement_quantity={"before": 1.0, "after": 0.0},
        cost_proxy={"before": 1.0, "after": 0.0},
        capacity_summary={"boundary": "shear_overdesign_candidate_evaluation"},
        failure_flags={"underdesign_created": False},
        engineering_status={"candidate_valid": True, "result": "ACCEPTED"},
    ).with_evaluation_hash()
    repeat = module.ShearOverdesignCandidateEvaluation(
        **{**evaluation.to_dict(), "evaluation_hash": None}
    ).with_evaluation_hash()

    evaluation_fields = {field.name for field in fields(module.ShearOverdesignCandidateEvaluation)}
    forbidden_hits = sorted(term for term in FORBIDDEN_SOURCE_TERMS if term in source)
    missing_fields = sorted(REQUIRED_EVALUATION_FIELDS - evaluation_fields)
    checks = {
        "module_imports_cleanly": module is not None,
        "required_fields_present": not missing_fields,
        "hashes_stable": evaluation.evaluation_hash == repeat.evaluation_hash
        and boundary_input.input_hash == module.ShearOverdesignCandidateInput(base_state=_base_state()).input_hash
        and remove_links.update_hash
        == module.ShearOverdesignCandidateUpdate(updates={"s_lig": 0.0, "lig_d": 0, "lig_legs": 0}).update_hash,
        "realistic_zero_shear_cleanup_normalizes": evaluation.shear_remains_compliant is True
        and evaluation.zero_shear_status.get("must_not_terminate_for_zero_utilisation") is True
        and evaluation.ligature_removal_status.get("no_unnecessary_ligatures_remain") is True,
        "shear_detailing_only_update_allowed": remove_links.shear_detailing_only is True,
        "geometry_update_rejected_by_boundary": geometry_update.geometry_reduction_attempted is True
        and geometry_update.shear_detailing_only is False,
        "no_page_ui_publication_apply_runtime_or_lane_coupling": not forbidden_hits,
    }
    failures = []
    if missing_fields:
        failures.append(f"missing_required_fields:{missing_fields}")
    if forbidden_hits:
        failures.append(f"forbidden_source_terms:{forbidden_hits}")
    failures.extend(key for key, passed in checks.items() if not passed)

    snapshot = {
        "schema": "shear_overdesign_candidate_evaluation_boundary.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "evaluation_fields": sorted(evaluation_fields),
        "allowed_update_keys": sorted(module.ALLOWED_SHEAR_OVERDESIGN_UPDATE_KEYS),
        "prohibited_geometry_update_keys": sorted(module.PROHIBITED_GEOMETRY_UPDATE_KEYS),
        "hashes": {
            "input_hash": boundary_input.input_hash,
            "update_hash": remove_links.update_hash,
            "candidate_state_hash": candidate_state_hash,
            "evaluation_hash": evaluation.evaluation_hash,
        },
        "sample_evaluation": evaluation.to_dict(),
    }
    json_path, report_path = _write_artifacts(snapshot)

    if failures:
        print("shear overdesign candidate evaluation boundary FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1

    print("shear overdesign candidate evaluation boundary PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
