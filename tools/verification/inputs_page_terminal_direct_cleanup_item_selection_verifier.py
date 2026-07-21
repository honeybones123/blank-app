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
    json_path = ARTIFACT_DIR / f"inputs_page_terminal_direct_cleanup_item_selection_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_terminal_direct_cleanup_item_selection_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_build_design_guide_shear_overdesign_contract_candidate_items": (
            inputs_page._build_design_guide_shear_overdesign_contract_candidate_items
        ),
        "_guidance_item_from_resolved_candidate": inputs_page._guidance_item_from_resolved_candidate,
        "_direct_target_band_guidance_item": inputs_page._direct_target_band_guidance_item,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _stage_recorder() -> tuple[list[str], Any]:
        stages: list[str] = []

        def _stage(label: str) -> None:
            stages.append(label)

        return stages, _stage

    stages, stage = _stage_recorder()
    debug: dict[str, Any] = {}
    builder_inputs: list[dict[str, Any]] = []
    resolved_inputs: list[dict[str, Any]] = []

    def _contract_builder(state):
        builder_inputs.append(dict(state))
        return {
            "candidates": [
                "skip",
                {
                    "candidate_search_evidence": {"selected_candidate_id": "c1"},
                    "updates": {"shear_links": "reduced"},
                },
            ]
        }

    def _resolved_item(candidate, **kwargs):
        resolved_inputs.append({"candidate": dict(candidate), "kwargs": dict(kwargs)})
        return {"title_main": kwargs.get("title"), "status": kwargs.get("status")}

    try:
        inputs_page._build_design_guide_shear_overdesign_contract_candidate_items = _contract_builder
        inputs_page._guidance_item_from_resolved_candidate = _resolved_item
        result = inputs_page.render_design_guide_terminal_direct_cleanup_item_selection(
            use_shear_overdesign_contract_cleanup=True,
            guidance_disp_state={"depth": 500},
            dg_overview={"utils": {"shear": 0.2}},
            dg_mode_cfg={"mode": "efficiency"},
            guidance_debug=debug,
            stage=stage,
        )
    finally:
        _restore()
    cases.append({"name": "shear_contract_path", "stages": stages, "debug": dict(debug), "result": result})
    if stages != [
        "post_plan.before_shear_overdesign_contract_cleanup_item",
        "post_plan.after_shear_overdesign_contract_cleanup_item",
    ]:
        failures.append(f"shear_contract_stage_order_mismatch:{stages}")
    if builder_inputs != [{"depth": 500}]:
        failures.append(f"shear_contract_builder_inputs_mismatch:{builder_inputs}")
    if not isinstance(result, dict) or result.get("source") != "shear_overdesign_contract_runtime_candidate":
        failures.append(f"shear_contract_result_source_mismatch:{result}")
    if result.get("candidate_search_evidence") != {"selected_candidate_id": "c1"}:
        failures.append(f"shear_contract_evidence_mismatch:{result}")
    if debug.get("render_stage_shear_overdesign_contract_candidate_count") != 2:
        failures.append(f"shear_contract_candidate_count_mismatch:{debug}")
    if debug.get("generic_target_band_search_skipped_reason") != "render_stage_shear_overdesign_contract_candidate_required":
        failures.append(f"shear_contract_debug_reason_mismatch:{debug}")
    resolved_kwargs = resolved_inputs[0]["kwargs"] if resolved_inputs else {}
    if resolved_kwargs.get("title") != "Shear cleanup - one-click reduction" or resolved_kwargs.get("status") != "PASS":
        failures.append(f"shear_contract_resolved_kwargs_mismatch:{resolved_kwargs}")

    stages, stage = _stage_recorder()
    debug = {}
    direct_inputs: list[dict[str, Any]] = []

    def _direct_guidance_item(state, overview, mode_cfg, *, strengthening, debug_sink):
        direct_inputs.append(
            {
                "state": dict(state),
                "overview": dict(overview),
                "mode_cfg": dict(mode_cfg),
                "strengthening": strengthening,
                "debug_sink_is_same": debug_sink is debug,
            }
        )
        debug_sink["direct_debug_touched"] = True
        return {"source": "direct_target_band", "title_main": "Direct cleanup"}

    try:
        inputs_page._direct_target_band_guidance_item = _direct_guidance_item
        result = inputs_page.render_design_guide_terminal_direct_cleanup_item_selection(
            use_shear_overdesign_contract_cleanup=False,
            guidance_disp_state={"width": 300},
            dg_overview={"utils": {"bending": 0.4}},
            dg_mode_cfg={"mode": "lean"},
            guidance_debug=debug,
            stage=stage,
        )
    finally:
        _restore()
    cases.append({"name": "direct_target_band_path", "stages": stages, "debug": dict(debug), "result": result})
    if stages != [
        "post_plan.before_direct_target_band_guidance_item",
        "post_plan.after_direct_target_band_guidance_item",
    ]:
        failures.append(f"direct_path_stage_order_mismatch:{stages}")
    expected_direct_inputs = [
        {
            "state": {"width": 300},
            "overview": {"utils": {"bending": 0.4}},
            "mode_cfg": {"mode": "lean"},
            "strengthening": False,
            "debug_sink_is_same": True,
        }
    ]
    if direct_inputs != expected_direct_inputs:
        failures.append(f"direct_path_inputs_mismatch:{direct_inputs}")
    if result != {"source": "direct_target_band", "title_main": "Direct cleanup"}:
        failures.append(f"direct_path_result_mismatch:{result}")
    if debug.get("direct_debug_touched") is not True:
        failures.append(f"direct_path_debug_sink_mismatch:{debug}")

    stages, stage = _stage_recorder()
    debug = {}

    def _raising_builder(state):
        raise RuntimeError("boom")

    try:
        inputs_page._build_design_guide_shear_overdesign_contract_candidate_items = _raising_builder
        result = inputs_page.render_design_guide_terminal_direct_cleanup_item_selection(
            use_shear_overdesign_contract_cleanup=True,
            guidance_disp_state={},
            dg_overview={},
            dg_mode_cfg={},
            guidance_debug=debug,
            stage=stage,
        )
    finally:
        _restore()
    cases.append({"name": "exception_path", "stages": stages, "debug": dict(debug), "result": result})
    if result is not None:
        failures.append(f"exception_path_result_not_none:{result}")
    if stages != [
        "post_plan.before_shear_overdesign_contract_cleanup_item",
        "post_plan.direct_target_band_guidance_item_exception",
    ]:
        failures.append(f"exception_path_stage_order_mismatch:{stages}")

    payload = {
        "verifier": "inputs_page_terminal_direct_cleanup_item_selection_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Terminal Direct Cleanup Item Selection Verifier",
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
