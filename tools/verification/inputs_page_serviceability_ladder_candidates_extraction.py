"""Verify serviceability ladder candidate extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "serviceability_ladder_candidates.py"
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


def _bind_module(*, crack_util: float | None = 0.8, deflection_util: float | None = 0.8, noop: bool = False) -> dict[str, Any]:
    from inputs_page_modules.design_guide import serviceability_ladder_candidates as extracted

    calls: dict[str, Any] = {
        "logs": [],
        "merged": [],
        "crack_eval": [],
        "deflection_eval": [],
        "action_updates": [],
        "descriptions": [],
    }

    def _log(ladder_name: str, **kwargs: Any) -> None:
        calls["logs"].append({"ladder_name": ladder_name, **kwargs})

    def _updates_match_state(state: dict, updates: dict) -> bool:
        return bool(noop)

    def _merge(state: dict, updates: dict) -> dict:
        merged = dict(state)
        merged.update(dict(updates or {}))
        calls["merged"].append(merged)
        return merged

    def _eval_crack(state: dict) -> dict | None:
        calls["crack_eval"].append(dict(state))
        return None if crack_util is None else {"util": crack_util}

    def _eval_deflection(state: dict) -> dict | None:
        calls["deflection_eval"].append(dict(state))
        return None if deflection_util is None else {"util": deflection_util}

    def _guidance_action_updates(action_type: str, payload: dict, *, state: dict | None = None) -> dict:
        calls["action_updates"].append({"action_type": action_type, "payload": dict(payload), "state": dict(state or {})})
        delta = float(payload.get("delta_mm", 0.0) or 0.0)
        if action_type == "increase_depth":
            return {"D": float((state or {}).get("D", 0.0) or 0.0) + delta}
        if action_type == "increase_width":
            return {"b": float((state or {}).get("b", 0.0) or 0.0) + delta}
        return {}

    def _describe_guidance_step(state: dict, next_state: dict, action_type: str, updates: dict | None) -> dict:
        description = {
            "action_type": action_type,
            "updates": dict(updates or {}),
            "next_state": dict(next_state or {}),
        }
        calls["descriptions"].append(description)
        return description

    def _float_from_state(state: dict, key: str, default: float = 0.0) -> float:
        return float(state.get(key, default) or default)

    extracted.bind_serviceability_ladder_candidate_dependencies(
        {
            "GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM": (25, 50),
            "GUIDANCE_LADDER_EARLY_STOP_UTIL": 0.85,
            "_describe_guidance_step": _describe_guidance_step,
            "_evaluate_crack_with_state": _eval_crack,
            "_evaluate_deflection_with_state": _eval_deflection,
            "_float_from_state": _float_from_state,
            "_guidance_action_updates": _guidance_action_updates,
            "_log_guidance_ladder_debug": _log,
            "_merge_guidance_state": _merge,
            "_updates_match_state": _updates_match_state,
        }
    )
    return {"module": extracted, "calls": calls}


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")
    bridge_crack_node = _function_node(bridge_source, "_try_crack_ladder_candidate")
    bridge_deflection_node = _function_node(bridge_source, "_try_deflection_ladder_candidate")
    bridge_picker_node = _function_node(bridge_source, "_pick_deflection_ladder_first_improvement")
    module_crack_node = _function_node(module_source, "_try_crack_ladder_candidate")
    module_deflection_node = _function_node(module_source, "_try_deflection_ladder_candidate")
    module_picker_node = _function_node(module_source, "_pick_deflection_ladder_first_improvement")
    module_sustained_node = _function_node(module_source, "_deflection_ladder_sustained_load_updates")
    bridge_crack_body = ast.get_source_segment(bridge_source, bridge_crack_node) or ""
    bridge_deflection_body = ast.get_source_segment(bridge_source, bridge_deflection_node) or ""
    bridge_picker_body = ast.get_source_segment(bridge_source, bridge_picker_node) or ""
    dependency_section = module_source.partition("def bind_serviceability_ladder_candidate_dependencies")[0]

    empty = _bind_module()
    empty_result = empty["module"]._try_crack_ladder_candidate(
        {"D": 600},
        label="empty",
        updates=None,
        base_util=1.2,
    )
    noop = _bind_module(noop=True)
    noop_result = noop["module"]._try_deflection_ladder_candidate(
        {"D": 600},
        label="noop",
        updates={"D": 600},
        base_util=1.2,
    )
    crack_none = _bind_module(crack_util=None)
    crack_none_result = crack_none["module"]._try_crack_ladder_candidate(
        {"D": 600},
        label="crack none",
        updates={"D": 650},
        base_util=1.2,
    )
    deflection_none = _bind_module(deflection_util=None)
    deflection_none_result = deflection_none["module"]._try_deflection_ladder_candidate(
        {"D": 600},
        label="deflection none",
        updates={"D": 650},
        base_util=1.2,
    )
    no_improve = _bind_module(crack_util=1.3)
    no_improve_result = no_improve["module"]._try_crack_ladder_candidate(
        {"D": 600},
        label="no improve",
        updates={"D": 650},
        base_util=1.2,
    )
    accepted = _bind_module(crack_util=0.8, deflection_util=0.9)
    accepted_crack = accepted["module"]._try_crack_ladder_candidate(
        {"D": 600},
        label="crack accepted",
        updates={"D": 650},
        base_util=1.2,
    )
    accepted_deflection = accepted["module"]._try_deflection_ladder_candidate(
        {"D": 600},
        label="deflection accepted",
        updates={"D": 650},
        base_util=1.2,
    )

    picker_depth = _bind_module()
    original_picker_try = picker_depth["module"]._try_deflection_ladder_candidate
    try:
        def _depth_first_try(state: dict, **kwargs: Any) -> dict | None:
            picker_depth["calls"].setdefault("picker_try", []).append({"state": dict(state), **kwargs})
            if kwargs.get("label") == "Increase depth D by 25 mm":
                return {"label": kwargs["label"], "updates": kwargs.get("updates"), "util_after": 0.7, "early_stop": True}
            return None

        picker_depth["module"]._try_deflection_ladder_candidate = _depth_first_try
        picked_depth = picker_depth["module"]._pick_deflection_ladder_first_improvement(
            {"D": 600.0, "b": 300.0, "g_kNm": 10.0},
            base_util=1.2,
        )
    finally:
        picker_depth["module"]._try_deflection_ladder_candidate = original_picker_try

    picker_width = _bind_module()
    original_picker_try = picker_width["module"]._try_deflection_ladder_candidate
    try:
        def _width_after_depth_try(state: dict, **kwargs: Any) -> dict | None:
            picker_width["calls"].setdefault("picker_try", []).append({"state": dict(state), **kwargs})
            if kwargs.get("label") == "Increase section width by 25 mm":
                return {"label": kwargs["label"], "updates": kwargs.get("updates"), "util_after": 0.8, "early_stop": True}
            return None

        picker_width["module"]._try_deflection_ladder_candidate = _width_after_depth_try
        picked_width = picker_width["module"]._pick_deflection_ladder_first_improvement(
            {"D": 600.0, "b": 300.0, "g_kNm": 10.0},
            base_util=1.2,
        )
    finally:
        picker_width["module"]._try_deflection_ladder_candidate = original_picker_try

    picker_sustained = _bind_module()
    original_picker_try = picker_sustained["module"]._try_deflection_ladder_candidate
    try:
        def _sustained_try(state: dict, **kwargs: Any) -> dict | None:
            picker_sustained["calls"].setdefault("picker_try", []).append({"state": dict(state), **kwargs})
            if kwargs.get("label") == "Reduce sustained dead load (one small step, ~8%)":
                return {"label": kwargs["label"], "updates": kwargs.get("updates"), "util_after": 0.9, "early_stop": False}
            return None

        picker_sustained["module"]._try_deflection_ladder_candidate = _sustained_try
        picked_sustained = picker_sustained["module"]._pick_deflection_ladder_first_improvement(
            {"D": 600.0, "b": 300.0, "g_kNm": 10.0},
            base_util=1.2,
        )
    finally:
        picker_sustained["module"]._try_deflection_ladder_candidate = original_picker_try

    picker_none = _bind_module()
    original_picker_try = picker_none["module"]._try_deflection_ladder_candidate
    try:
        def _never_try(state: dict, **kwargs: Any) -> dict | None:
            picker_none["calls"].setdefault("picker_try", []).append({"state": dict(state), **kwargs})
            return None

        picker_none["module"]._try_deflection_ladder_candidate = _never_try
        picked_none = picker_none["module"]._pick_deflection_ladder_first_improvement(
            {"D": 600.0, "b": 300.0},
            base_util=1.2,
        )
    finally:
        picker_none["module"]._try_deflection_ladder_candidate = original_picker_try

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import serviceability_ladder_candidates as extracted

    original_crack = bridge._try_crack_ladder_candidate_extracted
    original_deflection = bridge._try_deflection_ladder_candidate_extracted
    original_picker = bridge._pick_deflection_ladder_first_improvement_extracted
    bridge_calls: dict[str, Any] = {}

    def _fake_crack(state: dict, **kwargs: Any) -> dict:
        bridge_calls["crack"] = {
            "state": dict(state),
            **kwargs,
            "module_owner": extracted._try_crack_ladder_candidate is original_crack,
            "threshold_bound": getattr(extracted, "GUIDANCE_LADDER_EARLY_STOP_UTIL", None)
            == bridge.GUIDANCE_LADDER_EARLY_STOP_UTIL,
            "crack_eval_bound": getattr(extracted, "_evaluate_crack_with_state", None)
            is bridge._evaluate_crack_with_state,
        }
        return {"crack": True}

    def _fake_deflection(state: dict, **kwargs: Any) -> dict:
        bridge_calls["deflection"] = {
            "state": dict(state),
            **kwargs,
            "module_owner": extracted._try_deflection_ladder_candidate is original_deflection,
            "deflection_eval_bound": getattr(extracted, "_evaluate_deflection_with_state", None)
            is bridge._evaluate_deflection_with_state,
        }
        return {"deflection": True}

    def _fake_picker(state: dict, **kwargs: Any) -> dict:
        bridge_calls["picker"] = {
            "state": dict(state),
            **kwargs,
            "module_owner": extracted._pick_deflection_ladder_first_improvement is original_picker,
            "action_updates_bound": getattr(extracted, "_guidance_action_updates", None)
            is bridge._guidance_action_updates,
            "geometry_deltas_bound": getattr(extracted, "GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM", None)
            == bridge.GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM,
        }
        return {"picker": True}

    try:
        bridge._try_crack_ladder_candidate_extracted = _fake_crack
        bridge._try_deflection_ladder_candidate_extracted = _fake_deflection
        bridge._pick_deflection_ladder_first_improvement_extracted = _fake_picker
        wrapped_crack = bridge._try_crack_ladder_candidate(
            {"D": 600},
            label="wrapped crack",
            updates={"D": 650},
            base_util=1.2,
        )
        wrapped_deflection = bridge._try_deflection_ladder_candidate(
            {"D": 600},
            label="wrapped deflection",
            updates={"D": 650},
            base_util=1.2,
        )
        wrapped_picker = bridge._pick_deflection_ladder_first_improvement(
            {"D": 600},
            base_util=1.2,
        )
    finally:
        bridge._try_crack_ladder_candidate_extracted = original_crack
        bridge._try_deflection_ladder_candidate_extracted = original_deflection
        bridge._pick_deflection_ladder_first_improvement_extracted = original_picker

    checks: dict[str, bool] = {
        "bridge_crack_wrapper_is_small": (bridge_crack_node.end_lineno or bridge_crack_node.lineno)
        - bridge_crack_node.lineno
        + 1
        <= 18,
        "bridge_deflection_wrapper_is_small": (bridge_deflection_node.end_lineno or bridge_deflection_node.lineno)
        - bridge_deflection_node.lineno
        + 1
        <= 18,
        "bridge_picker_wrapper_is_small": (bridge_picker_node.end_lineno or bridge_picker_node.lineno)
        - bridge_picker_node.lineno
        + 1
        <= 4,
        "bridge_crack_binds_dependencies": "_bind_serviceability_ladder_candidate_dependencies(globals())" in bridge_crack_body,
        "bridge_deflection_binds_dependencies": "_bind_serviceability_ladder_candidate_dependencies(globals())" in bridge_deflection_body,
        "bridge_picker_binds_dependencies": "_bind_serviceability_ladder_candidate_dependencies(globals())" in bridge_picker_body,
        "bridge_crack_delegates_to_extracted_module": "_try_crack_ladder_candidate_extracted" in bridge_crack_body,
        "bridge_deflection_delegates_to_extracted_module": "_try_deflection_ladder_candidate_extracted" in bridge_deflection_body,
        "bridge_picker_delegates_to_extracted_module": "_pick_deflection_ladder_first_improvement_extracted" in bridge_picker_body,
        "module_contains_crack_body": (module_crack_node.end_lineno or module_crack_node.lineno) - module_crack_node.lineno + 1 >= 65,
        "module_contains_deflection_body": (module_deflection_node.end_lineno or module_deflection_node.lineno) - module_deflection_node.lineno + 1 >= 65,
        "module_contains_picker_body": (module_picker_node.end_lineno or module_picker_node.lineno) - module_picker_node.lineno + 1 >= 65,
        "module_contains_sustained_load_helper": (module_sustained_node.end_lineno or module_sustained_node.lineno) - module_sustained_node.lineno + 1 == 6,
        "module_has_needed_dependencies": all(
            token in dependency_section
            for token in (
                '"GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM"',
                '"GUIDANCE_LADDER_EARLY_STOP_UTIL"',
                '"_describe_guidance_step"',
                '"_evaluate_crack_with_state"',
                '"_evaluate_deflection_with_state"',
                '"_float_from_state"',
                '"_guidance_action_updates"',
                '"_log_guidance_ladder_debug"',
                '"_merge_guidance_state"',
                '"_updates_match_state"',
            )
        ),
        "empty_updates_rejected": empty_result is None and empty["calls"]["logs"][-1]["reason"] == "empty_updates",
        "noop_rejected": noop_result is None and noop["calls"]["logs"][-1]["reason"] == "noop_vs_state",
        "crack_eval_none_rejected": crack_none_result is None and crack_none["calls"]["logs"][-1]["reason"] == "crack_eval_none",
        "deflection_eval_none_rejected": deflection_none_result is None
        and deflection_none["calls"]["logs"][-1]["reason"] == "deflection_eval_none",
        "no_improvement_rejected": no_improve_result is None and no_improve["calls"]["logs"][-1]["reason"] == "no_improvement",
        "crack_accepts_improvement": accepted_crack == {
            "label": "crack accepted",
            "updates": {"D": 650},
            "util_after": 0.8,
            "early_stop": True,
        },
        "deflection_accepts_improvement": accepted_deflection == {
            "label": "deflection accepted",
            "updates": {"D": 650},
            "util_after": 0.9,
            "early_stop": False,
        },
        "picker_accepts_first_depth_improvement": picked_depth
        and picked_depth.get("kind") == "geometry"
        and picked_depth.get("action_type") == "increase_depth"
        and picked_depth.get("payload") == {"delta_mm": 25.0}
        and picked_depth.get("before_after", {}).get("action_type") == "increase_depth",
        "picker_falls_back_to_width_after_depth_trials": picked_width
        and picked_width.get("kind") == "geometry"
        and picked_width.get("action_type") == "increase_width"
        and [row["label"] for row in picker_width["calls"].get("picker_try", [])][:3]
        == ["Increase depth D by 25 mm", "Increase depth D by 50 mm", "Increase section width by 25 mm"],
        "picker_falls_back_to_sustained_load": picked_sustained
        and picked_sustained.get("kind") == "sustained_load"
        and picked_sustained.get("updates") == {"g_kNm": 9.200000000000001}
        and picked_sustained.get("before_after", {}).get("action_type") == "deflection_reduce_sustained_load",
        "picker_returns_none_without_improvement": picked_none is None,
        "bridge_runtime_delegates": wrapped_crack == {"crack": True}
        and wrapped_deflection == {"deflection": True}
        and wrapped_picker == {"picker": True},
        "bridge_runtime_binds_module_globals": bridge_calls["crack"]["threshold_bound"] is True
        and bridge_calls["crack"]["crack_eval_bound"] is True
        and bridge_calls["deflection"]["deflection_eval_bound"] is True
        and bridge_calls["picker"]["action_updates_bound"] is True
        and bridge_calls["picker"]["geometry_deltas_bound"] is True,
        "bridge_runtime_preserves_module_owner": bridge_calls["crack"]["module_owner"] is True
        and bridge_calls["deflection"]["module_owner"] is True
        and bridge_calls["picker"]["module_owner"] is True,
    }

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "bridge_crack_wrapper_lines": (bridge_crack_node.end_lineno or bridge_crack_node.lineno) - bridge_crack_node.lineno + 1,
        "bridge_deflection_wrapper_lines": (bridge_deflection_node.end_lineno or bridge_deflection_node.lineno) - bridge_deflection_node.lineno + 1,
        "bridge_picker_wrapper_lines": (bridge_picker_node.end_lineno or bridge_picker_node.lineno) - bridge_picker_node.lineno + 1,
        "module_crack_function_lines": (module_crack_node.end_lineno or module_crack_node.lineno) - module_crack_node.lineno + 1,
        "module_deflection_function_lines": (module_deflection_node.end_lineno or module_deflection_node.lineno) - module_deflection_node.lineno + 1,
        "module_picker_function_lines": (module_picker_node.end_lineno or module_picker_node.lineno) - module_picker_node.lineno + 1,
        "module_sustained_load_function_lines": (module_sustained_node.end_lineno or module_sustained_node.lineno) - module_sustained_node.lineno + 1,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_serviceability_ladder_candidates_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_serviceability_ladder_candidates_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Serviceability Ladder Candidates Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge crack wrapper lines: {result['bridge_crack_wrapper_lines']}",
                f"- Bridge deflection wrapper lines: {result['bridge_deflection_wrapper_lines']}",
                f"- Bridge picker wrapper lines: {result['bridge_picker_wrapper_lines']}",
                f"- Extracted crack function lines: {result['module_crack_function_lines']}",
                f"- Extracted deflection function lines: {result['module_deflection_function_lines']}",
                f"- Extracted picker function lines: {result['module_picker_function_lines']}",
                f"- Extracted sustained-load helper lines: {result['module_sustained_load_function_lines']}",
                "",
                "## Checks",
                "",
                *[f"- {check}: {'PASS' if passed else 'FAIL'}" for check, passed in checks.items()],
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
