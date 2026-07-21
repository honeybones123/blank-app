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
    json_path = ARTIFACT_DIR / f"inputs_page_terminal_overprovided_family_cleanup_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_terminal_overprovided_family_cleanup_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "identify_materially_overprovided_non_governing_families": inputs_page.identify_materially_overprovided_non_governing_families,
        "_parse_util_value": inputs_page._parse_util_value,
        "_overview_required_checks_acceptable": inputs_page._overview_required_checks_acceptable,
        "FINAL_ACCEPTED_MIN_FAMILY_UTIL": inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _run_case(
        name: str,
        *,
        overview: dict,
        family_utils: dict,
        material_families: list[str],
        governing_family: str | None,
        required_ok: bool,
    ) -> tuple[dict, list, object, object, bool]:
        stages: list[str] = []
        traces: list[dict[str, Any]] = []
        parse_inputs: list[Any] = []

        def _identify(overview_arg):
            return dict(family_utils), list(material_families), governing_family

        def _parse(value):
            parse_inputs.append(value)
            if value is None:
                return None
            return float(value)

        def _stage(label):
            stages.append(label)

        def _trace(label, **payload):
            traces.append({"label": label, **payload})

        try:
            inputs_page.identify_materially_overprovided_non_governing_families = _identify
            inputs_page._parse_util_value = _parse
            inputs_page._overview_required_checks_acceptable = lambda ov: bool(required_ok)
            inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85
            result = inputs_page.render_design_guide_terminal_overprovided_family_cleanup_setup(
                dg_overview=dict(overview),
                stage=_stage,
                trace=_trace,
            )
        finally:
            _restore()
        cases.append(
            {
                "name": name,
                "stages": stages,
                "traces": traces,
                "parse_inputs": parse_inputs,
                "result": result,
            }
        )
        return result

    shear_contract = _run_case(
        "shear_contract_cleanup_detected",
        overview={"utils": {"shear": 0.2}, "any_fail": False},
        family_utils={"shear": 0.2},
        material_families=[],
        governing_family="shear",
        required_ok=True,
    )
    if shear_contract != ({"shear": 0.2}, [], "shear", 0.2, True):
        failures.append(f"shear_contract_result_mismatch:{shear_contract}")
    if cases[-1]["stages"] != [
        "post_plan.before_identify_overprovided_families",
        "post_plan.after_identify_overprovided_families",
    ]:
        failures.append(f"shear_contract_stage_order_mismatch:{cases[-1]['stages']}")
    trace_payload = cases[-1]["traces"][0] if cases[-1]["traces"] else {}
    if trace_payload.get("material_family_count") != 0 or trace_payload.get("governing_family") != "shear":
        failures.append(f"shear_contract_trace_mismatch:{trace_payload}")

    material = _run_case(
        "material_families_preserved",
        overview={"utils": {"shear": 1.1}, "any_fail": False},
        family_utils={"bending": 0.3, "shear": 1.1},
        material_families=["bending"],
        governing_family="bending",
        required_ok=True,
    )
    if material != ({"bending": 0.3, "shear": 1.1}, ["bending"], "bending", 1.1, False):
        failures.append(f"material_result_mismatch:{material}")
    trace_payload = cases[-1]["traces"][0] if cases[-1]["traces"] else {}
    if trace_payload.get("material_families") != ["bending"]:
        failures.append(f"material_trace_mismatch:{trace_payload}")

    failed_overview = _run_case(
        "failed_overview_suppresses_shear_contract",
        overview={"utils": {"shear": 0.2}, "any_fail": True},
        family_utils={"shear": 0.2},
        material_families=[],
        governing_family="shear",
        required_ok=True,
    )
    if failed_overview[4] is not False:
        failures.append(f"failed_overview_contract_not_suppressed:{failed_overview}")

    required_not_ok = _run_case(
        "required_checks_not_ok_suppresses_shear_contract",
        overview={"utils": {"shear": 0.2}, "any_fail": False},
        family_utils={"shear": 0.2},
        material_families=[],
        governing_family="shear",
        required_ok=False,
    )
    if required_not_ok[4] is not False:
        failures.append(f"required_not_ok_contract_not_suppressed:{required_not_ok}")

    payload = {
        "verifier": "inputs_page_terminal_overprovided_family_cleanup_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": [
            {
                "name": case["name"],
                "stages": case["stages"],
                "traces": case["traces"],
                "parse_inputs": case["parse_inputs"],
            }
            for case in cases
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Terminal Overprovided Family Cleanup Setup Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}` stages={case['stages']}" for case in cases),
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
