"""Verify one-click solver iteration scoring-start state coordinator extraction."""

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
        "_trace_iteration_start_solver_coordinator": getattr(module, "_trace_iteration_start_solver_coordinator", None),
        "_candidate_target_domains_for_band": getattr(module, "_candidate_target_domains_for_band", None),
        "_one_click_required_domain_progress": getattr(module, "_one_click_required_domain_progress", None),
    }
    calls: list[dict[str, Any]] = []

    def _trace_iteration_start(**kwargs: Any) -> None:
        calls.append(
            {
                "step_idx": kwargs.get("step_idx"),
                "domain_match_prune_used": kwargs.get("domain_match_prune_used"),
                "shear_prune_rule_source": kwargs.get("shear_prune_rule_source"),
                "pruned_non_shear_family_count": kwargs.get("pruned_non_shear_family_count"),
                "mixed_direction_mode": kwargs.get("mixed_direction_mode"),
            }
        )

    try:
        module._trace_iteration_start_solver_coordinator = _trace_iteration_start
        module._candidate_target_domains_for_band = lambda cur_eval: list(cur_eval.get("target_domains") or [])
        module._one_click_required_domain_progress = lambda cur_eval, mode_config: dict(
            cur_eval.get("progress") or {}
        )
        with_prune = module._prepare_one_click_solver_iteration_scoring_start_state_coordinator(
            step_idx=2,
            cur_sig=("a", "b"),
            working={"D": 600},
            cur_eval={
                "target_domains": ["bending", "shear"],
                "progress": {"required_fail_count": 1, "required_unsatisfied_count": 3},
            },
            t_lo=0.85,
            t_hi=0.95,
            tightening_mode_active=True,
            governing_domain="shear",
            material_improvement_threshold=0.01,
            tightening_step_count=1,
            max_tightening_steps=8,
            mode_config=None,
            no_actionable_after_full_tightening_search=False,
            shear_governing_mode_active=True,
            shear_severity_band="high",
            shear_candidate_family_order=["spacing"],
            shear_governing_family_detected=True,
            governing_family_exists_after_domain_fix=True,
            mixed_direction_mode="prefer_reduction",
            pruned_non_shear_family_count=5,
            domain_match_prune_used=True,
            shear_prune_rule_source=None,
            trace_callback=lambda *_args, **_kwargs: None,
        )
        no_target_domains = module._prepare_one_click_solver_iteration_scoring_start_state_coordinator(
            step_idx=3,
            cur_sig=("c",),
            working={"D": 650},
            cur_eval={"target_domains": [], "progress": {"required_fail_count": 9}},
            t_lo=0.85,
            t_hi=0.95,
            tightening_mode_active=False,
            governing_domain="bending",
            material_improvement_threshold=0.02,
            tightening_step_count=0,
            max_tightening_steps=8,
            mode_config=None,
            no_actionable_after_full_tightening_search=True,
            shear_governing_mode_active=False,
            shear_severity_band=None,
            shear_candidate_family_order=[],
            shear_governing_family_detected=False,
            governing_family_exists_after_domain_fix=False,
            mixed_direction_mode="mixed",
            pruned_non_shear_family_count=0,
            domain_match_prune_used=False,
            shear_prune_rule_source="existing",
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
            elif hasattr(module, name):
                delattr(module, name)

    return {
        "with_prune": with_prune,
        "no_target_domains": no_target_domains,
        "calls": calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_iteration_scoring_start_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    candidate_pipeline_start, candidate_pipeline_end, candidate_pipeline_body = _function_segment(
        source, "_prepare_one_click_solver_candidate_pipeline_state_coordinator"
    )
    _, _, after_collection_body = _function_segment(
        source,
        "_run_one_click_solver_candidate_pipeline_after_collection_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    runtime_checks = {
        "domain_match_source_finalized": runtime["with_prune"] == {
            "shear_prune_rule_source": "domain_matcher",
            "cur_has_td": True,
            "cur_required_fail_count": 1,
            "cur_required_unsatisfied_count": 3,
            "scored": [],
        },
        "no_target_domains_defaults_preserved": runtime["no_target_domains"] == {
            "shear_prune_rule_source": "existing",
            "cur_has_td": False,
            "cur_required_fail_count": 0,
            "cur_required_unsatisfied_count": 0,
            "scored": [],
        },
        "trace_handoff_preserved": runtime["calls"] == [
            {
                "step_idx": 2,
                "domain_match_prune_used": True,
                "shear_prune_rule_source": "domain_matcher",
                "pruned_non_shear_family_count": 5,
                "mixed_direction_mode": "prefer_reduction",
            },
            {
                "step_idx": 3,
                "domain_match_prune_used": False,
                "shear_prune_rule_source": "existing",
                "pruned_non_shear_family_count": 0,
                "mixed_direction_mode": "mixed",
            },
        ],
    }
    static_checks = {
        "solver_delegates_iteration_loop": "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body,
        "helper_present": "def _prepare_one_click_solver_iteration_scoring_start_state_coordinator(" in source,
        "helper_finalizes_shear_prune_source": (
            'shear_prune_rule_source = "domain_matcher" if domain_match_prune_used else shear_prune_rule_source'
            in helper
        ),
        "helper_delegates_iteration_start_trace": "_trace_iteration_start_solver_coordinator(" in helper,
        "helper_preserves_target_domain_progress": "cur_has_td = bool(_candidate_target_domains_for_band(cur_eval))"
        in helper
        and "_one_click_required_domain_progress(cur_eval, mode_config) if cur_has_td else {}" in helper,
        "helper_initializes_scored": '"scored": []' in helper,
        "solver_delegates_iteration_scoring_start_state": (
            "_prepare_one_click_solver_iteration_scoring_start_state_coordinator("
            in after_collection_body
        ),
        "solver_rehydrates_scoring_start_fields": (
            "candidate_pipeline_after_collection_scope.update(iteration_scoring_start_state)"
            in after_collection_body
            and '"cur_has_td": candidate_pipeline_scope["cur_has_td"]'
            in source
            and '"scored": candidate_pipeline_scope["scored"]' in source
        ),
        "solver_no_longer_directly_traces_iteration_start": "_trace_iteration_start_solver_coordinator(" not in solve_body,
        "solver_no_longer_initializes_scored_inline": "scored: list[dict] = []" not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_iteration_scoring_start_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_iteration_scoring_start_state_coordinator",
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
        "next_safe_slice": "extract candidate preview evaluation setup branch",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_iteration_scoring_start_state_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_iteration_scoring_start_state_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Iteration Scoring-Start State Coordinator Extraction",
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
