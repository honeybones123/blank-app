from __future__ import annotations

import ast
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
MODULE_PATH = ROOT / "design_brain" / "shear_fail_bending_overdesign_candidate_merge.py"

FORBIDDEN_IMPORT_ROOTS = {"inputs_page", "streamlit"}
FORBIDDEN_SOURCE_TERMS = {
    "inputs_page",
    "streamlit",
    "st.session_state",
    "session_state",
    "button_contract",
    "publication",
    "apply_routing",
    "one_click",
    "run_shear_fail_governs_ladder_runtime",
    "run_bending_overdesign_governs_runtime",
}
REQUIRED_FIELDS = {
    "MixedCandidateEvaluation": {
        "input_hash",
        "update_hash",
        "candidate_state_hash",
        "shear_repaired",
        "bending_compliant",
        "creates_bending_underdesign",
        "evaluation_hash",
    },
    "ShearFailBendingOverdesignInputs": {
        "selected_family_id",
        "shear_fail_candidates",
        "bending_overdesign_candidates",
        "approved_mixed_merge_candidates",
    },
}


def _source() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


def _imports(source: str) -> list[str]:
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(imports)


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_fail_bending_overdesign_candidate_merge_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_bending_overdesign_candidate_merge_boundary_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SHEAR_FAIL_BENDING_OVERDESIGN Candidate Merge Boundary",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "This proves the data-boundary shape only.",
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
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    source = _source()
    imports = _imports(source)
    forbidden_imports = [item for item in imports if item.split(".", 1)[0] in FORBIDDEN_IMPORT_ROOTS]
    lowered = source.lower()
    forbidden_source_hits = sorted(term for term in FORBIDDEN_SOURCE_TERMS if term.lower() in lowered)

    from design_brain.shear_fail_bending_overdesign_candidate_merge import (  # noqa: WPS433
        MixedCandidateEvaluation,
        MixedMergedCandidate,
        MixedSourceCandidate,
        ShearFailBendingOverdesignInputs,
        merge_updates,
        mixed_candidate_state_hash,
        source_family_allowed,
        stable_shear_fail_bending_overdesign_hash,
    )

    shear = MixedSourceCandidate(
        source_family_id="SHEAR_FAIL_GOVERNS",
        candidate_id="shear_repair",
        updates={"lig_d": 12, "s_lig": 125},
    )
    bending = MixedSourceCandidate(
        source_family_id="BENDING_OVERDESIGN_GOVERNS",
        candidate_id="bending_cleanup",
        updates={"bot1_count": 4},
    )
    merged_updates = merge_updates(shear.updates, bending.updates)
    merged = MixedMergedCandidate(
        candidate_id="shear_repair+bending_cleanup",
        source_candidates=(shear, bending),
        updates=merged_updates,
    )
    inputs = ShearFailBendingOverdesignInputs(
        selected_family_id="SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        base_state={"D": 500.0, "b": 300.0, "s_lig": 200, "bot1_count": 5},
        shear_fail_candidates=(shear.to_dict(),),
        bending_overdesign_candidates=(bending.to_dict(),),
    )
    evaluation = MixedCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=merged.update_hash,
        candidate_state_hash=mixed_candidate_state_hash(inputs.base_state, merged.updates),
        source_family_ids=merged.source_families,
        source_candidates=tuple(candidate.candidate_id for candidate in merged.source_candidates),
        bending_utilisation_before=0.52,
        shear_utilisation_before=1.18,
        bending_utilisation_after=0.78,
        shear_utilisation_after=0.94,
        shear_repaired=True,
        bending_compliant=True,
        bending_moves_toward_target=True,
        creates_bending_underdesign=False,
        code_compliance_status={"status": "PASS"},
        constructability_status={"status": "PASS"},
        reinforcement_quantity={"after": 100.0},
        beam_volume={"after": 1.0},
        cost_proxy={"after": 1.0},
        engineering_status={"candidate_valid": True},
    ).with_evaluation_hash()
    repeated = MixedCandidateEvaluation(**{**evaluation.to_dict(), "evaluation_hash": None}).with_evaluation_hash()

    missing_fields = {
        "MixedCandidateEvaluation": sorted(REQUIRED_FIELDS["MixedCandidateEvaluation"] - {field.name for field in fields(MixedCandidateEvaluation)}),
        "ShearFailBendingOverdesignInputs": sorted(REQUIRED_FIELDS["ShearFailBendingOverdesignInputs"] - {field.name for field in fields(ShearFailBendingOverdesignInputs)}),
    }
    checks = {
        "imports_clean": not forbidden_imports,
        "source_terms_clean": not forbidden_source_hits,
        "required_fields_present": not any(missing_fields.values()),
        "allowed_sources_enforced": source_family_allowed("SHEAR_FAIL_GOVERNS")
        and source_family_allowed("BENDING_OVERDESIGN_GOVERNS")
        and not source_family_allowed("SHEAR_OVERDESIGN_GOVERNS"),
        "mandatory_shear_source_present": merged.has_mandatory_shear_source,
        "opportunistic_bending_source_present": merged.has_opportunistic_bending_source,
        "merged_update_hash_stable": merged.update_hash == stable_shear_fail_bending_overdesign_hash(merged.updates),
        "candidate_state_hash_stable": evaluation.candidate_state_hash == mixed_candidate_state_hash(inputs.base_state, merged.updates),
        "evaluation_hash_stable": evaluation.evaluation_hash == repeated.evaluation_hash,
        "selection_boundary_satisfied": inputs.selection_boundary_satisfied,
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "shear_fail_bending_overdesign_candidate_merge_boundary.v1",
        "result": "PASS" if not failures else "FAIL",
        "module": str(MODULE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "imports": imports,
        "forbidden_imports": forbidden_imports,
        "forbidden_source_hits": forbidden_source_hits,
        "missing_required_fields": missing_fields,
        "checks": checks,
        "hashes": {
            "input_hash": inputs.input_hash,
            "update_hash": merged.update_hash,
            "candidate_state_hash": evaluation.candidate_state_hash,
            "evaluation_hash": evaluation.evaluation_hash,
        },
        "sample": {
            "inputs": inputs.to_dict(),
            "merged_candidate": merged.to_dict(),
            "evaluation": evaluation.to_dict(),
        },
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("shear fail bending overdesign candidate merge boundary FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("shear fail bending overdesign candidate merge boundary PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
