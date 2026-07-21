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
    json_path = ARTIFACT_DIR / f"inputs_page_exact_blocker_restamp_helpers_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_exact_blocker_restamp_helpers_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    source = {
        "bending": {
            "family": "bending",
            "current_util": 0.72,
            "failed_check_util": 0.73,
            "reason": "below final threshold",
        },
        "shear": {
            "family": "shear",
            "current_util": 0.91,
            "failed_check_util": 0.91,
            "attempted_util": 0.89,
            "reason": "keep attempted util",
        },
        "serviceability": {
            "family": "serviceability",
            "current_util": 0.2,
            "reason": "ignored family",
        },
        "raw": "passthrough",
    }
    restamped = inputs_page.render_design_guide_restamp_exact_blocker_current_utils(
        source,
        {"bending": "0.81", "shear": 0.91, "serviceability": 0.99},
    )

    evidence = {
        "exact_blockers_by_family": {"bending": {"current_util": 0.7}},
        "post_click_exact_blockers_by_family": {"shear": {"failed_check_util": 0.65}},
        "cleanup_evidence_by_family": {"raw": "keep"},
        "post_click_cleanup_evidence_by_family": {"serviceability": {"current_util": 0.1}},
        "other": {"bending": {"current_util": 0.1}},
    }
    restamped_evidence = inputs_page.render_design_guide_restamp_exact_blocker_maps_in_evidence(
        evidence,
        {"bending": 0.84, "shear": 0.82},
    )

    expect(
        "current_util_restamped",
        restamped["bending"]["current_util"] == 0.81
        and restamped["bending"]["starting_util"] == 0.81
        and restamped["bending"]["failed_check_util"] == 0.81,
        f"bending={restamped.get('bending')}",
    )
    expect(
        "previous_values_preserved_as_attempted",
        restamped["bending"]["attempted_util"] == 0.72
        and restamped["bending"]["attempted_candidate_util"] == 0.72
        and restamped["bending"]["rejected_candidate_util"] == 0.72
        and restamped["bending"]["rejected_candidate_failed_check_util"] == 0.72,
        f"bending={restamped.get('bending')}",
    )
    expect(
        "matching_util_keeps_existing_attempted",
        restamped["shear"]["current_util"] == 0.91
        and restamped["shear"]["attempted_util"] == 0.89,
        f"shear={restamped.get('shear')}",
    )
    expect(
        "unsupported_and_raw_passthrough",
        restamped["serviceability"] == source["serviceability"]
        and restamped["raw"] == "passthrough",
        f"restamped={restamped}",
    )
    expect(
        "evidence_maps_restamped",
        restamped_evidence["exact_blockers_by_family"]["bending"]["current_util"] == 0.84
        and restamped_evidence["post_click_exact_blockers_by_family"]["shear"]["current_util"] == 0.82
        and restamped_evidence["cleanup_evidence_by_family"]["raw"] == "keep"
        and restamped_evidence["post_click_cleanup_evidence_by_family"]["serviceability"]
        == {"current_util": 0.1}
        and restamped_evidence["other"] == {"bending": {"current_util": 0.1}},
        f"restamped_evidence={restamped_evidence}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "restamped": restamped,
        "restamped_evidence": restamped_evidence,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Exact Blocker Restamp Helpers Verifier",
                "",
                f"Verdict: `{result['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Failures",
                "",
                *(failures or ["None."]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
