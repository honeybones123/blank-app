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
    json_path = ARTIFACT_DIR / f"inputs_page_presentation_bending_cleanup_same_click_shear_fold_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_presentation_bending_cleanup_same_click_shear_fold_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    def run_case(
        name: str,
        *,
        expected_allowed: bool,
        guidance_debug: dict,
        guidance_disp_state: dict,
        presentation_bending_updates: dict,
    ) -> None:
        result = inputs_page.render_design_guide_presentation_bending_cleanup_same_click_shear_fold_setup(
            guidance_debug=guidance_debug,
            guidance_disp_state=guidance_disp_state,
            presentation_bending_updates=presentation_bending_updates,
        )
        cases.append({"name": name, "expected_allowed": expected_allowed, "result": result})
        if result[2] is not expected_allowed:
            failures.append(f"{name}:expected_allowed={expected_allowed}:result={result}")

    run_case(
        "positive_same_click_shear_fold_allowed",
        expected_allowed=True,
        guidance_debug={"overview": {"utils": {"shear": 0.74}}},
        guidance_disp_state={"uls_Vstar": 25.0, "load_Vstar_proxy": 0.0},
        presentation_bending_updates={"bottom_bar_dia": 16},
    )
    run_case(
        "missing_shear_util_blocks",
        expected_allowed=False,
        guidance_debug={"overview": {"utils": {}}},
        guidance_disp_state={"uls_Vstar": 25.0, "load_Vstar_proxy": 0.0},
        presentation_bending_updates={"bottom_bar_dia": 16},
    )
    run_case(
        "accepted_shear_util_blocks",
        expected_allowed=False,
        guidance_debug={"overview": {"utils": {"shear": 0.95}}},
        guidance_disp_state={"uls_Vstar": 25.0, "load_Vstar_proxy": 0.0},
        presentation_bending_updates={"bottom_bar_dia": 16},
    )
    run_case(
        "zero_shear_demand_blocks",
        expected_allowed=False,
        guidance_debug={"overview": {"utils": {"shear": 0.74}}},
        guidance_disp_state={"uls_Vstar": 0.0, "load_Vstar_proxy": 0.0},
        presentation_bending_updates={"bottom_bar_dia": 16},
    )
    run_case(
        "empty_bending_updates_blocks",
        expected_allowed=False,
        guidance_debug={"overview": {"utils": {"shear": 0.74}}},
        guidance_disp_state={"uls_Vstar": 25.0, "load_Vstar_proxy": 0.0},
        presentation_bending_updates={},
    )
    run_case(
        "compound_shear_update_blocks",
        expected_allowed=False,
        guidance_debug={"overview": {"utils": {"shear": 0.74}}},
        guidance_disp_state={"uls_Vstar": 25.0, "load_Vstar_proxy": 0.0},
        presentation_bending_updates={"s_lig": 150},
    )

    payload_out = {
        "verifier": "inputs_page_presentation_bending_cleanup_same_click_shear_fold_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Presentation Bending Cleanup Same-Click Shear Fold Setup Verifier",
                "",
                f"Status: `{payload_out['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`: `{case['result'][2]}`" for case in cases),
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
