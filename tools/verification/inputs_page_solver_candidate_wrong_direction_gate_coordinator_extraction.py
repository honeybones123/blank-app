"""Verify one-click solver wrong-direction candidate gate coordinator extraction."""

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
        "_candidate_target_domains_for_band": getattr(module, "_candidate_target_domains_for_band", None),
        "_one_click_step_improves": getattr(module, "_one_click_step_improves", None),
        "_trace_candidate_eval_wrong_direction_solver_coordinator": getattr(
            module, "_trace_candidate_eval_wrong_direction_solver_coordinator", None
        ),
    }
    trace_calls: list[dict[str, Any]] = []

    def _domains(eval_obj: dict[str, Any]) -> list[str]:
        return list(eval_obj.get("domains") or [])

    def _improves(peval: dict[str, Any], cur_eval: dict[str, Any], mode_config: Any) -> bool:
        return bool(peval.get("improves_step"))

    def _trace(**kwargs: Any) -> None:
        trace_calls.append(
            {
                "multi_domain": kwargs.get("multi_domain_step_improves"),
                "all_pass": kwargs.get("all_pass_band_distance_improves"),
                "new_d": kwargs.get("new_d"),
            }
        )

    common = {
        "cur_eval": {"domains": []},
        "mode_config": {"mode": "balanced"},
        "step_idx": 5,
        "rc": {"title": "candidate"},
        "norm_u": {"D": 520},
        "new_u": 0.70,
        "cur_u": 0.80,
        "old_d": 0.10,
        "direction": {"is_growth_only": True},
        "governing_domain": "bending",
        "family_hint": "depth",
        "tightening_mode_active": True,
        "growth_candidates_rejected_in_tightening": 4,
        "trace_callback": lambda _ev, _dat: None,
    }
    try:
        module._candidate_target_domains_for_band = _domains
        module._one_click_step_improves = _improves
        module._trace_candidate_eval_wrong_direction_solver_coordinator = _trace

        rejected = module._handle_one_click_solver_candidate_wrong_direction_gate_coordinator(
            **common,
            peval={"overview": {"all_key_pass": False}, "domains": []},
            new_d=0.12,
        )
        multi_domain_escape = module._handle_one_click_solver_candidate_wrong_direction_gate_coordinator(
            **common,
            peval={"overview": {"all_key_pass": False}, "domains": ["bending"], "improves_step": True},
            new_d=0.12,
        )
        all_pass_distance_escape = module._handle_one_click_solver_candidate_wrong_direction_gate_coordinator(
            **common,
            peval={"overview": {"all_key_pass": True}, "domains": []},
            new_d=0.02,
        )
        not_tightening_escape = module._handle_one_click_solver_candidate_wrong_direction_gate_coordinator(
            **{**common, "tightening_mode_active": False},
            peval={"overview": {"all_key_pass": False}, "domains": []},
            new_d=0.12,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
            elif hasattr(module, name):
                delattr(module, name)

    return {
        "rejected": rejected,
        "multi_domain_escape": multi_domain_escape,
        "all_pass_distance_escape": all_pass_distance_escape,
        "not_tightening_escape": not_tightening_escape,
        "trace_calls": trace_calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_candidate_wrong_direction_gate_coordinator",
    )
    chain_start, chain_end, chain_body = _function_segment(
        source,
        "_handle_one_click_solver_candidate_direction_material_gate_chain_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    scoring_loop_start, scoring_loop_end, scoring_loop_body = _function_segment(
        source, "_run_one_click_solver_candidate_scoring_loop_coordinator"
    )
    _, _, post_metric_body = _function_segment(
        source, "_run_one_click_solver_single_candidate_post_metric_scoring_flow_coordinator"
    )
    _, _, direction_material_dispatch_body = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_direction_material_gate_chain_from_post_metric_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    runtime_checks = {
        "wrong_direction_rejects_and_increments_counter": runtime["rejected"] == {
            "growth_candidates_rejected_in_tightening": 5,
            "multi_domain_step_improves": False,
            "all_pass_band_distance_improves": False,
            "should_continue": True,
        },
        "multi_domain_escape_preserved": runtime["multi_domain_escape"] == {
            "growth_candidates_rejected_in_tightening": 4,
            "multi_domain_step_improves": True,
            "all_pass_band_distance_improves": False,
            "should_continue": False,
        },
        "all_pass_distance_escape_preserved": runtime["all_pass_distance_escape"] == {
            "growth_candidates_rejected_in_tightening": 4,
            "multi_domain_step_improves": False,
            "all_pass_band_distance_improves": True,
            "should_continue": False,
        },
        "not_tightening_escape_preserved": runtime["not_tightening_escape"] == {
            "growth_candidates_rejected_in_tightening": 4,
            "multi_domain_step_improves": False,
            "all_pass_band_distance_improves": False,
            "should_continue": False,
        },
        "trace_only_for_rejection": runtime["trace_calls"] == [
            {"multi_domain": False, "all_pass": False, "new_d": 0.12}
        ],
    }
    static_checks = {
        "solver_delegates_iteration_loop": (
            "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator("
            in solve_body
        ),
        "helper_present": "def _handle_one_click_solver_candidate_wrong_direction_gate_coordinator(" in source,
        "helper_preserves_multi_domain_improvement_check": (
            "_candidate_target_domains_for_band(cur_eval)" in helper
            and "_candidate_target_domains_for_band(peval)" in helper
            and "_one_click_step_improves(peval, cur_eval, mode_config)" in helper
        ),
        "helper_preserves_all_pass_distance_check": (
            'bool((peval.get("overview") or {}).get("all_key_pass"))' in helper
            and "math.isfinite(old_d)" in helper
            and "math.isfinite(new_d)" in helper
            and "new_d < old_d - 1e-6" in helper
        ),
        "helper_preserves_wrong_direction_condition": (
            "tightening_mode_active" in helper
            and "new_u < cur_u - 1e-6" in helper
            and "and not multi_domain_step_improves" in helper
            and "and not all_pass_band_distance_improves" in helper
        ),
        "helper_preserves_counter_and_trace": "growth_candidates_rejected_in_tightening += 1" in helper
        and "_trace_candidate_eval_wrong_direction_solver_coordinator(" in helper,
        "helper_returns_escape_booleans": '"multi_domain_step_improves": multi_domain_step_improves' in helper
        and '"all_pass_band_distance_improves": all_pass_band_distance_improves' in helper,
        "chain_delegates_wrong_direction_gate": (
            "_handle_one_click_solver_candidate_wrong_direction_gate_coordinator(" in chain_body
        ),
        "chain_rehydrates_counter_and_continue": (
            'growth_candidates_rejected_in_tightening = wrong_direction_gate_state[' in chain_body
            and 'if wrong_direction_gate_state["should_continue"]:' in chain_body
        ),
        "solver_delegates_direction_material_gate_chain": (
            "_dispatch_one_click_solver_candidate_direction_material_gate_chain_from_post_metric_coordinator("
            in post_metric_body
            and "_handle_one_click_solver_candidate_direction_material_gate_chain_coordinator("
            in direction_material_dispatch_body
        ),
        "solver_rehydrates_chain_counter_and_continue": (
            'growth_candidates_rejected_in_tightening = direction_material_gate_chain_state[' in post_metric_body
            and 'if direction_material_gate_chain_state["should_continue"]:' in post_metric_body
        ),
        "solver_no_longer_owns_multi_domain_check": "_one_click_step_improves(peval, cur_eval, mode_config)" not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_wrong_direction_gate_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_candidate_wrong_direction_gate_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "chain_segment": {
            "function": "_handle_one_click_solver_candidate_direction_material_gate_chain_coordinator",
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
        "next_safe_slice": "extract non-material improvement candidate gate coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_candidate_wrong_direction_gate_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_candidate_wrong_direction_gate_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Candidate Wrong Direction Gate Coordinator Extraction",
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
