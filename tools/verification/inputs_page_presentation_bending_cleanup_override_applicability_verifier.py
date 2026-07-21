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
    json_path = ARTIFACT_DIR / f"inputs_page_presentation_bending_cleanup_override_applicability_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_presentation_bending_cleanup_override_applicability_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    base = {
        "presentation_headline": "Target band achieved",
        "presentation_bending_util": 0.74,
        "presentation_bending_evidence": {
            "search_scope": "design_guide_bending_only_cleanup",
            "safe_executor_backed_candidates_count": 1,
        },
        "presentation_bending_updates": {"bottom_bar_dia": 16},
        "guidance_items": [{"title": "Primary"}],
        "guidance_debug": {},
    }

    failures: list[str] = []
    cases: list[dict] = []

    def run_case(name: str, expected: bool, **overrides) -> None:
        payload = {
            key: (dict(value) if isinstance(value, dict) else list(value) if isinstance(value, list) else value)
            for key, value in base.items()
        }
        payload.update(overrides)
        actual = inputs_page.render_design_guide_presentation_bending_cleanup_override_applicable(**payload)
        cases.append({"name": name, "expected": expected, "actual": actual})
        if actual is not expected:
            failures.append(f"{name}:expected={expected}:actual={actual}")

    run_case("positive_applicability", True)
    run_case("headline_must_be_target_band_achieved", False, presentation_headline="Design is efficient")
    run_case("bending_util_required", False, presentation_bending_util=None)
    run_case("bending_util_must_be_below_final_threshold", False, presentation_bending_util=0.85)
    run_case(
        "search_scope_must_be_bending_only",
        False,
        presentation_bending_evidence={
            "search_scope": "design_guide_combined_cleanup",
            "safe_executor_backed_candidates_count": 1,
        },
    )
    run_case(
        "safe_executor_backed_candidate_required",
        False,
        presentation_bending_evidence={
            "search_scope": "design_guide_bending_only_cleanup",
            "safe_executor_backed_candidates_count": 0,
        },
    )
    run_case("updates_required", False, presentation_bending_updates={})
    run_case("primary_guidance_item_required", False, guidance_items=[])
    run_case("primary_guidance_item_must_be_dict", False, guidance_items=["not-a-dict"])
    run_case(
        "active_fail_repaired_green_secondary_blocker_suppresses",
        False,
        guidance_debug={"active_fail_repaired_green_with_secondary_blocker": True},
    )
    run_case(
        "post_click_accepted_green_suppresses",
        False,
        guidance_debug={"post_click_accepted_green_valid": True},
    )

    payload_out = {
        "verifier": "inputs_page_presentation_bending_cleanup_override_applicability_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Presentation Bending Cleanup Override Applicability Verifier",
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
