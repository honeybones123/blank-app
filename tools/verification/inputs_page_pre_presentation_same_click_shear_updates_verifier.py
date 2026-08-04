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
    json_path = ARTIFACT_DIR / f"inputs_page_pre_presentation_same_click_shear_updates_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_pre_presentation_same_click_shear_updates_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_shear_low_util_target_cleanup_item": inputs_page._shear_low_util_target_cleanup_item,
        "_COMPOUND_SHEAR_UPDATE_KEYS": inputs_page._COMPOUND_SHEAR_UPDATE_KEYS,
        "FINAL_ACCEPTED_MIN_FAMILY_UTIL": inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _run_case(name: str, *, updates: dict, helper_result: Any):
        helper_calls: list[dict[str, Any]] = []

        def _helper(state, overview, *, threshold, allow_best_safe_below_threshold):
            helper_calls.append(
                {
                    "state": dict(state),
                    "overview": dict(overview),
                    "threshold": threshold,
                    "allow_best_safe_below_threshold": allow_best_safe_below_threshold,
                }
            )
            if helper_result == "raise":
                raise RuntimeError("boom")
            return helper_result

        try:
            inputs_page._COMPOUND_SHEAR_UPDATE_KEYS = {"shear_links", "shear_diameter"}
            inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85
            inputs_page._shear_low_util_target_cleanup_item = _helper
            result = inputs_page.render_design_guide_pre_presentation_same_click_shear_updates(
                pre_presentation_updates=dict(updates),
                guidance_disp_state={"depth": 500},
                pre_presentation_overview={"utils": {"shear": 0.4}},
            )
        finally:
            _restore()
        cases.append({"name": name, "result": result, "helper_calls": helper_calls})
        return result, helper_calls

    result, helper_calls = _run_case(
        "existing_shear_updates_preferred",
        updates={"bottom_bars": 4, "shear_links": "reduce"},
        helper_result={"button_contract": {"updates": {"shear_links": "helper"}}},
    )
    if result != {"shear_links": "reduce"}:
        failures.append(f"existing_shear_updates_mismatch:{result}")
    if helper_calls:
        failures.append(f"existing_shear_helper_called:{helper_calls}")

    result, helper_calls = _run_case(
        "button_contract_updates_fallback",
        updates={"bottom_bars": 4},
        helper_result={"button_contract": {"updates": {"shear_diameter": 10}}},
    )
    if result != {"shear_diameter": 10}:
        failures.append(f"contract_fallback_mismatch:{result}")
    if not helper_calls or helper_calls[0].get("threshold") != 0.85:
        failures.append(f"contract_helper_call_mismatch:{helper_calls}")
    if helper_calls and helper_calls[0].get("allow_best_safe_below_threshold") is not True:
        failures.append(f"contract_helper_allow_flag_mismatch:{helper_calls}")

    result, _ = _run_case(
        "selected_action_updates_fallback",
        updates={},
        helper_result={"selected_action_updates": {"shear_links": "selected"}},
    )
    if result != {"shear_links": "selected"}:
        failures.append(f"selected_action_fallback_mismatch:{result}")

    result, _ = _run_case(
        "item_updates_fallback",
        updates={},
        helper_result={"updates": {"shear_links": "item"}},
    )
    if result != {"shear_links": "item"}:
        failures.append(f"item_updates_fallback_mismatch:{result}")

    result, _ = _run_case(
        "evidence_best_safe_fallback",
        updates={},
        helper_result={"candidate_search_evidence": {"best_safe_candidate_updates": {"shear_links": "best"}}},
    )
    if result != {"shear_links": "best"}:
        failures.append(f"best_safe_fallback_mismatch:{result}")

    result, _ = _run_case(
        "evidence_selected_fallback",
        updates={},
        helper_result={"candidate_search_evidence": {"selected_candidate_updates": {"shear_links": "evidence"}}},
    )
    if result != {"shear_links": "evidence"}:
        failures.append(f"evidence_selected_fallback_mismatch:{result}")

    result, _ = _run_case(
        "helper_exception_returns_empty",
        updates={},
        helper_result="raise",
    )
    if result != {}:
        failures.append(f"exception_result_mismatch:{result}")

    payload = {
        "verifier": "inputs_page_pre_presentation_same_click_shear_updates_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Pre Presentation Same Click Shear Updates Verifier",
                "",
                f"Status: `{payload['status']}`",
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
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
