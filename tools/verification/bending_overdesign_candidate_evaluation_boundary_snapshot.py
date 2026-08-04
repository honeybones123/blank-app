"""Boundary proof for bending-overdesign candidate evaluation data shapes."""

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
MODULE_PATH = ROOT / "design_brain" / "bending_overdesign_candidate_evaluation.py"


REQUIRED_EVALUATION_FIELDS = {
    "input_hash",
    "update_hash",
    "candidate_state_hash",
    "bending_utilisation",
    "previous_bending_utilisation",
    "target_band_status",
    "utilisation_moves_toward_target",
    "bending_remains_compliant",
    "constructability_status",
    "code_compliance_status",
    "minimum_reinforcement_status",
    "geometry_compliance_status",
    "beam_proportion_status",
    "reinforcement_quantity",
    "beam_volume",
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
    "run_bending_overdesign_governs_runtime",
    "BOTTOM_REINFORCEMENT_REDUCTION",
    "LAYER_REDUCTION",
    "WIDTH_REDUCTION",
    "DEPTH_REDUCTION",
    "EXACT_STOP",
    "EXHAUSTED",
}


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_overdesign_candidate_evaluation_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_overdesign_candidate_evaluation_boundary_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failure_lines = [f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]
    report_lines = [
        "# Bending Overdesign Candidate Evaluation Boundary",
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
        "Mstar": 220.0,
        "phiMu": 330.0,
        "bending_utilisation": 0.67,
        "As": 2260.0,
        "As_min": 950.0,
        "bot1_count": 5,
        "db_bot_1": 24,
        "bot_row_count": 1,
        "constructability": "PASS",
    }


def main() -> int:
    module = importlib.import_module("design_brain.bending_overdesign_candidate_evaluation")
    source = MODULE_PATH.read_text(encoding="utf-8", errors="replace")

    boundary_input = module.BendingOverdesignCandidateInput(base_state=_base_state())
    reinforcement_update = module.BendingOverdesignCandidateUpdate(updates={"bot1_count": 4, "db_bot_1": 24})
    geometry_update = module.BendingOverdesignCandidateUpdate(updates={"b": 275.0})
    invalid_update = module.BendingOverdesignCandidateUpdate(updates={"cta_label": "Apply this"})
    candidate_state_hash = module.build_bending_overdesign_candidate_state_hash(
        boundary_input.base_state,
        reinforcement_update.updates,
    )
    evaluation = module.BendingOverdesignCandidateEvaluation(
        input_hash=boundary_input.input_hash,
        update_hash=reinforcement_update.update_hash,
        candidate_state_hash=candidate_state_hash,
        bending_utilisation=0.86,
        previous_bending_utilisation=0.67,
        target_band_status={"lower": 0.85, "upper": 1.0, "inside": True},
        utilisation_moves_toward_target=True,
        bending_remains_compliant=True,
        constructability_status={"status": "PASS"},
        code_compliance_status={"status": "PASS"},
        minimum_reinforcement_status={
            "As": 1809.6,
            "As_min": 950.0,
            "As_greater_than_or_equal_to_As_min": True,
            "discard_before_ranking": False,
        },
        geometry_compliance_status={"status": "PASS"},
        beam_proportion_status={"status": "PASS"},
        reinforcement_quantity={"before": 2260.0, "after": 1809.6},
        beam_volume={"before": 150000.0, "after": 150000.0},
        cost_proxy={"before": 1.0, "after": 0.82},
        capacity_summary={"boundary": "bending_overdesign_candidate_evaluation"},
        failure_flags={"underdesign_created": False, "below_minimum_reinforcement": False},
        engineering_status={"candidate_valid": True, "result": "ACCEPTED"},
    ).with_evaluation_hash()
    below_minimum = module.BendingOverdesignCandidateEvaluation(
        input_hash=boundary_input.input_hash,
        update_hash=module.BendingOverdesignCandidateUpdate(updates={"bot1_count": 1, "db_bot_1": 16}).update_hash,
        candidate_state_hash=module.build_bending_overdesign_candidate_state_hash(
            boundary_input.base_state,
            {"bot1_count": 1, "db_bot_1": 16},
        ),
        bending_utilisation=1.14,
        previous_bending_utilisation=0.67,
        target_band_status={"inside": False},
        utilisation_moves_toward_target=False,
        bending_remains_compliant=False,
        constructability_status={"status": "PASS"},
        code_compliance_status={"status": "FAIL"},
        minimum_reinforcement_status={
            "As": 201.0,
            "As_min": 950.0,
            "As_greater_than_or_equal_to_As_min": False,
            "discard_before_ranking": True,
        },
        geometry_compliance_status={"status": "PASS"},
        beam_proportion_status={"status": "PASS"},
        reinforcement_quantity={"before": 2260.0, "after": 201.0},
        beam_volume={"before": 150000.0, "after": 150000.0},
        cost_proxy={"before": 1.0, "after": 0.12},
        capacity_summary={"boundary": "bending_overdesign_candidate_evaluation"},
        failure_flags={"underdesign_created": True, "below_minimum_reinforcement": True},
        engineering_status={"candidate_valid": False, "result": "REJECTED"},
    ).with_evaluation_hash()
    repeat = module.BendingOverdesignCandidateEvaluation(
        **{**evaluation.to_dict(), "evaluation_hash": None}
    ).with_evaluation_hash()

    evaluation_fields = {field.name for field in fields(module.BendingOverdesignCandidateEvaluation)}
    forbidden_hits = sorted(term for term in FORBIDDEN_SOURCE_TERMS if term in source)
    missing_fields = sorted(REQUIRED_EVALUATION_FIELDS - evaluation_fields)
    checks = {
        "module_imports_cleanly": module is not None,
        "required_fields_present": not missing_fields,
        "hashes_stable": evaluation.evaluation_hash == repeat.evaluation_hash
        and boundary_input.input_hash == module.BendingOverdesignCandidateInput(base_state=_base_state()).input_hash
        and reinforcement_update.update_hash
        == module.BendingOverdesignCandidateUpdate(updates={"bot1_count": 4, "db_bot_1": 24}).update_hash,
        "realistic_target_band_candidate_normalizes": evaluation.bending_remains_compliant is True
        and evaluation.target_band_status.get("inside") is True
        and evaluation.utilisation_moves_toward_target is True,
        "minimum_reinforcement_boundary_normalizes": below_minimum.minimum_reinforcement_status.get(
            "As_greater_than_or_equal_to_As_min"
        )
        is False
        and below_minimum.minimum_reinforcement_status.get("discard_before_ranking") is True
        and below_minimum.engineering_status.get("candidate_valid") is False,
        "reinforcement_update_recognized": reinforcement_update.reinforcement_update is True
        and reinforcement_update.bending_overdesign_update is True,
        "geometry_update_recognized": geometry_update.geometry_update is True
        and geometry_update.bending_overdesign_update is True,
        "non_boundary_update_rejected": invalid_update.bending_overdesign_update is False,
        "no_page_ui_publication_apply_runtime_or_lane_coupling": not forbidden_hits,
    }
    failures = []
    if missing_fields:
        failures.append(f"missing_required_fields:{missing_fields}")
    if forbidden_hits:
        failures.append(f"forbidden_source_terms:{forbidden_hits}")
    failures.extend(key for key, passed in checks.items() if not passed)

    snapshot = {
        "schema": "bending_overdesign_candidate_evaluation_boundary.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "evaluation_fields": sorted(evaluation_fields),
        "allowed_update_keys": sorted(module.ALLOWED_BENDING_OVERDESIGN_UPDATE_KEYS),
        "geometry_update_keys": sorted(module.GEOMETRY_UPDATE_KEYS),
        "reinforcement_update_keys": sorted(module.REINFORCEMENT_UPDATE_KEYS),
        "hashes": {
            "input_hash": boundary_input.input_hash,
            "update_hash": reinforcement_update.update_hash,
            "candidate_state_hash": candidate_state_hash,
            "evaluation_hash": evaluation.evaluation_hash,
        },
        "sample_evaluation": evaluation.to_dict(),
        "minimum_reinforcement_rejection": below_minimum.to_dict(),
    }
    json_path, report_path = _write_artifacts(snapshot)

    if failures:
        print("bending overdesign candidate evaluation boundary FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1

    print("bending overdesign candidate evaluation boundary PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
