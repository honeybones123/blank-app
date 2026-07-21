"""Verify one-click solver tightening-depth gate state coordinator extraction."""

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
        "_candidate_objective_util": getattr(module, "_candidate_objective_util", None),
        "_one_click_budget_stop_has_better_next_hop": getattr(
            module,
            "_one_click_budget_stop_has_better_next_hop",
            None,
        ),
        "_trace_tightening_depth_budget_solver_stop_coordinator": getattr(
            module,
            "_trace_tightening_depth_budget_solver_stop_coordinator",
            None,
        ),
    }
    calls: list[dict[str, Any]] = []

    try:
        module._candidate_objective_util = lambda cur_eval: 0.91
        module._one_click_budget_stop_has_better_next_hop = lambda cur_eval, mode_config: True
        module._trace_tightening_depth_budget_solver_stop_coordinator = lambda **kwargs: (
            "tightening_depth_budget_reached",
            "exhausted",
            0.12,
        )
        extension = module._prepare_one_click_solver_tightening_depth_gate_state_coordinator(
            cur_eval={"overview": {}},
            mode_config={"mode": "probe"},
            step_trace=[],
            initial_snapshot={"D": 600},
            working={"D": 650},
            cur_ib=False,
            cur_pass=False,
            winning_label=None,
            winning_action_type=None,
            tightening_mode_active=True,
            tightening_step_count=5,
            max_tightening_steps=4,
            tightening_budget_extensions_used=0,
            tightening_budget_extension_cap=2,
            candidate_family_depth_reached="spacing",
            trace_callback=lambda *_args, **_kwargs: None,
        )

        module._one_click_budget_stop_has_better_next_hop = lambda cur_eval, mode_config: False

        def _stop(**kwargs: Any) -> tuple[str, str, float]:
            calls.append(
                {
                    "stop": {
                        "cur_ib": kwargs.get("cur_ib"),
                        "cur_pass": kwargs.get("cur_pass"),
                        "tightening_step_count": kwargs.get("tightening_step_count"),
                        "max_tightening_steps": kwargs.get("max_tightening_steps"),
                        "candidate_family_depth_reached": kwargs.get("candidate_family_depth_reached"),
                    }
                }
            )
            return "tightening_depth_budget_reached", "exhausted", 0.12

        module._trace_tightening_depth_budget_solver_stop_coordinator = _stop
        stopped = module._prepare_one_click_solver_tightening_depth_gate_state_coordinator(
            cur_eval={"overview": {}},
            mode_config={"mode": "probe"},
            step_trace=[],
            initial_snapshot={"D": 600},
            working={"D": 650},
            cur_ib=False,
            cur_pass=False,
            winning_label="Candidate",
            winning_action_type="tighten",
            tightening_mode_active=True,
            tightening_step_count=5,
            max_tightening_steps=4,
            tightening_budget_extensions_used=2,
            tightening_budget_extension_cap=2,
            candidate_family_depth_reached="spacing",
            trace_callback=lambda *_args, **_kwargs: None,
        )

        normal = module._prepare_one_click_solver_tightening_depth_gate_state_coordinator(
            cur_eval={"overview": {}},
            mode_config={"mode": "probe"},
            step_trace=[],
            initial_snapshot={"D": 600},
            working={"D": 650},
            cur_ib=False,
            cur_pass=False,
            winning_label=None,
            winning_action_type=None,
            tightening_mode_active=False,
            tightening_step_count=0,
            max_tightening_steps=4,
            tightening_budget_extensions_used=0,
            tightening_budget_extension_cap=2,
            candidate_family_depth_reached="none",
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    return {"extension": extension, "stopped": stopped, "normal": normal, "calls": calls}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_tightening_depth_gate_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    iteration_gate_start, iteration_gate_end, iteration_gate_body = _function_segment(
        source, "_prepare_one_click_solver_iteration_gate_state_coordinator"
    )
    _, _, tightening_depth_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_tightening_depth_gate_state_from_iteration_gate_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    runtime_checks = {
        "extension_path_preserved": runtime["extension"] == {
            "cur_u": 0.91,
            "max_tightening_steps": 5,
            "tightening_budget_extensions_used": 1,
            "final_distance_to_band": None,
            "should_continue": True,
            "should_break": False,
        },
        "stop_path_preserved": runtime["stopped"] == {
            "cur_u": 0.91,
            "max_tightening_steps": 4,
            "tightening_budget_extensions_used": 2,
            "stop_reason": "tightening_depth_budget_reached",
            "status": "exhausted",
            "final_distance_to_band": 0.12,
            "should_continue": False,
            "should_break": True,
        }
        and runtime["calls"] == [
            {
                "stop": {
                    "cur_ib": False,
                    "cur_pass": False,
                    "tightening_step_count": 5,
                    "max_tightening_steps": 4,
                    "candidate_family_depth_reached": "spacing",
                }
            }
        ],
        "normal_path_preserved": runtime["normal"] == {
            "cur_u": 0.91,
            "max_tightening_steps": 4,
            "tightening_budget_extensions_used": 0,
            "final_distance_to_band": None,
            "should_continue": False,
            "should_break": False,
        },
    }
    static_checks = {
        "solver_delegates_iteration_gate_state": (
            "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator("
            in solve_body
            and "_prepare_one_click_solver_iteration_gate_state_coordinator(" in source
        ),
        "helper_present": "def _prepare_one_click_solver_tightening_depth_gate_state_coordinator(" in source,
        "helper_preserves_current_util": "_candidate_objective_util(cur_eval)" in helper,
        "helper_preserves_budget_gate": "tightening_mode_active and tightening_step_count > max_tightening_steps"
        in helper,
        "helper_preserves_extension_probe": "_one_click_budget_stop_has_better_next_hop(cur_eval, mode_config)"
        in helper,
        "helper_preserves_extension_updates": '"max_tightening_steps": max_tightening_steps + 1' in helper
        and '"tightening_budget_extensions_used": tightening_budget_extensions_used + 1' in helper
        and '"should_continue": True' in helper,
        "helper_preserves_stop_routing": "_trace_tightening_depth_budget_solver_stop_coordinator(" in helper
        and '"should_break": True' in helper,
        "solver_delegates_tightening_depth_gate": (
            "_dispatch_one_click_solver_tightening_depth_gate_state_from_iteration_gate_coordinator("
            in iteration_gate_body
            and "_prepare_one_click_solver_tightening_depth_gate_state_coordinator("
            in tightening_depth_dispatch
            and "iteration_gate_scope[" in tightening_depth_dispatch
        ),
        "solver_preserves_continue_and_break": 'if tightening_depth_gate_state["should_continue"]:' in iteration_gate_body
        and 'if tightening_depth_gate_state["should_break"]:' in iteration_gate_body,
        "solver_rehydrates_tightening_depth_fields": 'cur_u = tightening_depth_gate_state["cur_u"]' in iteration_gate_body
        and 'max_tightening_steps = tightening_depth_gate_state["max_tightening_steps"]' in iteration_gate_body
        and '"final_distance_to_band": tightening_depth_gate_state["final_distance_to_band"]' in iteration_gate_body,
        "solver_no_longer_inlines_tightening_depth_gate": "tightening_step_count > max_tightening_steps" not in solve_body
        and "_trace_tightening_depth_budget_solver_stop_coordinator(" not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_tightening_depth_gate_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_tightening_depth_gate_state_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
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
        "next_safe_slice": "extract candidate collection and governing-domain candidate selection",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_tightening_depth_gate_state_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_tightening_depth_gate_state_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Tightening Depth Gate State Coordinator Extraction",
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
