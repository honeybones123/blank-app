"""Verify shear candidate generation extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "app_bridge" / "shear_candidate_generation.py"
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


def _bind_escalation_module(*, geometry_locked: bool = False, active: bool = True) -> dict[str, Any]:
    from inputs_page_modules.app_bridge import shear_candidate_generation as extracted

    calls: dict[str, Any] = {"activation": [], "types": []}

    def _activation(state: dict) -> dict:
        calls["activation"].append(dict(state or {}))
        activated = dict(state or {})
        activated.setdefault("lig_d", 10)
        activated.setdefault("lig_legs", 2)
        activated.setdefault("s_lig", 200)
        return activated

    def _active(state: dict) -> bool:
        return bool(active)

    def _int(state: dict, key: str, default: int = 0) -> int:
        return int(float(state.get(key, default) or default))

    def _float(state: dict, key: str, default: float = 0.0) -> float:
        return float(state.get(key, default) or default)

    def _width_context(state: dict) -> tuple[str, None, float]:
        key = "bf" if "bf" in state else "b"
        return key, None, float(state.get(key, state.get("b", 300.0)) or 300.0)

    def _locked(state: dict) -> bool:
        return bool(geometry_locked)

    def _key(state: dict) -> tuple:
        return tuple(sorted((str(k), str(v)) for k, v in dict(state or {}).items()))

    def _ctype(base: dict, candidate: dict) -> str:
        calls["types"].append({"base": dict(base or {}), "candidate": dict(candidate or {})})
        updates = {k for k, v in dict(candidate or {}).items() if dict(base or {}).get(k) != v}
        has_geom = bool(updates.intersection({"D", "b", "bf", "bw"}))
        has_links = bool(updates.intersection({"lig_d", "lig_legs", "s_lig"}))
        if has_geom and has_links:
            return "combined"
        if has_geom:
            return "geometry"
        if "s_lig" in updates:
            return "spacing"
        if "lig_legs" in updates:
            return "legs"
        if "lig_d" in updates:
            return "diameter"
        return "unchanged"

    extracted.bind_shear_candidate_generation_dependencies(
        {
            "_activation_shear_state": _activation,
            "_float_from_state": _float,
            "_geometry_lock_enabled": _locked,
            "_int_from_state": _int,
            "_make_auto_design_candidate_key": _key,
            "_resolve_geometry_width_context": _width_context,
            "_shear_candidate_type": _ctype,
            "_shear_reinforcement_is_active": _active,
            "REO_BAR_DIAS": [10, 12, 16, 20, 24],
            "REO_SPACINGS": [300, 200, 150, 100],
        }
    )
    return {"module": extracted, "calls": calls}


def _escalation_cases() -> list[dict[str, Any]]:
    base = {"D": 600.0, "b": 300.0, "lig_d": 10, "lig_legs": 2, "s_lig": 200}
    unlocked = _bind_escalation_module()
    unlocked_result = unlocked["module"]._generate_escalated_shear_states(base, severity_band="severe")
    locked = _bind_escalation_module(geometry_locked=True)
    locked_result = locked["module"]._generate_escalated_shear_states(base, severity_band="severe")
    extreme = _bind_escalation_module()
    extreme_result = extreme["module"]._generate_escalated_shear_states(base, severity_band="extreme")
    inactive = _bind_escalation_module(active=False)
    inactive_result = inactive["module"]._generate_escalated_shear_states({"D": 600.0, "b": 300.0}, severity_band="severe")

    def states(rows: list[tuple[str, dict]]) -> list[dict]:
        return [dict(row[1]) for row in rows]

    unlocked_states = states(unlocked_result)
    locked_states = states(locked_result)
    extreme_states = states(extreme_result)
    inactive_states = states(inactive_result)
    return [
        {
            "name": "unlocked_generates_link_geometry_and_combined_states",
            "passed": len(unlocked_result) == 44
            and any(s.get("D") == 650.0 for s in unlocked_states)
            and any(s.get("b") == 350.0 for s in unlocked_states)
            and any(s.get("D") == 650.0 and s.get("b") == 350.0 and s.get("lig_legs") == 6 for s in unlocked_states),
        },
        {
            "name": "geometry_lock_limits_to_link_states",
            "passed": len(locked_result) == 36
            and all(s.get("D") == 600.0 and s.get("b") == 300.0 for s in locked_states),
        },
        {
            "name": "extreme_adds_third_geometry_step_and_max_dia",
            "passed": len(extreme_result) == 60
            and any(s.get("D") == 750.0 for s in extreme_states)
            and any(s.get("b") == 450.0 for s in extreme_states)
            and any(s.get("lig_d") == 24 for s in extreme_states),
        },
        {
            "name": "inactive_state_is_activated_before_generation",
            "passed": bool(inactive["calls"]["activation"])
            and len(inactive_result) == 44
            and all("lig_d" in s and "lig_legs" in s and "s_lig" in s for s in inactive_states),
        },
    ]


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")

    bridge_node = _function_node(bridge_source, "_generate_shear_candidates")
    bridge_escalated_node = _function_node(bridge_source, "_generate_escalated_shear_states")
    module_node = _function_node(module_source, "_generate_shear_candidates")
    module_escalated_node = _function_node(module_source, "_generate_escalated_shear_states")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    bridge_escalated_body = ast.get_source_segment(bridge_source, bridge_escalated_node) or ""
    dependency_block = module_source.split("def bind_shear_candidate_generation_dependencies", 1)[0]
    escalation_cases = _escalation_cases()

    checks: dict[str, bool] = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 3,
        "bridge_escalated_wrapper_is_small": (bridge_escalated_node.end_lineno or bridge_escalated_node.lineno) - bridge_escalated_node.lineno + 1 <= 3,
        "bridge_binds_dependencies": "_bind_shear_candidate_generation_dependencies(globals())" in bridge_body,
        "bridge_escalated_binds_dependencies": "_bind_shear_candidate_generation_dependencies(globals())" in bridge_escalated_body,
        "bridge_delegates_to_extracted_module": "_generate_shear_candidates_extracted" in bridge_body,
        "bridge_escalated_delegates_to_extracted_module": "_generate_escalated_shear_states_extracted" in bridge_escalated_body,
        "bridge_removed_escalated_body": "_activation_shear_state" not in bridge_escalated_body
        and "width_steps" not in bridge_escalated_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 108,
        "module_contains_escalated_body": (module_escalated_node.end_lineno or module_escalated_node.lineno) - module_escalated_node.lineno + 1 >= 60,
        "module_has_dependency_binder": "def bind_shear_candidate_generation_dependencies" in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_owns_escalated_helper": '"_generate_escalated_shear_states"' not in dependency_block,
        "module_binds_escalated_dependencies": all(
            token in dependency_block
            for token in (
                '"_activation_shear_state"',
                '"_float_from_state"',
                '"_geometry_lock_enabled"',
                '"_int_from_state"',
                '"_resolve_geometry_width_context"',
            )
        ),
        "module_keeps_shear_candidate_contract_surface": all(
            token in module_source
            for token in (
                "apply_shear_recommendation",
                "shear_candidate_type",
                "secondary_actions_combined",
                "shear_combined",
                "_generate_shear_candidates",
                "_log_severe_shear_escalation",
                "_invalid_shear_spacing_change_without_activation",
                "_generate_secondary_bending_tightening_states",
                "REO_BAR_DIAS",
                "REO_SPACINGS",
                "SHARED_DEFAULTS",
            )
        ),
        "module_keeps_escalated_contract_surface": all(
            token in module_source
            for token in (
                "max_legs = 10 if severity_band == \"extreme\" else 8",
                "max_dia = 24 if severity_band == \"extreme\" else 20",
                "width_steps.append(current_width + 150.0)",
                "depth_steps.append(current_depth + 150.0)",
                "_geometry_lock_enabled(state)",
            )
        ),
        "all_escalation_cases_pass": all(row["passed"] for row in escalation_cases),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.app_bridge import shear_candidate_generation as extracted

    original = bridge._generate_shear_candidates_extracted
    original_escalated = bridge._generate_escalated_shear_states_extracted
    module_escalated_owner = extracted._generate_escalated_shear_states
    call_record: dict = {}
    escalated_call_record: dict = {}

    def _fake_extracted(state: dict, mode_config: dict) -> list[dict]:
        call_record.update(
            {
                "state": dict(state),
                "mode_config": dict(mode_config),
                "bound_eval": getattr(extracted, "_evaluate_auto_design_candidate", None)
                is bridge._evaluate_auto_design_candidate,
                "bound_score": getattr(extracted, "_score_auto_design_candidate", None)
                is bridge._score_auto_design_candidate,
                "bound_escalated": getattr(extracted, "_generate_escalated_shear_states", None)
                is module_escalated_owner,
                "bound_invalid_spacing": getattr(
                    extracted,
                    "_invalid_shear_spacing_change_without_activation",
                    None,
                )
                is bridge._invalid_shear_spacing_change_without_activation,
                "bound_log": getattr(extracted, "_log_severe_shear_escalation", None)
                is bridge._log_severe_shear_escalation,
                "bound_shared_defaults": getattr(extracted, "SHARED_DEFAULTS", None)
                is bridge.SHARED_DEFAULTS,
                "bound_reo_bar_dias": getattr(extracted, "REO_BAR_DIAS", None)
                is bridge.REO_BAR_DIAS,
                "bound_reo_spacings": getattr(extracted, "REO_SPACINGS", None)
                is bridge.REO_SPACINGS,
            }
        )
        return [{"source": "fake_shear_candidate"}]

    def _fake_escalated(state: dict, *, severity_band: str) -> list[tuple[str, dict]]:
        escalated_call_record.update(
            {
                "state": dict(state),
                "severity_band": severity_band,
                "bound_activation": getattr(extracted, "_activation_shear_state", None)
                is bridge._activation_shear_state,
                "bound_width": getattr(extracted, "_resolve_geometry_width_context", None)
                is bridge._resolve_geometry_width_context,
                "module_owner": extracted._generate_escalated_shear_states is module_escalated_owner,
            }
        )
        return [("fake", {"D": 700})]

    try:
        bridge._generate_shear_candidates_extracted = _fake_extracted
        bridge._generate_escalated_shear_states_extracted = _fake_escalated
        returned = bridge._generate_shear_candidates({"Vu_star": 300.0}, {"mode": "balanced"})
        escalated_returned = bridge._generate_escalated_shear_states({"Vu_star": 300.0}, severity_band="extreme")
    finally:
        bridge._generate_shear_candidates_extracted = original
        bridge._generate_escalated_shear_states_extracted = original_escalated

    checks["bridge_runtime_binds_module_globals"] = (
        getattr(extracted, "_evaluate_auto_design_candidate", None) is bridge._evaluate_auto_design_candidate
        and getattr(extracted, "_score_auto_design_candidate", None) is bridge._score_auto_design_candidate
        and getattr(extracted, "_generate_escalated_shear_states", None) is module_escalated_owner
        and getattr(extracted, "_invalid_shear_spacing_change_without_activation", None)
        is bridge._invalid_shear_spacing_change_without_activation
        and getattr(extracted, "_log_severe_shear_escalation", None) is bridge._log_severe_shear_escalation
        and getattr(extracted, "SHARED_DEFAULTS", None) is bridge.SHARED_DEFAULTS
        and getattr(extracted, "REO_BAR_DIAS", None) is bridge.REO_BAR_DIAS
        and getattr(extracted, "REO_SPACINGS", None) is bridge.REO_SPACINGS
        and getattr(extracted, "_activation_shear_state", None) is bridge._activation_shear_state
        and getattr(extracted, "_resolve_geometry_width_context", None) is bridge._resolve_geometry_width_context
    )
    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == [{"source": "fake_shear_candidate"}]
        and call_record.get("state") == {"Vu_star": 300.0}
        and call_record.get("mode_config") == {"mode": "balanced"}
        and call_record.get("bound_eval") is True
        and call_record.get("bound_score") is True
        and call_record.get("bound_escalated") is True
        and call_record.get("bound_invalid_spacing") is True
        and call_record.get("bound_log") is True
        and call_record.get("bound_shared_defaults") is True
        and call_record.get("bound_reo_bar_dias") is True
        and call_record.get("bound_reo_spacings") is True
    )
    checks["bridge_escalated_runtime_delegates_with_arguments"] = (
        escalated_returned == [("fake", {"D": 700})]
        and escalated_call_record.get("state") == {"Vu_star": 300.0}
        and escalated_call_record.get("severity_band") == "extreme"
        and escalated_call_record.get("bound_activation") is True
        and escalated_call_record.get("bound_width") is True
        and escalated_call_record.get("module_owner") is True
    )

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "escalation_case_results": escalation_cases,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "bridge_escalated_wrapper_lines": (bridge_escalated_node.end_lineno or bridge_escalated_node.lineno) - bridge_escalated_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
        "module_escalated_function_lines": (module_escalated_node.end_lineno or module_escalated_node.lineno) - module_escalated_node.lineno + 1,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_shear_candidate_generation_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_shear_candidate_generation_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Shear Candidate Generation Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Bridge escalated wrapper lines: {result['bridge_escalated_wrapper_lines']}",
                f"- Extracted module function lines: {result['module_function_lines']}",
                f"- Extracted escalated function lines: {result['module_escalated_function_lines']}",
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
