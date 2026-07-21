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
    json_path = ARTIFACT_DIR / f"inputs_page_presentation_bending_cleanup_override_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_presentation_bending_cleanup_override_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    result = inputs_page.render_design_guide_presentation_bending_cleanup_override_setup(
        dg_presentation={"headline": "  Target band achieved  ", "subtext": "  Keep reducing  "},
        guidance_debug={
            "overview": {"utils": {"bending": "0.74"}},
            "candidate_search_evidence": {
                "target_band_candidate_count": 2,
                "best_target_band_candidate_updates": {"bottom_bar_dia": 16},
                "selected_candidate_updates": {"bottom_bar_dia": 20},
                "closest_safe_candidate_updates": {"bottom_bar_dia": 24},
            },
        },
    )
    cases.append({"name": "target_band_updates_are_preferred", "result": result})
    if result[0] != "Target band achieved":
        failures.append(f"target_band_headline_trim_mismatch:{result}")
    if result[1] != "Keep reducing":
        failures.append(f"target_band_subtext_trim_mismatch:{result}")
    if result[2] != 0.74:
        failures.append(f"target_band_bending_util_mismatch:{result}")
    if result[4] != {"bottom_bar_dia": 16}:
        failures.append(f"target_band_updates_precedence_mismatch:{result}")

    result = inputs_page.render_design_guide_presentation_bending_cleanup_override_setup(
        dg_presentation={"headline": "Target band achieved", "subtext": "Selected fallback"},
        guidance_debug={
            "overview": {"utils": {"bending": 0.81}},
            "candidate_search_evidence": {
                "target_band_candidate_count": 0,
                "best_target_band_candidate_updates": {"bottom_bar_dia": 12},
                "selected_candidate_updates": {"bottom_bar_dia": 20},
                "closest_safe_candidate_updates": {"bottom_bar_dia": 24},
            },
        },
    )
    cases.append({"name": "selected_updates_fallback_when_no_target_band_candidate", "result": result})
    if result[4] != {"bottom_bar_dia": 20}:
        failures.append(f"selected_updates_fallback_mismatch:{result}")

    result = inputs_page.render_design_guide_presentation_bending_cleanup_override_setup(
        dg_presentation={"headline": "Target band achieved", "subtext": "Closest fallback"},
        guidance_debug={
            "overview": {"utils": {}},
            "candidate_search_evidence": {
                "target_band_candidate_count": 0,
                "closest_safe_candidate_updates": {"bottom_bar_dia": 24},
            },
        },
    )
    cases.append({"name": "closest_safe_updates_fallback_and_missing_util", "result": result})
    if result[2] is not None:
        failures.append(f"missing_util_expected_none:{result}")
    if result[4] != {"bottom_bar_dia": 24}:
        failures.append(f"closest_safe_updates_fallback_mismatch:{result}")

    result = inputs_page.render_design_guide_presentation_bending_cleanup_override_setup(
        dg_presentation={},
        guidance_debug={},
    )
    cases.append({"name": "empty_inputs_are_stable", "result": result})
    if result != ("", "", None, {}, {}):
        failures.append(f"empty_inputs_mismatch:{result}")

    payload_out = {
        "verifier": "inputs_page_presentation_bending_cleanup_override_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Presentation Bending Cleanup Override Setup Verifier",
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
