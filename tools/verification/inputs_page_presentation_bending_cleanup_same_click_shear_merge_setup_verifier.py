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
    json_path = ARTIFACT_DIR / f"inputs_page_presentation_bending_cleanup_same_click_shear_merge_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_presentation_bending_cleanup_same_click_shear_merge_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original = inputs_page._publishable_same_click_shear_cleanup_merge
    failures: list[str] = []
    cases: list[dict] = []

    def call_with(fake):
        inputs_page._publishable_same_click_shear_cleanup_merge = fake
        return inputs_page.render_design_guide_presentation_bending_cleanup_same_click_shear_merge_setup(
            guidance_disp_state={"uls_Vstar": 25.0},
            presentation_shear_updates={"s_lig": 150},
        )

    try:
        def expected_util_fake(state, updates):
            return {
                "updates": {"s_lig": 150, "bottom_bar_dia": 16},
                "expected_util": "0.82",
                "overview": {
                    "worst_util": "0.76",
                    "governing_util": "0.74",
                    "utils": {"shear": "0.84"},
                    "statuses": {"shear": "PASS"},
                },
                "evidence": {
                    "post_click_exact_blockers_by_family": {"shear": {"reason": "spacing"}},
                },
            }

        result = call_with(expected_util_fake)
        cases.append({"name": "expected_util_and_post_click_exact_blocker", "result": result})
        if result[1] != {"s_lig": 150, "bottom_bar_dia": 16}:
            failures.append(f"updates_mismatch:{result}")
        if result[3] != {"shear": "PASS"}:
            failures.append(f"statuses_mismatch:{result}")
        if result[4] != 0.82:
            failures.append(f"expected_util_precedence_mismatch:{result}")
        if result[5] != 0.84:
            failures.append(f"shear_util_mismatch:{result}")
        if result[7] != {"shear": {"reason": "spacing"}} or result[8] is not True:
            failures.append(f"post_click_exact_blocker_mismatch:{result}")

        def worst_util_fake(state, updates):
            return {
                "updates": {"s_lig": 175},
                "overview": {
                    "worst_util": "0.79",
                    "governing_util": "0.77",
                    "utils": {"shear": "0.81"},
                },
                "evidence": {
                    "exact_blockers_by_family": {"bending": {"reason": "depth"}},
                },
            }

        result = call_with(worst_util_fake)
        cases.append({"name": "worst_util_and_exact_blocker_fallback", "result": result})
        if result[4] != 0.79:
            failures.append(f"worst_util_fallback_mismatch:{result}")
        if result[7] != {"bending": {"reason": "depth"}} or result[8] is not False:
            failures.append(f"exact_blocker_fallback_mismatch:{result}")

        def governing_util_fake(state, updates):
            return {
                "updates": {},
                "overview": {"governing_util": "0.78", "utils": {}},
                "evidence": {},
            }

        result = call_with(governing_util_fake)
        cases.append({"name": "governing_util_fallback_and_empty_outputs", "result": result})
        if result[1] != {} or result[3] != {} or result[4] != 0.78 or result[5] is not None:
            failures.append(f"governing_util_empty_output_mismatch:{result}")
    finally:
        inputs_page._publishable_same_click_shear_cleanup_merge = original

    payload_out = {
        "verifier": "inputs_page_presentation_bending_cleanup_same_click_shear_merge_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Presentation Bending Cleanup Same-Click Shear Merge Setup Verifier",
                "",
                f"Status: `{payload_out['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`" for case in cases),
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
