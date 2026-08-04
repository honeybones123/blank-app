"""Verify one-click solver current iteration eval state coordinator extraction."""

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


def _run_normal_case(module: Any) -> dict[str, Any]:
    originals = {
        "BEAM_STATUS_FAIL": getattr(module, "BEAM_STATUS_FAIL", None),
        "_build_canonical_design_state_pack": getattr(module, "_build_canonical_design_state_pack", None),
        "evaluate_candidate_full": getattr(module, "evaluate_candidate_full", None),
        "_candidate_state_signature": getattr(module, "_candidate_state_signature", None),
        "_one_click_tightening_mode_active": getattr(module, "_one_click_tightening_mode_active", None),
        "_governing_focus_from_overview": getattr(module, "_governing_focus_from_overview", None),
    }
    calls: list[dict[str, Any]] = []
    cur_eval = {
        "overview": {
            "all_key_pass": False,
            "statuses": {"shear": "FAIL", "flexure": "FAIL", "crack": "PASS"},
        }
    }

    try:
        module.BEAM_STATUS_FAIL = "FAIL"
        module._build_canonical_design_state_pack = lambda working: {"pack": dict(working)}

        def _eval(pack: dict, **kwargs: Any) -> dict[str, Any]:
            calls.append({"evaluate": {"pack": pack, "kwargs": dict(kwargs)}})
            return cur_eval

        module.evaluate_candidate_full = _eval
        module._candidate_state_signature = lambda eval_obj: ("sig", "cur")
        module._one_click_tightening_mode_active = lambda eval_obj, mode_config: True
        module._governing_focus_from_overview = lambda overview: "shear"
        result = module._prepare_one_click_solver_current_iteration_eval_state_coordinator(
            step_idx=3,
            working={"D": 650},
            mode_config={"mode": "probe"},
            target_band_domain="bending",
            step_trace=[],
            initial_snapshot={"D": 600},
            winning_label="Previous",
            winning_action_type="previous_action",
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    return {"result": result, "calls": calls}


def _run_none_case(module: Any) -> dict[str, Any]:
    originals = {
        "_build_canonical_design_state_pack": getattr(module, "_build_canonical_design_state_pack", None),
        "evaluate_candidate_full": getattr(module, "evaluate_candidate_full", None),
        "_trace_evaluate_failed_working_solver_stop_coordinator": getattr(
            module,
            "_trace_evaluate_failed_working_solver_stop_coordinator",
            None,
        ),
    }
    calls: list[dict[str, Any]] = []

    try:
        module._build_canonical_design_state_pack = lambda working: {"pack": dict(working)}
        module.evaluate_candidate_full = lambda *_args, **_kwargs: None

        def _failed(**kwargs: Any) -> tuple[str, str]:
            calls.append(
                {
                    "failed": {
                        "step_trace": list(kwargs.get("step_trace") or []),
                        "initial_snapshot": dict(kwargs.get("initial_snapshot") or {}),
                        "working": dict(kwargs.get("working") or {}),
                        "winning_label": kwargs.get("winning_label"),
                        "winning_action_type": kwargs.get("winning_action_type"),
                    }
                }
            )
            return "evaluate_failed_working", "failed"

        module._trace_evaluate_failed_working_solver_stop_coordinator = _failed
        result = module._prepare_one_click_solver_current_iteration_eval_state_coordinator(
            step_idx=0,
            working={"D": 650},
            mode_config={"mode": "probe"},
            target_band_domain="bending",
            step_trace=[{"label": "old"}],
            initial_snapshot={"D": 600},
            winning_label="Previous",
            winning_action_type="previous_action",
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    return {"result": result, "calls": calls}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_current_iteration_eval_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    iteration_gate_start, iteration_gate_end, iteration_gate_body = _function_segment(
        source, "_prepare_one_click_solver_iteration_gate_state_coordinator"
    )
    _, _, iteration_gate_after_current_eval_body = _function_segment(
        source,
        "_prepare_one_click_solver_iteration_gate_after_current_eval_state_coordinator",
    )
    loop_start, loop_end, loop_body = _function_segment(
        source, "_run_one_click_solver_iteration_loop_coordinator"
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    normal = _run_normal_case(module)
    none_case = _run_none_case(module)
    result = normal["result"]
    runtime_checks = {
        "working_eval_call_preserved": normal["calls"] == [
            {
                "evaluate": {
                    "pack": {"pack": {"D": 650}},
                    "kwargs": {
                        "source": "one_click_work_3",
                        "label": "Working",
                        "action_type": "one_click",
                        "updates": {},
                    },
                }
            }
        ],
        "normal_iteration_fields_preserved": result["cur_eval"] is not None
        and result["cur_pass"] is False
        and result["cur_sig"] == ("sig", "cur")
        and result["tightening_mode_active"] is True
        and result["governing_domain"] == "shear"
        and result["target_band_domain"] == "shear"
        and result["cur_statuses"] == {"shear": "FAIL", "flexure": "FAIL", "crack": "PASS"}
        and result["cur_shear_status"] == "FAIL"
        and result["cur_shear_failing"] is True
        and result["cur_fail_keys"] == {"shear", "flexure"}
        and result["governing_domain_norm"] == "shear"
        and result["governing_domain_failing"] is True
        and result["should_break"] is False,
        "evaluate_failed_stop_routing_preserved": none_case["result"] == {
            "cur_eval": None,
            "stop_reason": "evaluate_failed_working",
            "status": "failed",
            "should_break": True,
        }
        and none_case["calls"] == [
            {
                "failed": {
                    "step_trace": [{"label": "old"}],
                    "initial_snapshot": {"D": 600},
                    "working": {"D": 650},
                    "winning_label": "Previous",
                    "winning_action_type": "previous_action",
                }
            }
        ],
    }
    static_checks = {
        "solver_delegates_iteration_gate_state": (
            "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator("
            in solve_body
            and "_dispatch_one_click_solver_iteration_gate_state_from_iteration_loop_coordinator("
            in loop_body
            and "_prepare_one_click_solver_iteration_gate_state_coordinator(" in source
        ),
        "helper_present": "def _prepare_one_click_solver_current_iteration_eval_state_coordinator(" in source,
        "helper_preserves_working_evaluation": "evaluate_candidate_full(" in helper
        and 'source=f"one_click_work_{step_idx}"' in helper
        and 'label="Working"' in helper
        and 'action_type="one_click"' in helper
        and "updates={}" in helper,
        "helper_preserves_failed_eval_stop_routing": "_trace_evaluate_failed_working_solver_stop_coordinator("
        in helper
        and '"should_break": True' in helper,
        "helper_preserves_pass_signature_tightening": "_candidate_state_signature(cur_eval)" in helper
        and "_one_click_tightening_mode_active(cur_eval, mode_config)" in helper,
        "helper_preserves_governing_pivot": "target_band_domain != \"shear\"" in helper
        and "target_band_domain = \"shear\"" in helper,
        "helper_preserves_status_and_shear_failure": "cur_statuses = dict((cur_eval.get(\"overview\") or {}).get(\"statuses\") or {})"
        in helper
        and "cur_shear_status == BEAM_STATUS_FAIL" in helper,
        "helper_preserves_fail_key_normalization": "cur_fail_keys = {" in helper
        and "str(k or \"\").strip().lower()" in helper
        and '"flexure"' in helper
        and '"ductility"' in helper,
        "solver_delegates_current_iteration_eval_state": "_prepare_one_click_solver_current_iteration_eval_state_coordinator("
        in iteration_gate_body,
        "solver_preserves_break_on_none": 'if cur_eval is None:' in iteration_gate_body
        and '"stop_reason": current_iteration_eval_state["stop_reason"]' in iteration_gate_body
        and '"should_break": True' in iteration_gate_body,
        "solver_rehydrates_current_iteration_fields": 'cur_pass = current_iteration_eval_state["cur_pass"]'
        in iteration_gate_after_current_eval_body
        and 'governing_domain_failing = current_iteration_eval_state["governing_domain_failing"]'
        in iteration_gate_after_current_eval_body,
        "solver_no_longer_inlines_current_iteration_eval": 'source=f"one_click_work_{step_idx}"' not in solve_body
        and "_trace_evaluate_failed_working_solver_stop_coordinator(" not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_current_iteration_eval_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_current_iteration_eval_state_coordinator",
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
        "loop_segment": {
            "function": "_run_one_click_solver_iteration_loop_coordinator",
            "start_line": loop_start,
            "end_line": loop_end,
            "line_count": loop_end - loop_start + 1,
        },
        "static_checks": static_checks,
        "runtime_checks": runtime_checks,
        "runtime": {
            "normal": {
                "calls": normal["calls"],
                "result": {
                    key: sorted(value) if isinstance(value, set) else value
                    for key, value in result.items()
                },
            },
            "none_case": none_case,
        },
        "product_behavior_changed": False,
        "next_safe_slice": "extract current target-domain attachment and required-domain gate",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_current_iteration_eval_state_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_current_iteration_eval_state_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Current Iteration Eval State Coordinator Extraction",
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
