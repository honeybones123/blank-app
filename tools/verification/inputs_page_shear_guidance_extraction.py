"""Verify shear guidance item extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "shear_guidance.py"
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


def _bind_helper_module(
    *,
    geometry_trial: dict | None = None,
    depth_updates: dict | None = None,
    updates_match: bool = False,
) -> dict[str, Any]:
    from inputs_page_modules.design_guide import shear_guidance as extracted

    calls: dict[str, Any] = {"items": [], "emits": [], "trials": [], "actions": []}

    def _choose(state: dict, **kwargs: Any) -> dict | None:
        calls["trials"].append({"state": dict(state), **kwargs})
        return geometry_trial

    def _title(base_title: str, g: dict, state: dict) -> str:
        return f"{base_title} via {g.get('label')}"

    def _change_lines(state: dict, updates: dict) -> list[str]:
        return [f"{key} -> {value}" for key, value in sorted(dict(updates or {}).items())]

    def _guidance_item(*args: Any, **kwargs: Any) -> dict:
        item = {"args": list(args), "kwargs": dict(kwargs)}
        calls["items"].append(item)
        return item

    def _action_updates(action_type: str, payload: dict, *, state: dict | None = None) -> dict | None:
        calls["actions"].append({"action_type": action_type, "payload": dict(payload), "state": dict(state or {})})
        return None if depth_updates is None else dict(depth_updates)

    def _updates_match_state(state: dict, updates: dict) -> bool:
        return bool(updates_match)

    def _emit(item: dict, **kwargs: Any) -> dict:
        calls["emits"].append({"item": item, **kwargs})
        return {"emitted": item, **kwargs}

    extracted.bind_shear_guidance_dependencies(
        {
            "_choose_geometry_trial_for_metric": _choose,
            "_geometry_trial_title_for_choice": _title,
            "_guidance_action_updates": _action_updates,
            "_guidance_change_lines_for_updates": _change_lines,
            "_guidance_item": _guidance_item,
            "_updates_match_state": _updates_match_state,
        }
    )
    return {"module": extracted, "calls": calls, "emit": _emit}


def _helper_cases() -> list[dict[str, Any]]:
    state = {"D": 600}
    geometry = _bind_helper_module(
        geometry_trial={
            "label": "Increase depth D by 50 mm",
            "updates": {"D": 650},
            "util_after": 0.72,
            "payload": {"delta_mm": 50.0},
            "action_type": "increase_depth",
            "before_after": "D 600 -> 650",
        }
    )
    geometry_result = geometry["module"]._shear_item_from_geometry_trials(
        state,
        title="Shear governs",
        status="FAIL",
        util=1.2,
        secondary="secondary",
        reasoning_fallback="fallback",
        levers="levers",
        default_depth_delta=100.0,
        branch="fail:depth",
        _emit=geometry["emit"],
    )
    fallback = _bind_helper_module(depth_updates={"D": 700})
    fallback_result = fallback["module"]._shear_item_from_geometry_trials(
        state,
        title="Shear governs",
        status="FAIL",
        util=1.2,
        secondary="secondary",
        reasoning_fallback="fallback",
        levers="levers",
        default_depth_delta=100.0,
        branch="fail:depth",
        _emit=fallback["emit"],
    )
    null_util = _bind_helper_module(geometry_trial={"label": "unused"})
    null_result = null_util["module"]._shear_item_from_geometry_trials(
        state,
        title="Shear governs",
        status="FAIL",
        util=None,
        secondary="secondary",
        reasoning_fallback="fallback",
        levers="levers",
        default_depth_delta=100.0,
        branch="fail:depth",
        _emit=null_util["emit"],
    )
    no_fallback = _bind_helper_module(depth_updates={"D": 600}, updates_match=True)
    no_fallback_result = no_fallback["module"]._shear_item_from_geometry_trials(
        state,
        title="Shear governs",
        status="FAIL",
        util=1.2,
        secondary="secondary",
        reasoning_fallback="fallback",
        levers="levers",
        default_depth_delta=100.0,
        branch="fail:depth",
        _emit=no_fallback["emit"],
    )
    return [
        {
            "name": "geometry_trial_path_emits_expected_contract",
            "passed": geometry_result.get("branch") == "fail:depth"
            and geometry_result.get("proposed_updates") == {"D": 650}
            and geometry_result.get("expected_util_after") == 0.72
            and geometry["calls"]["items"][0]["args"][:4] == [
                "shear",
                "Shear governs via Increase depth D by 50 mm",
                "Increase depth D by 50 mm",
                "secondary",
            ]
            and "shear utilisation 1.20" in geometry["calls"]["items"][0]["args"][4]
            and geometry["calls"]["items"][0]["kwargs"].get("guidance_change_lines") == ["D -> 650"],
            "result": geometry_result,
        },
        {
            "name": "depth_fallback_heuristic_emits_expected_contract",
            "passed": fallback_result.get("branch") == "fail:depth:depth_fallback_heuristic"
            and fallback_result.get("proposed_updates") == {"D": 700}
            and fallback["calls"]["items"][0]["args"][2] == "Increase depth D by ~100 mm"
            and fallback["calls"]["items"][0]["args"][7] == {"delta_mm": 100.0},
            "result": fallback_result,
        },
        {
            "name": "null_util_returns_none_without_side_effects",
            "passed": null_result is None and not null_util["calls"]["trials"] and not null_util["calls"]["items"],
        },
        {
            "name": "matching_depth_fallback_returns_none",
            "passed": no_fallback_result is None and no_fallback["calls"]["actions"],
        },
    ]


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")

    bridge_node = _function_node(bridge_source, "_shear_guidance_item")
    bridge_helper_node = _function_node(bridge_source, "_shear_item_from_geometry_trials")
    module_node = _function_node(module_source, "_shear_guidance_item")
    module_helper_node = _function_node(module_source, "_shear_item_from_geometry_trials")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    bridge_helper_body = ast.get_source_segment(bridge_source, bridge_helper_node) or ""
    dependency_block = module_source.split("def bind_shear_guidance_dependencies", 1)[0]
    helper_cases = _helper_cases()

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 4,
        "bridge_helper_wrapper_is_small": (bridge_helper_node.end_lineno or bridge_helper_node.lineno) - bridge_helper_node.lineno + 1 <= 26,
        "bridge_binds_dependencies": "_bind_shear_guidance_dependencies(globals())" in bridge_body,
        "bridge_helper_binds_dependencies": "_bind_shear_guidance_dependencies(globals())" in bridge_helper_body,
        "bridge_delegates_to_extracted_module": "_shear_guidance_item_extracted" in bridge_body,
        "bridge_helper_delegates_to_extracted_module": "_shear_item_from_geometry_trials_extracted" in bridge_helper_body,
        "bridge_removed_helper_body": "width/depth trial chooser picked" not in bridge_helper_body
        and "_guidance_change_lines_for_updates" not in bridge_helper_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 > 190,
        "module_contains_helper_body": (module_helper_node.end_lineno or module_helper_node.lineno) - module_helper_node.lineno + 1 >= 60,
        "module_has_dependency_binder": "def bind_shear_guidance_dependencies" in module_source,
        "module_does_not_bind_nested_false_positives": all(
            name not in dependency_block
            for name in (
                '"_emit"',
                '"branch"',
                '"expected_util_after"',
                '"proposed_updates"',
                '"search_label"',
            )
        ),
        "module_does_not_import_streamlit": "streamlit" not in module_source and "import st" not in module_source,
        "module_does_not_read_session_state": ".session_state" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_owns_helper": '"_shear_item_from_geometry_trials"' not in dependency_block,
        "module_binds_helper_dependencies": all(
            token in dependency_block
            for token in (
                '"_choose_geometry_trial_for_metric"',
                '"_geometry_trial_title_for_choice"',
                '"_guidance_action_updates"',
                '"_guidance_change_lines_for_updates"',
            )
        ),
        "module_keeps_helper_contract_surface": all(
            token in module_source
            for token in (
                "shear_geometry_trials",
                "width/depth trial chooser picked",
                "shear utilisation",
                "guidance_change_lines",
                "depth_fallback_heuristic",
            )
        ),
        "all_helper_cases_pass": all(row["passed"] for row in helper_cases),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import shear_guidance as extracted

    sentinel = {"sentinel": "shear_guidance"}
    original = bridge._shear_guidance_item_extracted
    original_helper = bridge._shear_item_from_geometry_trials_extracted
    helper_call_record: dict[str, Any] = {}

    def _fake_extracted(state: dict, pack: dict) -> dict:
        return {
            "result": dict(sentinel),
            "state": dict(state),
            "pack": dict(pack),
            "bound_guidance_item": getattr(extracted, "_guidance_item", None) is bridge._guidance_item,
        }

    def _fake_helper(state: dict, **kwargs: Any) -> dict:
        helper_call_record.update(
            {
                "state": dict(state),
                **kwargs,
                "bound_guidance_item": getattr(extracted, "_guidance_item", None) is bridge._guidance_item,
                "bound_choose": getattr(extracted, "_choose_geometry_trial_for_metric", None)
                is bridge._choose_geometry_trial_for_metric,
            }
        )
        return {"helper": True}

    try:
        bridge._shear_guidance_item_extracted = _fake_extracted
        bridge._shear_item_from_geometry_trials_extracted = _fake_helper
        wrapped = bridge._shear_guidance_item({"D": 600}, {"summary_governing_util": 0.8})
        helper_wrapped = bridge._shear_item_from_geometry_trials(
            {"D": 600},
            title="Shear governs",
            status="FAIL",
            util=1.2,
            secondary="secondary",
            reasoning_fallback="fallback",
            levers="levers",
            default_depth_delta=100.0,
            branch="fail",
            _emit=lambda item, **kwargs: item,
        )
    finally:
        bridge._shear_guidance_item_extracted = original
        bridge._shear_item_from_geometry_trials_extracted = original_helper

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_guidance_item", None) is bridge._guidance_item
        and getattr(extracted, "_compute_shear_recommendation", None)
        is bridge._compute_shear_recommendation
        and getattr(extracted, "_choose_geometry_trial_for_metric", None)
        is bridge._choose_geometry_trial_for_metric
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        wrapped.get("result") == sentinel
        and wrapped.get("state") == {"D": 600}
        and wrapped.get("pack") == {"summary_governing_util": 0.8}
        and wrapped.get("bound_guidance_item") is True
    )
    checks["bridge_helper_runtime_delegates_with_arguments"] = (
        helper_wrapped == {"helper": True}
        and helper_call_record.get("state") == {"D": 600}
        and helper_call_record.get("title") == "Shear governs"
        and helper_call_record.get("status") == "FAIL"
        and helper_call_record.get("util") == 1.2
        and helper_call_record.get("default_depth_delta") == 100.0
        and helper_call_record.get("bound_guidance_item") is True
        and helper_call_record.get("bound_choose") is True
    )

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "helper_case_results": helper_cases,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "bridge_helper_wrapper_lines": (bridge_helper_node.end_lineno or bridge_helper_node.lineno) - bridge_helper_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
        "module_helper_function_lines": (module_helper_node.end_lineno or module_helper_node.lineno) - module_helper_node.lineno + 1,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_shear_guidance_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_shear_guidance_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Shear Guidance Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Bridge helper wrapper lines: {result['bridge_helper_wrapper_lines']}",
                f"- Extracted module function lines: {result['module_function_lines']}",
                f"- Extracted helper function lines: {result['module_helper_function_lines']}",
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
