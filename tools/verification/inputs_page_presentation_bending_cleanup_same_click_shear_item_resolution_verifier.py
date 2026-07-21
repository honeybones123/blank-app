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
    json_path = ARTIFACT_DIR / f"inputs_page_presentation_bending_cleanup_same_click_shear_item_resolution_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_presentation_bending_cleanup_same_click_shear_item_resolution_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original = inputs_page._shear_low_util_target_cleanup_item
    failures: list[str] = []
    cases: list[dict] = []

    def call_with(fake):
        inputs_page._shear_low_util_target_cleanup_item = fake
        return inputs_page.render_design_guide_presentation_bending_cleanup_same_click_shear_item_resolution(
            guidance_debug={"overview": {"utils": {"shear": 0.74}}},
            guidance_disp_state={"uls_Vstar": 25.0},
        )

    try:
        def contract_updates_fake(state, overview, *, threshold, allow_best_safe_below_threshold):
            return {
                "button_contract": {"updates": {"s_lig": 125}},
                "selected_action_updates": {"s_lig": 150},
                "updates": {"s_lig": 175},
                "candidate_search_evidence": {
                    "best_safe_candidate_updates": {"s_lig": 200},
                    "selected_candidate_updates": {"s_lig": 225},
                },
            }

        result = call_with(contract_updates_fake)
        cases.append({"name": "contract_updates_preferred", "result": result})
        if result[1] != {"updates": {"s_lig": 125}} or result[3] != {"s_lig": 125}:
            failures.append(f"contract_updates_precedence_mismatch:{result}")

        def selected_action_fake(state, overview, *, threshold, allow_best_safe_below_threshold):
            return {
                "selected_action_updates": {"s_lig": 150},
                "updates": {"s_lig": 175},
                "candidate_search_evidence": {
                    "best_safe_candidate_updates": {"s_lig": 200},
                    "selected_candidate_updates": {"s_lig": 225},
                },
            }

        result = call_with(selected_action_fake)
        cases.append({"name": "selected_action_updates_fallback", "result": result})
        if result[3] != {"s_lig": 150}:
            failures.append(f"selected_action_updates_fallback_mismatch:{result}")

        def item_updates_fake(state, overview, *, threshold, allow_best_safe_below_threshold):
            return {
                "updates": {"s_lig": 175},
                "candidate_search_evidence": {
                    "best_safe_candidate_updates": {"s_lig": 200},
                    "selected_candidate_updates": {"s_lig": 225},
                },
            }

        result = call_with(item_updates_fake)
        cases.append({"name": "item_updates_fallback", "result": result})
        if result[3] != {"s_lig": 175}:
            failures.append(f"item_updates_fallback_mismatch:{result}")

        def evidence_updates_fake(state, overview, *, threshold, allow_best_safe_below_threshold):
            return {
                "candidate_search_evidence": {
                    "best_safe_candidate_updates": {"s_lig": 200},
                    "selected_candidate_updates": {"s_lig": 225},
                },
            }

        result = call_with(evidence_updates_fake)
        cases.append({"name": "evidence_best_safe_updates_fallback", "result": result})
        if result[3] != {"s_lig": 200}:
            failures.append(f"evidence_best_safe_updates_fallback_mismatch:{result}")

        def selected_evidence_updates_fake(state, overview, *, threshold, allow_best_safe_below_threshold):
            return {
                "candidate_search_evidence": {
                    "selected_candidate_updates": {"s_lig": 225},
                },
            }

        result = call_with(selected_evidence_updates_fake)
        cases.append({"name": "evidence_selected_updates_fallback", "result": result})
        if result[3] != {"s_lig": 225}:
            failures.append(f"evidence_selected_updates_fallback_mismatch:{result}")

        def raising_fake(state, overview, *, threshold, allow_best_safe_below_threshold):
            raise RuntimeError("boom")

        result = call_with(raising_fake)
        cases.append({"name": "helper_exception_returns_empty_resolution", "result": result})
        if result != (None, {}, {}, {}):
            failures.append(f"exception_resolution_mismatch:{result}")
    finally:
        inputs_page._shear_low_util_target_cleanup_item = original

    payload_out = {
        "verifier": "inputs_page_presentation_bending_cleanup_same_click_shear_item_resolution_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Presentation Bending Cleanup Same-Click Shear Item Resolution Verifier",
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
