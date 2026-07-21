"""Verify candidate direction/material gate-chain coordinator extraction."""

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
_MISSING = object()


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


def _patch(module: Any, replacements: dict[str, Any]) -> dict[str, Any]:
    originals = {name: getattr(module, name, _MISSING) for name in replacements}
    for name, value in replacements.items():
        setattr(module, name, value)
    return originals


def _restore(module: Any, originals: dict[str, Any]) -> None:
    for name, original in originals.items():
        if original is _MISSING:
            delattr(module, name)
        else:
            setattr(module, name, original)


def _call(module: Any, *, wrong_continue: bool, non_continue: bool) -> tuple[dict[str, Any], list[str]]:
    calls: list[str] = []

    def _wrong(**kwargs: Any) -> dict[str, Any]:
        calls.append("wrong")
        return {
            "growth_candidates_rejected_in_tightening": int(
                kwargs["growth_candidates_rejected_in_tightening"]
            )
            + 1,
            "multi_domain_step_improves": False,
            "all_pass_band_distance_improves": False,
            "should_continue": wrong_continue,
        }

    def _non_material(**kwargs: Any) -> dict[str, Any]:
        calls.append("non_material")
        return {
            "rejected_as_non_material_improvement": int(
                kwargs["rejected_as_non_material_improvement"]
            )
            + 1,
            "shear_remove_links_candidate_dropped_reason": "non_material_improvement",
            "shear_remove_links_candidate_materiality": "non_material",
            "should_continue": non_continue,
        }

    originals = _patch(
        module,
        {
            "_handle_one_click_solver_candidate_wrong_direction_gate_coordinator": _wrong,
            "_handle_one_click_solver_candidate_non_material_gate_coordinator": _non_material,
        },
    )
    try:
        returned = module._handle_one_click_solver_candidate_direction_material_gate_chain_coordinator(
            peval={"overview": {}},
            cur_eval={"overview": {}},
            mode_config={"mode": "tight"},
            step_idx=3,
            rc={"title": "candidate"},
            norm_u={"D": 650},
            new_u=0.70,
            cur_u=0.80,
            new_d=0.12,
            old_d=0.10,
            direction={"is_growth_only": True},
            governing_domain="shear",
            family_hint="depth",
            tightening_mode_active=True,
            growth_candidates_rejected_in_tightening=4,
            material_improvement_threshold=0.01,
            remove_links_candidate=True,
            remove_links_truth_ok=False,
            shear_remove_links_candidate_dropped_reason=None,
            shear_remove_links_candidate_materiality="not_evaluated",
            rejected_as_non_material_improvement=7,
            trace_callback=lambda ev, dat: None,
        )
    finally:
        _restore(module, originals)
    return returned, calls


def _run_case(module: Any) -> dict[str, Any]:
    wrong_reject, wrong_calls = _call(module, wrong_continue=True, non_continue=True)
    non_material_reject, non_calls = _call(module, wrong_continue=False, non_continue=True)
    pass_through, pass_calls = _call(module, wrong_continue=False, non_continue=False)
    return {
        "wrong_reject": wrong_reject,
        "wrong_calls": wrong_calls,
        "non_material_reject": non_material_reject,
        "non_calls": non_calls,
        "pass_through": pass_through,
        "pass_calls": pass_calls,
        "matches": (
            wrong_calls == ["wrong"]
            and wrong_reject == {
                "growth_candidates_rejected_in_tightening": 5,
                "rejected_as_non_material_improvement": 7,
                "shear_remove_links_candidate_dropped_reason": None,
                "shear_remove_links_candidate_materiality": "not_evaluated",
                "should_continue": True,
            }
            and non_calls == ["wrong", "non_material"]
            and non_material_reject == {
                "growth_candidates_rejected_in_tightening": 5,
                "rejected_as_non_material_improvement": 8,
                "shear_remove_links_candidate_dropped_reason": "non_material_improvement",
                "shear_remove_links_candidate_materiality": "non_material",
                "should_continue": True,
            }
            and pass_calls == ["wrong", "non_material"]
            and pass_through == {
                "growth_candidates_rejected_in_tightening": 5,
                "rejected_as_non_material_improvement": 8,
                "shear_remove_links_candidate_dropped_reason": "non_material_improvement",
                "shear_remove_links_candidate_materiality": "non_material",
                "should_continue": False,
            }
        ),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_candidate_direction_material_gate_chain_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    scoring_loop_start, scoring_loop_end, scoring_loop_body = _function_segment(
        source, "_run_one_click_solver_candidate_scoring_loop_coordinator"
    )
    _, _, single_candidate_body = _function_segment(
        source, "_run_one_click_solver_single_candidate_scoring_flow_coordinator"
    )
    _, _, post_metric_body = _function_segment(
        source, "_run_one_click_solver_single_candidate_post_metric_scoring_flow_coordinator"
    )
    _, _, direction_material_dispatch_body = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_direction_material_gate_chain_from_post_metric_coordinator",
    )
    _, _, pre_selection_body = _function_segment(
        source, "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator"
    )

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "solver_delegates_iteration_loop": "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body,
        "pre_selection_delegates_candidate_scoring_loop": (
            "_dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator(" in pre_selection_body
        ),
        "scoring_loop_delegates_single_candidate_flow": (
            "_run_one_click_solver_single_candidate_scoring_flow_coordinator(" in scoring_loop_body
        ),
        "single_candidate_flow_delegates_post_metric_scoring_flow": (
            "_run_one_click_solver_single_candidate_post_metric_scoring_flow_coordinator(" in single_candidate_body
        ),
        "helper_present": (
            "def _handle_one_click_solver_candidate_direction_material_gate_chain_coordinator(" in source
        ),
        "helper_delegates_wrong_direction_first": (
            "_handle_one_click_solver_candidate_wrong_direction_gate_coordinator(" in helper
            and "_handle_one_click_solver_candidate_non_material_gate_coordinator(" in helper
            and helper.index("_handle_one_click_solver_candidate_wrong_direction_gate_coordinator(")
            < helper.index("_handle_one_click_solver_candidate_non_material_gate_coordinator(")
        ),
        "helper_short_circuits_wrong_direction_continue": (
            'if wrong_direction_gate_state["should_continue"]:' in helper
        ),
        "helper_delegates_non_material_gate": (
            "_handle_one_click_solver_candidate_non_material_gate_coordinator(" in helper
        ),
        "helper_returns_all_mutated_state": all(
            token in helper
            for token in (
                '"growth_candidates_rejected_in_tightening"',
                '"rejected_as_non_material_improvement"',
                '"shear_remove_links_candidate_dropped_reason"',
                '"shear_remove_links_candidate_materiality"',
                '"should_continue"',
            )
        ),
        "post_metric_flow_delegates_direction_material_gate_chain": (
            "_dispatch_one_click_solver_candidate_direction_material_gate_chain_from_post_metric_coordinator("
            in post_metric_body
        ),
        "post_metric_direction_material_dispatch_delegates_chain": (
            "_handle_one_click_solver_candidate_direction_material_gate_chain_coordinator("
            in direction_material_dispatch_body
            and "post_metric_scope[" in direction_material_dispatch_body
        ),
        "post_metric_flow_rehydrates_chain_state": all(
            token in post_metric_body
            for token in (
                'growth_candidates_rejected_in_tightening = direction_material_gate_chain_state[',
                'rejected_as_non_material_improvement = direction_material_gate_chain_state[',
                'shear_remove_links_candidate_dropped_reason = direction_material_gate_chain_state[',
                'shear_remove_links_candidate_materiality = direction_material_gate_chain_state[',
                'if direction_material_gate_chain_state["should_continue"]:',
            )
        ),
        "scoring_loop_no_longer_delegates_direction_material_gate_chain_directly": (
            "_handle_one_click_solver_candidate_direction_material_gate_chain_coordinator(" not in scoring_loop_body
        ),
        "solver_no_longer_inlines_wrong_or_non_material_gate": (
            "_handle_one_click_solver_candidate_wrong_direction_gate_coordinator(" not in solve_body
            and "_handle_one_click_solver_candidate_non_material_gate_coordinator(" not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_direction_material_gate_chain_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_candidate_direction_material_gate_chain_coordinator",
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
        "runtime": {"matches": runtime["matches"]},
        "product_behavior_changed": False,
        "next_safe_slice": "extract scored candidate assembly chain",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_candidate_direction_material_gate_chain_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_candidate_direction_material_gate_chain_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Candidate Direction Material Gate Chain Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Runtime",
            f"- Direction/material gate chain matches: `{payload['runtime']['matches']}`",
            "",
            "## Next Safe Slice",
            "",
            str(payload["next_safe_slice"]),
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
