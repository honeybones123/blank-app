from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_presentation_bending_cleanup_expected_util_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_presentation_bending_cleanup_expected_util_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    def run_case(name: str, expected, *, family: str, updates: dict, evidence: dict) -> None:
        actual = inputs_page.render_design_guide_presentation_bending_cleanup_expected_util_setup(
            presentation_bending_family=family,
            presentation_bending_updates=updates,
            presentation_bending_evidence=evidence,
        )
        cases.append({"name": name, "expected": expected, "actual": actual})
        if actual != expected:
            failures.append(f"{name}:expected={expected}:actual={actual}")

    run_case(
        "selected_candidate_util_preferred",
        0.82,
        family="bending",
        updates={"bottom_bar_dia": 16},
        evidence={
            "selected_candidate_util": "0.82",
            "best_target_band_candidate_util": "0.9",
            "closest_safe_candidate_util": "0.75",
        },
    )
    run_case(
        "best_target_band_candidate_util_fallback",
        0.9,
        family="bending",
        updates={"bottom_bar_dia": 16},
        evidence={
            "best_target_band_candidate_util": "0.9",
            "closest_safe_candidate_util": "0.75",
        },
    )
    run_case(
        "closest_safe_candidate_util_fallback",
        0.75,
        family="bending",
        updates={"bottom_bar_dia": 16},
        evidence={"closest_safe_candidate_util": "0.75"},
    )
    run_case(
        "combined_family_uses_same_fallback_order",
        0.88,
        family="combined",
        updates={"s_lig": 150, "bottom_bar_dia": 16},
        evidence={"selected_candidate_util": "0.88"},
    )
    run_case(
        "empty_evidence_returns_none",
        None,
        family="bending",
        updates={"bottom_bar_dia": 16},
        evidence={},
    )
    run_case(
        "unparseable_evidence_returns_none",
        None,
        family="bending",
        updates={"bottom_bar_dia": 16},
        evidence={"selected_candidate_util": "not-a-number"},
    )

    payload_out = {
        "verifier": "inputs_page_presentation_bending_cleanup_expected_util_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Presentation Bending Cleanup Expected Util Setup Verifier",
                "",
                f"Status: `{payload_out['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`: `{case['actual']}`" for case in cases),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload_out["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
