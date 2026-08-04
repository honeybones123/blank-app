"""Verify geometry trial selector extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "geometry_trial_selector.py"
ARTIFACTS = ROOT / "artifacts" / "verification"
AUDITS = ROOT / "artifacts" / "audits"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _function_node(source: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def _bind_metric_reader(
    *,
    crack: dict | None = None,
    deflection: dict | None = None,
    shear: dict | None = None,
    bending: dict | None = None,
    overview: dict | None = None,
    overview_raises: bool = False,
) -> dict[str, Any]:
    from inputs_page_modules.design_guide import geometry_trial_selector as extracted

    calls: dict[str, Any] = {
        "crack": [],
        "deflection": [],
        "shear": [],
        "bending": [],
        "overview": [],
    }

    def _parse_util_value(value: Any) -> float | None:
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    def _crack(state: dict) -> dict | None:
        calls["crack"].append(dict(state or {}))
        return crack

    def _deflection(state: dict) -> dict | None:
        calls["deflection"].append(dict(state or {}))
        return deflection

    def _shear(state: dict) -> dict | None:
        calls["shear"].append(dict(state or {}))
        return shear

    def _bending(state: dict) -> dict | None:
        calls["bending"].append(dict(state or {}))
        return bending

    def _overview(state: dict) -> dict:
        calls["overview"].append(dict(state or {}))
        if overview_raises:
            raise RuntimeError("overview unavailable")
        return dict(overview or {})

    extracted.bind_geometry_trial_selector_dependencies(
        {
            "_parse_util_value": _parse_util_value,
            "_evaluate_crack_with_state": _crack,
            "_evaluate_deflection_with_state": _deflection,
            "_evaluate_shear_with_state": _shear,
            "_evaluate_bending_with_bottom_state": _bending,
            "_collect_design_overview": _overview,
        }
    )
    return {"module": extracted, "calls": calls}


def _metric_reader_cases() -> list[dict[str, Any]]:
    state = {"D": 600}

    crack_case = _bind_metric_reader(crack={"util": "1.23"})
    crack_result = crack_case["module"]._read_metric_for_geometry_trial(state, metric="crack")

    deflection_case = _bind_metric_reader(deflection={"util": "0.87"})
    deflection_result = deflection_case["module"]._read_metric_for_geometry_trial(state, metric="deflection")

    shear_case = _bind_metric_reader(shear={"web_util": "1.11", "util": "9.99"})
    shear_result = shear_case["module"]._read_metric_for_geometry_trial(state, metric="shear")

    bending_direct = _bind_metric_reader(bending={"summary_util": "0.76"})
    bending_direct_result = bending_direct["module"]._read_metric_for_geometry_trial(state, metric="bending")

    ductility = _bind_metric_reader(
        overview={
            "packs": {
                "bending": {
                    "rows": [
                        {"uid": "strength", "title": "Strength", "util": "0.4"},
                        {"uid": "ductility", "title": "Ductility", "util": "0.66"},
                    ]
                }
            },
            "utils": {"bending": "0.88"},
        }
    )
    ductility_result = ductility["module"]._read_metric_for_geometry_trial(
        state,
        metric="bending",
        bending_mode="ductility",
    )

    bending_utils_fallback = _bind_metric_reader(
        bending={"summary_util": None},
        overview={"utils": {"bending": "0.91"}},
    )
    bending_utils_fallback_result = bending_utils_fallback["module"]._read_metric_for_geometry_trial(state, metric="bending")

    bending_pos = _bind_metric_reader(
        bending={"summary_util": None},
        overview={"packs": {"bending": {"bending_pos": {"util": "0.72"}}}},
    )
    bending_pos_result = bending_pos["module"]._read_metric_for_geometry_trial(
        state,
        metric="bending",
        bending_mode="positive",
    )

    shear_direct_none = _bind_metric_reader(
        shear=None,
        overview={"packs": {"shear": {"summary_governing_util": "0.83", "summary_util": "0.99"}}},
    )
    shear_direct_none_result = shear_direct_none["module"]._read_metric_for_geometry_trial(state, metric="shear")

    overview_exception = _bind_metric_reader(crack=None, overview_raises=True)
    overview_exception_result = overview_exception["module"]._read_metric_for_geometry_trial(state, metric="crack")

    return [
        {"name": "crack_direct_util", "passed": crack_result == 1.23, "calls": crack_case["calls"]},
        {"name": "deflection_direct_util", "passed": deflection_result == 0.87, "calls": deflection_case["calls"]},
        {"name": "shear_prefers_web_util", "passed": shear_result == 1.11, "calls": shear_case["calls"]},
        {"name": "bending_direct_summary_util", "passed": bending_direct_result == 0.76, "calls": bending_direct["calls"]},
        {"name": "bending_ductility_row", "passed": ductility_result == 0.66, "calls": ductility["calls"]},
        {"name": "bending_utils_fallback", "passed": bending_utils_fallback_result == 0.91, "calls": bending_utils_fallback["calls"]},
        {"name": "bending_positive_pack_fallback", "passed": bending_pos_result == 0.72, "calls": bending_pos["calls"]},
        {
            "name": "shear_direct_none_preserves_no_fallback",
            "passed": shear_direct_none_result is None and not shear_direct_none["calls"]["overview"],
            "calls": shear_direct_none["calls"],
        },
        {"name": "overview_exception_returns_none", "passed": overview_exception_result is None, "calls": overview_exception["calls"]},
    ]


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")

    bridge_node = _function_node(bridge_source, "_choose_geometry_trial_for_metric")
    bridge_metric_node = _function_node(bridge_source, "_read_metric_for_geometry_trial")
    module_node = _function_node(module_source, "_choose_geometry_trial_for_metric")
    module_metric_node = _function_node(module_source, "_read_metric_for_geometry_trial")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    bridge_metric_body = ast.get_source_segment(bridge_source, bridge_metric_node) or ""
    dependency_block = module_source.split("def bind_geometry_trial_selector_dependencies", 1)[0]
    metric_cases = _metric_reader_cases()

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 16,
        "bridge_metric_wrapper_is_small": (bridge_metric_node.end_lineno or bridge_metric_node.lineno) - bridge_metric_node.lineno + 1 <= 12,
        "bridge_binds_dependencies": "_bind_geometry_trial_selector_dependencies(globals())" in bridge_body,
        "bridge_metric_binds_dependencies": "_bind_geometry_trial_selector_dependencies(globals())" in bridge_metric_body,
        "bridge_delegates_to_extracted_module": "_choose_geometry_trial_for_metric_extracted" in bridge_body,
        "bridge_metric_delegates_to_extracted_module": "_read_metric_for_geometry_trial_extracted" in bridge_metric_body,
        "bridge_removed_metric_reader_body": "Read an existing overview metric" not in bridge_metric_body
        and "_collect_design_overview" not in bridge_metric_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 190,
        "module_contains_metric_reader_body": (module_metric_node.end_lineno or module_metric_node.lineno) - module_metric_node.lineno + 1 >= 60,
        "module_has_dependency_binder": "def bind_geometry_trial_selector_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "dependency_binder_excludes_nested_read_metric": '"read_metric"' not in dependency_block,
        "dependency_binder_does_not_inject_metric_reader": '"_read_metric_for_geometry_trial"' not in dependency_block,
        "dependency_binder_includes_metric_reader_dependencies": all(
            token in dependency_block
            for token in (
                '"_collect_design_overview"',
                '"_evaluate_bending_with_bottom_state"',
                '"_evaluate_crack_with_state"',
                '"_evaluate_deflection_with_state"',
                '"_evaluate_shear_with_state"',
                '"_parse_util_value"',
            )
        ),
        "module_keeps_debug_session_surface": (
            "st.session_state[DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY]" in module_source
            and "correction_candidate_considered" in module_source
            and "best_scored_trial" in module_source
        ),
        "module_keeps_metric_reader_surface": all(
            token in module_source
            for token in (
                "Read an existing overview metric for geometry-trial ranking.",
                "_evaluate_crack_with_state",
                "_evaluate_deflection_with_state",
                "_evaluate_shear_with_state",
                "_evaluate_bending_with_bottom_state",
                "summary_governing_util",
                "summary_util_total",
            )
        ),
        "all_metric_reader_cases_pass": all(row["passed"] for row in metric_cases),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import geometry_trial_selector as extracted

    original = bridge._choose_geometry_trial_for_metric_extracted
    original_metric = bridge._read_metric_for_geometry_trial_extracted
    module_metric_owner = extracted._read_metric_for_geometry_trial
    call_record: dict = {}
    metric_call_record: dict = {}

    def _fake_extracted(
        state: dict,
        *,
        metric: str,
        baseline_util: float | None = None,
        bending_mode: str = "governing",
        ladder_name: str = "geometry_trial",
    ) -> dict | None:
        call_record.update(
            {
                "state": dict(state),
                "metric": metric,
                "baseline_util": baseline_util,
                "bending_mode": bending_mode,
                "ladder_name": ladder_name,
                "bound_st": getattr(extracted, "st", None) is bridge.st,
                "bound_debug_key": (
                    getattr(extracted, "DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY", None)
                    == bridge.DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY
                ),
                "bound_read_metric": (
                    getattr(extracted, "_read_metric_for_geometry_trial", None)
                    is module_metric_owner
                ),
                "bound_guidance_updates": (
                    getattr(extracted, "_guidance_action_updates", None)
                    is bridge._guidance_action_updates
                ),
            }
        )
        return {"label": "fake geometry"}

    def _fake_metric(
        state: dict,
        *,
        metric: str,
        bending_mode: str = "governing",
    ) -> float:
        metric_call_record.update(
            {
                "state": dict(state),
                "metric": metric,
                "bending_mode": bending_mode,
                "bound_crack": getattr(extracted, "_evaluate_crack_with_state", None)
                is bridge._evaluate_crack_with_state,
                "bound_bending": getattr(extracted, "_evaluate_bending_with_bottom_state", None)
                is bridge._evaluate_bending_with_bottom_state,
                "metric_module_owner": extracted._read_metric_for_geometry_trial is module_metric_owner,
            }
        )
        return 0.42

    try:
        bridge._choose_geometry_trial_for_metric_extracted = _fake_extracted
        bridge._read_metric_for_geometry_trial_extracted = _fake_metric
        returned = bridge._choose_geometry_trial_for_metric(
            {"D": 600},
            metric="bending",
            baseline_util=1.25,
            bending_mode="governing",
            ladder_name="geometry_trial_test",
        )
        metric_returned = bridge._read_metric_for_geometry_trial(
            {"D": 600},
            metric="crack",
            bending_mode="ductility",
        )
    finally:
        bridge._choose_geometry_trial_for_metric_extracted = original
        bridge._read_metric_for_geometry_trial_extracted = original_metric

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "st", None) is bridge.st
        and getattr(extracted, "DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY", None)
        == bridge.DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY
        and getattr(extracted, "_geometry_width_depth_trial_specs", None)
        is bridge._geometry_width_depth_trial_specs
        and getattr(extracted, "_log_guidance_ladder_debug", None)
        is bridge._log_guidance_ladder_debug
        and getattr(extracted, "_evaluate_crack_with_state", None)
        is bridge._evaluate_crack_with_state
        and getattr(extracted, "_parse_util_value", None)
        is bridge._parse_util_value
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"label": "fake geometry"}
        and call_record.get("state") == {"D": 600}
        and call_record.get("metric") == "bending"
        and call_record.get("baseline_util") == 1.25
        and call_record.get("bending_mode") == "governing"
        and call_record.get("ladder_name") == "geometry_trial_test"
        and call_record.get("bound_st") is True
        and call_record.get("bound_debug_key") is True
        and call_record.get("bound_read_metric") is True
        and call_record.get("bound_guidance_updates") is True
    )
    checks["bridge_metric_runtime_delegates_with_arguments"] = (
        metric_returned == 0.42
        and metric_call_record.get("state") == {"D": 600}
        and metric_call_record.get("metric") == "crack"
        and metric_call_record.get("bending_mode") == "ductility"
        and metric_call_record.get("bound_crack") is True
        and metric_call_record.get("bound_bending") is True
        and metric_call_record.get("metric_module_owner") is True
    )

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "metric_reader_case_results": metric_cases,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "bridge_metric_wrapper_lines": (bridge_metric_node.end_lineno or bridge_metric_node.lineno) - bridge_metric_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
        "module_metric_function_lines": (module_metric_node.end_lineno or module_metric_node.lineno) - module_metric_node.lineno + 1,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_geometry_trial_selector_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_geometry_trial_selector_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Geometry Trial Selector Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Bridge metric wrapper lines: {result['bridge_metric_wrapper_lines']}",
                f"- Extracted module function lines: {result['module_function_lines']}",
                f"- Extracted metric function lines: {result['module_metric_function_lines']}",
                "",
                "## Checks",
                "",
                *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(result["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
