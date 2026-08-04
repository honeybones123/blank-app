"""Verify one-click solver candidate scoring-state coordinator extraction."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AUTO_DESIGN_COMPUTE = ROOT / "inputs_page_modules" / "auto_design_compute.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _run_cases(module: Any) -> dict[str, Any]:
    originals = {
        "_candidate_in_target_band": getattr(module, "_candidate_in_target_band", None),
        "_candidate_target_domains_for_band": getattr(module, "_candidate_target_domains_for_band", None),
        "_one_click_domain_max_distance": getattr(module, "_one_click_domain_max_distance", None),
        "_one_click_domain_total_distance": getattr(module, "_one_click_domain_total_distance", None),
        "_one_click_required_domain_progress": getattr(module, "_one_click_required_domain_progress", None),
        "_one_click_mixed_direction_rank_adjustment": getattr(module, "_one_click_mixed_direction_rank_adjustment", None),
        "_resolve_target_band_candidate_sort_key": getattr(module, "_resolve_target_band_candidate_sort_key", None),
        "_one_click_directional_tie_key": getattr(module, "_one_click_directional_tie_key", None),
        "_float_from_state": getattr(module, "_float_from_state", None),
        "_design_optimisation_goal": getattr(module, "_design_optimisation_goal", None),
    }
    sort_calls: list[dict[str, Any]] = []

    def _in_band(peval: dict[str, Any], mode_config: Any) -> bool:
        return bool(peval.get("in_band"))

    def _domains(eval_obj: dict[str, Any]) -> list[str]:
        return list(eval_obj.get("domains") or [])

    def _max_distance(peval: dict[str, Any], mode_config: Any) -> float:
        return float(peval.get("max_distance", 0.0))

    def _total_distance(peval: dict[str, Any], mode_config: Any) -> float:
        return float(peval.get("total_distance", 0.0))

    def _progress(eval_obj: dict[str, Any], mode_config: Any) -> dict[str, int]:
        return dict(eval_obj.get("progress") or {})

    def _mixed_rank(cur_eval: dict[str, Any], peval: dict[str, Any], active: bool, mode_config: Any) -> dict[str, Any]:
        if not active:
            return {"active": False}
        return {
            "active": True,
            "primary_material_improvement": peval.get("primary_material", False),
            "primary_distance": peval.get("primary_distance", 9.0),
            "secondary_distance": peval.get("secondary_distance", 8.0),
        }

    def _sort_key(**kwargs: Any) -> tuple[Any, ...]:
        sort_calls.append(dict(kwargs))
        return ("sort", len(sort_calls), kwargs.get("tightening_mode_active"))

    def _tie_key(cur_u: float, new_u: float, mode_config: Any) -> float:
        return round(float(new_u) - float(cur_u), 6)

    def _float_from_state(state: dict[str, Any], key: str, default: float) -> float:
        return float(state.get(key, default) or default)

    def _goal(preview: dict[str, Any]) -> str:
        return str(preview.get("goal") or "")

    try:
        module._candidate_in_target_band = _in_band
        module._candidate_target_domains_for_band = _domains
        module._one_click_domain_max_distance = _max_distance
        module._one_click_domain_total_distance = _total_distance
        module._one_click_required_domain_progress = _progress
        module._one_click_mixed_direction_rank_adjustment = _mixed_rank
        module._resolve_target_band_candidate_sort_key = _sort_key
        module._one_click_directional_tie_key = _tie_key
        module._float_from_state = _float_from_state
        module._design_optimisation_goal = _goal

        shear_tightening = module._prepare_one_click_solver_candidate_scoring_state_coordinator(
            peval={
                "overview": {"all_key_pass": True},
                "in_band": True,
                "domains": ["shear", "web"],
                "max_distance": 0.03,
                "total_distance": 0.11,
                "progress": {"required_fail_count": 0, "required_unsatisfied_count": 2},
                "reo_congestion_index": 2.4,
            },
            cur_eval={
                "overview": {"all_key_pass": True},
                "domains": ["shear", "web"],
            },
            preview={"s_lig": 95, "goal": "less_shear_reinforcement"},
            mode_config={"mode": "balanced"},
            rc={"_shear_candidate_type": "spacing"},
            norm_u={"s_lig": 95, "lig_legs": 4},
            direction={"is_reduction_candidate": False},
            new_u=0.76,
            cur_u=0.80,
            new_d=0.02,
            mixed_direction_mode=False,
            tightening_mode_active=True,
            governing_domain="shear",
            family_hint="more_legs",
            shear_util_preview=0.92,
            web_util_preview=0.95,
            cur_has_td=True,
            cur_required_fail_count=0,
            cur_required_unsatisfied_count=3,
            web_crushing_penalty_applied=5,
        )
        non_tightening = module._prepare_one_click_solver_candidate_scoring_state_coordinator(
            peval={
                "overview": {"all_key_pass": False},
                "in_band": False,
                "domains": [],
                "primary_material": True,
            },
            cur_eval={"overview": {"all_key_pass": False}},
            preview={},
            mode_config={"mode": "balanced"},
            rc={},
            norm_u={"D": 620},
            direction={"is_reduction_candidate": True},
            new_u=0.91,
            cur_u=0.85,
            new_d=0.07,
            mixed_direction_mode=True,
            tightening_mode_active=False,
            governing_domain="bending",
            family_hint="depth",
            shear_util_preview=None,
            web_util_preview=None,
            cur_has_td=False,
            cur_required_fail_count=0,
            cur_required_unsatisfied_count=0,
            web_crushing_penalty_applied=5,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
            elif hasattr(module, name):
                delattr(module, name)

    return {
        "shear_tightening": shear_tightening,
        "non_tightening": non_tightening,
        "sort_calls": sort_calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_candidate_scoring_state_coordinator",
    )
    sort_start, sort_end, sort_helper = _function_segment(
        source,
        "_prepare_one_click_solver_candidate_sorting_state_coordinator",
    )
    chain_start, chain_end, chain_body = _function_segment(
        source,
        "_handle_one_click_solver_candidate_scored_assembly_chain_coordinator",
    )
    _, _, post_metric_body = _function_segment(
        source,
        "_run_one_click_solver_single_candidate_post_metric_scoring_flow_coordinator",
    )
    _, _, scored_assembly_dispatch_body = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_scored_assembly_chain_from_post_metric_coordinator",
    )
    _, _, pre_selection_body = _function_segment(
        source,
        "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator",
    )
    _, _, candidate_flow_body = _function_segment(
        source,
        "_run_one_click_solver_iteration_candidate_flow_coordinator",
    )
    _, _, iteration_loop_body = _function_segment(
        source,
        "_run_one_click_solver_iteration_loop_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    scoring_loop_start, scoring_loop_end, scoring_loop_body = _function_segment(
        source, "_run_one_click_solver_candidate_scoring_loop_coordinator"
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    shear = runtime["shear_tightening"]
    non_tightening = runtime["non_tightening"]
    sort_calls = runtime["sort_calls"]
    runtime_checks = {
        "shear_tightening_outputs_preserved": (
            shear["okp"] is True
            and shear["nib"] is True
            and shear["tier"] == 0
            and shear["has_target_domains"] is True
            and shear["new_max"] == 0.03
            and shear["new_total"] == 0.11
            and shear["prefer_total_before_max"] is True
            and shear["domain_progress"] == {"required_fail_count": 0, "required_unsatisfied_count": 2}
            and shear["required_fail_count"] == 0
            and shear["required_unsatisfied_count"] == 2
            and abs(float(shear["dk"]) - 0.04) < 1e-9
            and shear["web_crushing_penalty_applied"] == 6
        ),
        "shear_sort_inputs_preserved": (
            sort_calls[0].get("tier") == 0
            and tuple(sort_calls[0].get("mixed_sort_prefix") or ()) == ()
            and sort_calls[0].get("tightening_mode_active") is True
            and sort_calls[0].get("governing_domain") == "shear"
            and sort_calls[0].get("has_target_domains") is True
            and sort_calls[0].get("new_max") == 0.03
            and sort_calls[0].get("new_total") == 0.11
            and sort_calls[0].get("required_fail_count") == 0
            and sort_calls[0].get("required_unsatisfied_count") == 2
            and sort_calls[0].get("prefer_total_before_max") is True
            and sort_calls[0].get("shear_sort_util") == 0.92
            and sort_calls[0].get("web_sort_util") == 0.95
            and sort_calls[0].get("practical_spacing_penalty") == 1
            and sort_calls[0].get("congestion_penalty") == 1
            and sort_calls[0].get("goal_bias") == 1
            and sort_calls[0].get("new_distance") == 0.02
            and abs(float(sort_calls[0].get("wrong_dir_penalty")) - 0.04) < 1e-9
            and sort_calls[0].get("reduction_bias") == 1
            and sort_calls[0].get("update_count") == 2
        ),
        "non_tightening_outputs_preserved": (
            non_tightening["okp"] is False
            and non_tightening["nib"] is False
            and non_tightening["tier"] == 1
            and non_tightening["has_target_domains"] is False
            and non_tightening["new_max"] is None
            and non_tightening["new_total"] is None
            and non_tightening["domain_progress"] == {}
            and non_tightening["dk"] == 0.06
            and non_tightening["web_crushing_penalty_applied"] == 5
        ),
        "non_tightening_sort_inputs_preserved": sort_calls[1] == {
            "tier": 1,
            "mixed_sort_prefix": (0, 9.0, 8.0),
            "tightening_mode_active": False,
            "governing_domain": "bending",
            "has_target_domains": False,
            "new_max": None,
            "new_total": None,
            "required_fail_count": 0,
            "required_unsatisfied_count": 0,
            "prefer_total_before_max": False,
            "new_distance": 0.07,
            "directional_tie_key": 0.06,
            "update_count": 1,
        },
    }
    static_checks = {
        "solver_delegates_iteration_loop": (
            "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body
        ),
        "iteration_loop_delegates_candidate_flow": (
            "_dispatch_one_click_solver_iteration_candidate_flow_from_iteration_loop_coordinator("
            in iteration_loop_body
        ),
        "candidate_flow_delegates_pre_selection": (
            "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator("
            in candidate_flow_body
        ),
        "pre_selection_delegates_candidate_scoring_loop": (
            "_dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator(" in pre_selection_body
            or "_run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator(" in pre_selection_body
        ),
        "helper_present": "def _prepare_one_click_solver_candidate_scoring_state_coordinator(" in source,
        "helper_preserves_pass_band_tier": (
            'okp = bool((peval.get("overview") or {}).get("all_key_pass"))' in helper
            and "_candidate_in_target_band(peval, mode_config)" in helper
            and "tier = 0 if (okp and nib) else 1" in helper
        ),
        "helper_preserves_target_domain_metrics": (
            "_one_click_domain_max_distance(peval, mode_config)" in helper
            and "_one_click_domain_total_distance(peval, mode_config)" in helper
            and "_one_click_required_domain_progress(peval, mode_config)" in helper
        ),
        "helper_preserves_prefer_total_before_max": (
            "cur_required_unsatisfied_count > 1" in helper
            and "required_unsatisfied_count > 1" in helper
            and "len(_candidate_target_domains_for_band(peval) or []) > 1" in helper
        ),
        "helper_preserves_mixed_rank_prefix": (
            "_one_click_mixed_direction_rank_adjustment(" in sort_helper
            and "primary_material_improvement" in sort_helper
        ),
        "helper_preserves_tightening_shear_penalties": (
            "web_crushing_penalty_applied += 1" in sort_helper
            and "_design_optimisation_goal(preview)" in sort_helper
            and "_float_from_state(preview, \"s_lig\", 0.0)" in sort_helper
        ),
        "helper_delegates_sorting_state": (
            "_prepare_one_click_solver_candidate_sorting_state_coordinator(" in helper
        ),
        "helper_preserves_sort_key_resolution": sort_helper.count("_resolve_target_band_candidate_sort_key(") == 2,
        "chain_delegates_scoring_state": (
            "_prepare_one_click_solver_candidate_scoring_state_coordinator(" in chain_body
        ),
        "chain_rehydrates_scoring_fields": (
            'nib = scoring_state["nib"]' in chain_body
            and 'sort_key = scoring_state["sort_key"]' in chain_body
            and 'web_crushing_penalty_applied = scoring_state["web_crushing_penalty_applied"]' in chain_body
        ),
        "post_metric_flow_delegates_scored_assembly_chain": (
            "_dispatch_one_click_solver_candidate_scored_assembly_chain_from_post_metric_coordinator("
            in post_metric_body
        ),
        "post_metric_scored_assembly_dispatch_delegates_chain": (
            "_handle_one_click_solver_candidate_scored_assembly_chain_coordinator("
            in scored_assembly_dispatch_body
            and "post_metric_scope[" in scored_assembly_dispatch_body
        ),
        "post_metric_flow_rehydrates_scored_assembly_state": (
            'scored = scored_assembly_chain_state["scored"]' in post_metric_body
            and 'web_crushing_penalty_applied = scored_assembly_chain_state['
            in post_metric_body
        ),
        "solver_no_longer_resolves_sort_key_inline": "_resolve_target_band_candidate_sort_key(" not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_scoring_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_candidate_scoring_state_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "sort_segment": {
            "function": "_prepare_one_click_solver_candidate_sorting_state_coordinator",
            "start_line": sort_start,
            "end_line": sort_end,
            "line_count": sort_end - sort_start + 1,
        },
        "chain_segment": {
            "function": "_handle_one_click_solver_candidate_scored_assembly_chain_coordinator",
            "start_line": chain_start,
            "end_line": chain_end,
            "line_count": chain_end - chain_start + 1,
        },
        "solver_segment": {
            "function": "_solve_one_click_to_target",
            "start_line": solve_start,
            "end_line": solve_end,
            "line_count": solve_end - solve_start + 1,
        },
        "static_checks": static_checks,
        "runtime_checks": runtime_checks,
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract scored candidate append coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_candidate_scoring_state_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_candidate_scoring_state_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Candidate Scoring State Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("## Runtime Checks")
    for key, value in payload["runtime_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Next Safe Slice", "", str(payload["next_safe_slice"])])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
