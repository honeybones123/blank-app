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
    json_path = ARTIFACT_DIR / f"inputs_page_presentation_bending_cleanup_same_click_shear_merge_acceptance_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_presentation_bending_cleanup_same_click_shear_merge_acceptance_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    base = {
        "presentation_same_updates": {"s_lig": 150, "bottom_bar_dia": 16},
        "presentation_same_util": 0.92,
        "presentation_same_shear_util": 0.92,
        "presentation_same_shear_exact_stop_proven": False,
        "presentation_same_overview": {
            "any_fail": False,
            "statuses": {"bending": "PASS", "shear": "PASS"},
        },
        "presentation_same_statuses": {"bending": "PASS", "shear": "PASS"},
    }

    def cloned_base() -> dict:
        return {
            key: (dict(value) if isinstance(value, dict) else value)
            for key, value in base.items()
        }

    def run_case(name: str, expected: bool, **overrides) -> None:
        payload = cloned_base()
        payload.update(overrides)
        actual = inputs_page.render_design_guide_presentation_bending_cleanup_same_click_shear_merge_accepted(
            **payload
        )
        cases.append({"name": name, "expected": expected, "actual": actual})
        if actual is not expected:
            failures.append(f"{name}:expected={expected}:actual={actual}")

    run_case("accepted_when_shear_reaches_threshold", True)
    run_case("empty_updates_block", False, presentation_same_updates={})
    run_case("missing_same_util_blocks", False, presentation_same_util=None)
    run_case("missing_shear_util_blocks", False, presentation_same_shear_util=None)
    run_case("low_shear_without_exact_stop_blocks", False, presentation_same_shear_util=0.70)
    run_case(
        "low_shear_with_exact_stop_is_allowed",
        True,
        presentation_same_shear_util=0.70,
        presentation_same_shear_exact_stop_proven=True,
    )
    run_case(
        "overview_any_fail_blocks",
        False,
        presentation_same_overview={"any_fail": True, "statuses": {"shear": "PASS"}},
    )
    run_case(
        "unacceptable_required_checks_block",
        False,
        presentation_same_overview={
            "any_fail": False,
            "statuses": {"bending": "FAIL", "shear": "PASS"},
        },
    )
    run_case(
        "explicit_preview_fail_blocks",
        False,
        presentation_same_statuses={"bending": "PASS", "shear": "FAIL"},
    )

    payload_out = {
        "verifier": "inputs_page_presentation_bending_cleanup_same_click_shear_merge_acceptance_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Presentation Bending Cleanup Same-Click Shear Merge Acceptance Verifier",
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
