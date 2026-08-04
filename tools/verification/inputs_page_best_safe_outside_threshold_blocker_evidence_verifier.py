from __future__ import annotations

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


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_best_safe_outside_threshold_blocker_evidence_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_best_safe_outside_threshold_blocker_evidence_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    bending_evidence = {
        "best_safe_candidate_updates": {"D": 550},
        "attempted_candidate_count": 4,
        "safe_candidate_count": 2,
        "target_high": 1.05,
        "blocker_reasons_by_family": {"shear": ["existing"]},
    }
    bending_exact = inputs_page.render_design_guide_displayed_best_safe_outside_threshold_blocker_evidence(
        proof_action_family="bending",
        proof_action_expected_util=0.74,
        proof_action_contract_for_evidence={"updates": {"D": 600}},
        engine_candidate_search_evidence=bending_evidence,
        overview={"utils": {"bending": 0.82}},
    )
    bending_blocker = dict(bending_exact.get("bending") or {})
    cases.append({"name": "bending_created", "exact": bending_exact, "evidence": bending_evidence})
    if bending_blocker.get("family") != "bending":
        failures.append(f"bending_family_mismatch:{bending_blocker}")
    if bending_blocker.get("best_safe_candidate_updates") != {"D": 600}:
        failures.append(f"bending_updates_precedence_mismatch:{bending_blocker}")
    if bending_blocker.get("current_util") != 0.82:
        failures.append(f"bending_current_util_mismatch:{bending_blocker}")
    if bending_blocker.get("safe_bending_cleanup_count") != 2:
        failures.append(f"bending_safe_count_mismatch:{bending_blocker}")
    if bending_evidence.get("post_click_exact_blockers_by_family") != bending_exact:
        failures.append(f"bending_post_click_map_not_written:{bending_evidence}")
    if bending_evidence.get("blocker_reasons_by_family", {}).get("shear") != ["existing"]:
        failures.append(f"bending_existing_reasons_lost:{bending_evidence}")

    shear_evidence = {
        "selected_candidate_updates": {"s_lig": 150},
        "total_candidates_considered": 3,
        "safe_executor_backed_candidates_count": 5,
        "selected_candidate_id": "safe-shear-1",
    }
    shear_exact = inputs_page.render_design_guide_displayed_best_safe_outside_threshold_blocker_evidence(
        proof_action_family="shear",
        proof_action_expected_util=0.73,
        proof_action_contract_for_evidence={},
        engine_candidate_search_evidence=shear_evidence,
        overview={"utils": {}},
    )
    shear_blocker = dict(shear_exact.get("shear") or {})
    cases.append({"name": "shear_created", "exact": shear_exact, "evidence": shear_evidence})
    if shear_blocker.get("current_util") != 0.73:
        failures.append(f"shear_current_util_fallback_mismatch:{shear_blocker}")
    if shear_blocker.get("safe_shear_cleanup_count") != 5:
        failures.append(f"shear_safe_count_mismatch:{shear_blocker}")
    if shear_blocker.get("failed_candidate_id") != "safe-shear-1":
        failures.append(f"shear_failed_candidate_id_mismatch:{shear_blocker}")

    existing_blocker = {"family": "bending", "source": "existing"}
    existing_evidence = {
        "exact_blockers_by_family": {"bending": dict(existing_blocker)},
        "blocker_reasons_by_family": {"bending": ["keep"]},
    }
    existing_exact = inputs_page.render_design_guide_displayed_best_safe_outside_threshold_blocker_evidence(
        proof_action_family="bending",
        proof_action_expected_util=0.7,
        proof_action_contract_for_evidence={"updates": {"D": 700}},
        engine_candidate_search_evidence=existing_evidence,
        overview={"utils": {"bending": 0.8}},
    )
    cases.append({"name": "existing_preserved", "exact": existing_exact, "evidence": existing_evidence})
    if existing_exact.get("bending") != existing_blocker:
        failures.append(f"existing_blocker_changed:{existing_exact}")
    if "post_click_exact_blockers_by_family" in existing_evidence:
        failures.append(f"existing_branch_unexpected_write:{existing_evidence}")

    payload = {
        "verifier": "inputs_page_best_safe_outside_threshold_blocker_evidence_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Best Safe Outside Threshold Blocker Evidence Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(f"- `{case['name']}` families: `{sorted(case['exact'].keys())}`" for case in cases),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
