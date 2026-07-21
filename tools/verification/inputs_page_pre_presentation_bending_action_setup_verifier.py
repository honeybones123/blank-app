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
    json_path = ARTIFACT_DIR / f"inputs_page_pre_presentation_bending_action_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_pre_presentation_bending_action_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_parse_util_value": inputs_page._parse_util_value,
        "_float_from_state": inputs_page._float_from_state,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _parse(value):
        if value is None:
            return None
        return float(value)

    def _float_from_state(state, key, default=0.0):
        return state.get(key, default)

    def _run_case(name: str, *, primary: dict, evidence: dict, utils: dict, state: dict, debug: dict):
        try:
            inputs_page._parse_util_value = _parse
            inputs_page._float_from_state = _float_from_state
            result = inputs_page.render_design_guide_pre_presentation_bending_action_setup(
                pre_presentation_primary=dict(primary),
                pre_presentation_evidence=dict(evidence),
                pre_presentation_utils=dict(utils),
                guidance_disp_state=dict(state),
                guidance_debug=dict(debug),
            )
        finally:
            _restore()
        cases.append({"name": name, "result": result})
        return result

    result = _run_case(
        "target_band_candidate_preferred",
        primary={"title_main": "Primary", "candidate_search_evidence": {"x": 1}},
        evidence={
            "target_band_candidate_count": 2,
            "best_target_band_candidate_id": "target-1",
            "selected_candidate_id": "selected-1",
        },
        utils={"shear": 0.72},
        state={"uls_Vstar": -12.5, "load_Vstar_proxy": 8.0},
        debug={"materially_overprovided_families": ["Shear"], "selected_family_id": "BENDING"},
    )
    (
        item,
        candidate_id,
        family,
        subfamilies,
        title,
        shear_util,
        material_families,
        selected_family,
        combined_expected,
        shear_demand,
    ) = result
    if item != {"title_main": "Primary", "candidate_search_evidence": {"x": 1}}:
        failures.append(f"target_item_copy_mismatch:{item}")
    if candidate_id != "target-1":
        failures.append(f"target_candidate_id_mismatch:{candidate_id}")
    if family != "bending" or subfamilies != ["bottom_reinforcement"]:
        failures.append(f"target_family_defaults_mismatch:{family}:{subfamilies}")
    if title != "Bending cleanup - further reduction reaches target range":
        failures.append(f"target_title_mismatch:{title}")
    if shear_util != 0.72:
        failures.append(f"target_shear_util_mismatch:{shear_util}")
    if material_families != {"shear"}:
        failures.append(f"target_material_families_mismatch:{material_families}")
    if selected_family != "BENDING":
        failures.append(f"target_selected_family_mismatch:{selected_family}")
    if combined_expected is not True:
        failures.append(f"target_combined_expected_mismatch:{combined_expected}")
    if shear_demand != 12.5:
        failures.append(f"target_shear_demand_mismatch:{shear_demand}")

    result = _run_case(
        "selected_candidate_fallback_combined_family",
        primary={},
        evidence={"selected_candidate_id": "selected-2"},
        utils={"shear": None},
        state={"uls_Vstar": 0.0, "load_Vstar_proxy": 15.0},
        debug={"published_family_id": "combined_overdesign_governs"},
    )
    if result[1] != "selected-2":
        failures.append(f"selected_candidate_fallback_mismatch:{result[1]}")
    if result[4] != "Bending cleanup - best safe one-click reduction":
        failures.append(f"selected_title_mismatch:{result[4]}")
    if result[5] is not None:
        failures.append(f"selected_shear_util_mismatch:{result[5]}")
    if result[8] is not True:
        failures.append(f"selected_combined_expected_mismatch:{result[8]}")
    if result[9] != 15.0:
        failures.append(f"selected_shear_demand_mismatch:{result[9]}")

    result = _run_case(
        "default_candidate_id_no_combined_context",
        primary={},
        evidence={},
        utils={},
        state={},
        debug={"materially_overprovided_families": ["bending"]},
    )
    if result[1] != "bending_only_cleanup_candidate":
        failures.append(f"default_candidate_id_mismatch:{result[1]}")
    if result[6] != {"bending"}:
        failures.append(f"default_material_family_mismatch:{result[6]}")
    if result[8] is not False:
        failures.append(f"default_combined_expected_mismatch:{result[8]}")
    if result[9] != 0.0:
        failures.append(f"default_shear_demand_mismatch:{result[9]}")

    payload = {
        "verifier": "inputs_page_pre_presentation_bending_action_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Pre Presentation Bending Action Setup Verifier",
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
