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
    json_path = ARTIFACT_DIR / f"inputs_page_proof_action_threshold_state_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_proof_action_threshold_state_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _run_case(
        name: str,
        *,
        proof_contract: dict,
        item: dict | None,
        evidence: dict,
        expected: tuple[str, float | None, bool],
    ) -> None:
        result = inputs_page.render_design_guide_proof_action_threshold_state(
            proof_action_contract_for_evidence=dict(proof_contract),
            displayed_primary_item=None if item is None else dict(item),
            engine_candidate_search_evidence=dict(evidence),
        )
        cases.append(
            {
                "name": name,
                "proof_contract": proof_contract,
                "item": item,
                "evidence": evidence,
                "result": list(result),
                "expected": list(expected),
            }
        )
        if result != expected:
            failures.append(f"{name}_mismatch:result={result}:expected={expected}")

    _run_case(
        "proof_contract_family_and_expected_util_win",
        proof_contract={"family": "shear", "expected_util": "0.74"},
        item={"family": "bending"},
        evidence={
            "selected_candidate_util": 0.8,
            "best_safe_partial_cleanup": True,
            "target_band_candidate_count": 0,
            "executable_target_band_candidate_count": 0,
        },
        expected=("shear", 0.74, True),
    )
    _run_case(
        "item_check_key_and_selected_util_fallback",
        proof_contract={},
        item={"check_key": "bending"},
        evidence={
            "selected_candidate_util": 0.9,
            "no_second_cta_required": True,
            "target_band_candidate_count": 0,
            "executable_target_band_candidate_count": 0,
        },
        expected=("bending", 0.9, False),
    )
    _run_case(
        "closest_safe_util_and_target_candidate_blocks_threshold",
        proof_contract={"family": "bending"},
        item=None,
        evidence={
            "closest_safe_candidate_util": 0.74,
            "best_safe_partial_cleanup": True,
            "target_band_candidate_count": 1,
            "executable_target_band_candidate_count": 0,
        },
        expected=("bending", 0.74, False),
    )
    _run_case(
        "unsupported_family_never_thresholds",
        proof_contract={"family": "serviceability", "expected_util": 0.5},
        item={"family": "bending"},
        evidence={
            "best_safe_partial_cleanup": True,
            "target_band_candidate_count": 0,
            "executable_target_band_candidate_count": 0,
        },
        expected=("serviceability", 0.5, False),
    )

    payload = {
        "verifier": "inputs_page_proof_action_threshold_state_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Proof Action Threshold State Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(f"- `{case['name']}` result: `{case['result']}`" for case in cases),
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
