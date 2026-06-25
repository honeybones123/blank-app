from __future__ import annotations

import ast
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
RUNTIME_PATH = ROOT / "design_brain" / "families" / "shear_fail_bending_overdesign_governs" / "runtime.py"

from design_brain.shear_fail_bending_overdesign_candidate_merge import (  # noqa: E402
    MixedCandidateEvaluation,
    MixedMergedCandidate,
    ShearFailBendingOverdesignInputs,
    mixed_candidate_state_hash,
)
from design_brain.families.shear_fail_bending_overdesign_governs.contract import (  # noqa: E402
    contract_hash,
    ranking_criteria,
)
from design_brain.families.shear_fail_bending_overdesign_governs.runtime import (  # noqa: E402
    run_shear_fail_bending_overdesign_runtime,
)


FORBIDDEN_RUNTIME_TERMS = {
    "inputs_page",
    "streamlit",
    "st.session_state",
    "button_contract",
    "publication",
    "apply_routing",
    "one_click",
    "run_shear_fail_governs_ladder_runtime",
    "run_bending_overdesign_governs_runtime",
}


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
    json_path = ARTIFACT_DIR / f"shear_fail_bending_overdesign_governs_runtime_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_bending_overdesign_governs_runtime_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SHEAR_FAIL_BENDING_OVERDESIGN Runtime Snapshot",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Runtime",
                "",
                f"- runtime_hash: `{snapshot['runtime_hash']}`",
                f"- selected: `{snapshot['selected_candidate_id']}`",
                f"- ranking: `{snapshot['ranking_criteria']}`",
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


def _evaluate(inputs: ShearFailBendingOverdesignInputs, candidate: MixedMergedCandidate) -> MixedCandidateEvaluation:
    has_shear = candidate.has_mandatory_shear_source
    has_bending = candidate.has_opportunistic_bending_source
    creates_bending_underdesign = candidate.candidate_id == "shear_repair+bending_bad_cleanup"
    return MixedCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=candidate.update_hash,
        candidate_state_hash=mixed_candidate_state_hash(inputs.base_state, candidate.updates),
        source_family_ids=candidate.source_families,
        source_candidates=tuple(source.candidate_id for source in candidate.source_candidates),
        bending_utilisation_before=0.52,
        shear_utilisation_before=1.18,
        bending_utilisation_after=1.04 if creates_bending_underdesign else (0.91 if has_bending else 0.52),
        shear_utilisation_after=0.93 if has_shear else 1.18,
        shear_repaired=has_shear,
        bending_compliant=not creates_bending_underdesign,
        bending_moves_toward_target=has_bending and not creates_bending_underdesign,
        creates_bending_underdesign=creates_bending_underdesign,
        code_compliance_status={"status": "PASS"},
        constructability_status={"status": "PASS"},
        reinforcement_quantity={"increase": 4.0 if has_bending else 8.0},
        beam_volume={"geometry_increase": 0.0},
        cost_proxy={"after": 80.0 if has_bending else 100.0},
        engineering_status={"candidate_valid": has_shear and not creates_bending_underdesign},
    ).with_evaluation_hash()


def main() -> int:
    inputs = ShearFailBendingOverdesignInputs(
        selected_family_id="SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        base_state={"Vstar": 260.0, "phiVu": 210.0, "Mstar": 180.0, "phiMu": 360.0},
        shear_fail_candidates=(
            {"source_family_id": "SHEAR_FAIL_GOVERNS", "candidate_id": "shear_repair", "updates": {"s_lig": 125}},
        ),
        bending_overdesign_candidates=(
            {"source_family_id": "BENDING_OVERDESIGN_GOVERNS", "candidate_id": "bending_cleanup", "updates": {"bot1_count": 4}},
            {"source_family_id": "BENDING_OVERDESIGN_GOVERNS", "candidate_id": "bending_bad_cleanup", "updates": {"bot1_count": 2}},
        ),
    )
    result = run_shear_fail_bending_overdesign_runtime(inputs=inputs, evaluate_candidate=_evaluate)
    repeat = run_shear_fail_bending_overdesign_runtime(inputs=inputs, evaluate_candidate=_evaluate)
    source = RUNTIME_PATH.read_text(encoding="utf-8", errors="replace")
    imports = _imports(source)
    forbidden_imports = [item for item in imports if item.split(".", 1)[0] in {"inputs_page", "streamlit"}]
    forbidden_terms = sorted(term for term in FORBIDDEN_RUNTIME_TERMS if term.lower() in source.lower())
    checks = {
        "runtime_boundary_clean": not forbidden_imports and not forbidden_terms,
        "contract_hash_present": bool(contract_hash()),
        "status_selected": result.status == "SELECTED",
        "selected_uses_mandatory_source": "SHEAR_FAIL_GOVERNS" in tuple((result.selected_recommendation or {}).get("source_family_ids") or ()),
        "selected_can_use_opportunistic_source": "BENDING_OVERDESIGN_GOVERNS" in tuple((result.selected_recommendation or {}).get("source_family_ids") or ()),
        "bad_bending_cleanup_rejected": any(
            row.get("creates_bending_underdesign") is True and row.get("accepted") is False
            for row in result.rejected_candidate_evidence
        ),
        "ranking_order_from_contract": tuple(result.ranking_evidence.get("criteria") or ()) == tuple(ranking_criteria()),
        "runtime_hash_stable": result.runtime_hash == repeat.runtime_hash,
        "proof_only_shared_surfaces": result.ownership_proof.get("shared_surfaces_owned_outside") is True,
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "shear_fail_bending_overdesign_governs_runtime.v1",
        "result": "PASS" if not failures else "FAIL",
        "runtime_hash": result.runtime_hash,
        "selected_candidate_id": (result.selected_recommendation or {}).get("candidate_id"),
        "ranking_criteria": list(result.ranking_evidence.get("criteria") or ()),
        "contract_hash": contract_hash(),
        "checks": checks,
        "forbidden_imports": forbidden_imports,
        "forbidden_terms": forbidden_terms,
        "runtime_result": result.to_family_result_payload(),
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS runtime snapshot FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS runtime snapshot PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
