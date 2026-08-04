"""Verify one-click solver non-governing domain-prune coordinator extraction."""

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
        "_one_click_domain_needs_cleanup": getattr(module, "_one_click_domain_needs_cleanup", None),
        "_trace_candidate_eval_domain_pre_eval_rejection_solver_coordinator": getattr(
            module,
            "_trace_candidate_eval_domain_pre_eval_rejection_solver_coordinator",
            None,
        ),
        "_COMPOUND_SHEAR_UPDATE_KEYS": getattr(module, "_COMPOUND_SHEAR_UPDATE_KEYS", None),
        "BEAM_STATUS_FAIL": getattr(module, "BEAM_STATUS_FAIL", None),
    }
    calls: list[dict[str, Any]] = []

    def _trace(**kwargs: Any) -> None:
        calls.append(
            {
                "reason": kwargs.get("rejection_reason"),
                "family": kwargs.get("family_hint"),
                "governing_domain": kwargs.get("governing_domain"),
                "updates": dict(kwargs.get("norm_u") or {}),
                "tightening": bool(kwargs.get("tightening_mode_active")),
            }
        )

    try:
        module._trace_candidate_eval_domain_pre_eval_rejection_solver_coordinator = _trace
        module._COMPOUND_SHEAR_UPDATE_KEYS = frozenset({"lig_d", "lig_legs", "s_lig"})
        module.BEAM_STATUS_FAIL = "FAIL"
        module._one_click_domain_needs_cleanup = lambda *_args, **_kwargs: False
        cleanup_pruned = module._handle_one_click_solver_non_governing_domain_prune_candidate_coordinator(
            step_idx=1,
            rc={"title": "Remove redundant shear", "action_type": "cleanup"},
            norm_u={"lig_d": 0},
            direction={"is_reduction_candidate": True},
            cur_eval={"overview": {"statuses": {"shear": "PASS"}}},
            mode_config=None,
            target_domains_for_band=["bending"],
            tightening_mode_active=True,
            governing_domain="bending",
            family_hint="non_governing_cleanup",
            rejected_as_non_governing_cleanup=2,
            rejected_as_non_governing_shear_strengthening=3,
            trace_callback=lambda *_args, **_kwargs: None,
        )

        module._one_click_domain_needs_cleanup = lambda *_args, **_kwargs: True
        cleanup_allowed = module._handle_one_click_solver_non_governing_domain_prune_candidate_coordinator(
            step_idx=2,
            rc={"title": "Shear cleanup still needed", "action_type": "cleanup"},
            norm_u={"lig_d": 0},
            direction={"is_reduction_candidate": True},
            cur_eval={"overview": {"statuses": {"shear": "FAIL"}}},
            mode_config=None,
            target_domains_for_band=["bending"],
            tightening_mode_active=False,
            governing_domain="bending",
            family_hint="non_governing_cleanup",
            rejected_as_non_governing_cleanup=2,
            rejected_as_non_governing_shear_strengthening=3,
            trace_callback=lambda *_args, **_kwargs: None,
        )

        strengthening_pruned = module._handle_one_click_solver_non_governing_domain_prune_candidate_coordinator(
            step_idx=3,
            rc={"title": "Add shear reinforcement", "action_type": "strengthen"},
            norm_u={"lig_d": 12},
            direction={"is_growth_only": True},
            cur_eval={"overview": {"statuses": {"shear": "PASS"}}},
            mode_config=None,
            target_domains_for_band=["bending"],
            tightening_mode_active=False,
            governing_domain="bending",
            family_hint="shear",
            rejected_as_non_governing_cleanup=2,
            rejected_as_non_governing_shear_strengthening=3,
            trace_callback=lambda *_args, **_kwargs: None,
        )

        strengthening_allowed = module._handle_one_click_solver_non_governing_domain_prune_candidate_coordinator(
            step_idx=4,
            rc={"title": "Shear fail strengthening", "action_type": "strengthen"},
            norm_u={"lig_d": 12},
            direction={"is_growth_only": True},
            cur_eval={"overview": {"statuses": {"shear": "FAIL"}}},
            mode_config=None,
            target_domains_for_band=["bending"],
            tightening_mode_active=False,
            governing_domain="bending",
            family_hint="shear",
            rejected_as_non_governing_cleanup=2,
            rejected_as_non_governing_shear_strengthening=3,
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
            elif hasattr(module, name):
                delattr(module, name)

    return {
        "cleanup_pruned": cleanup_pruned,
        "cleanup_allowed": cleanup_allowed,
        "strengthening_pruned": strengthening_pruned,
        "strengthening_allowed": strengthening_allowed,
        "calls": calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_non_governing_domain_prune_candidate_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    scoring_loop_start, scoring_loop_end, scoring_loop_body = _function_segment(
        source, "_run_one_click_solver_candidate_scoring_loop_coordinator"
    )
    _, _, single_candidate_body = _function_segment(
        source, "_run_one_click_solver_single_candidate_scoring_flow_coordinator"
    )
    _, _, pre_metric_body = _function_segment(
        source, "_run_one_click_solver_single_candidate_pre_metric_gate_flow_coordinator"
    )
    _, _, pre_selection_body = _function_segment(
        source, "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator"
    )
    _, _, pre_selection_pipeline_body = _function_segment(
        source,
        "_run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    runtime_checks = {
        "cleanup_pruned_preserved": runtime["cleanup_pruned"] == {
            "rejected_as_non_governing_cleanup": 3,
            "rejected_as_non_governing_shear_strengthening": 3,
            "should_continue": True,
        },
        "cleanup_allowed_preserved": runtime["cleanup_allowed"] == {
            "rejected_as_non_governing_cleanup": 2,
            "rejected_as_non_governing_shear_strengthening": 3,
            "should_continue": False,
        },
        "strengthening_pruned_preserved": runtime["strengthening_pruned"] == {
            "rejected_as_non_governing_cleanup": 2,
            "rejected_as_non_governing_shear_strengthening": 4,
            "should_continue": True,
        },
        "strengthening_allowed_preserved": runtime["strengthening_allowed"] == {
            "rejected_as_non_governing_cleanup": 2,
            "rejected_as_non_governing_shear_strengthening": 3,
            "should_continue": False,
        },
        "trace_reasons_preserved": runtime["calls"] == [
            {
                "reason": "non_governing_shear_cleanup_pruned",
                "family": "non_governing_cleanup",
                "governing_domain": "bending",
                "updates": {"lig_d": 0},
                "tightening": True,
            },
            {
                "reason": "non_governing_shear_strengthening_pruned",
                "family": "shear",
                "governing_domain": "bending",
                "updates": {"lig_d": 12},
                "tightening": False,
            },
        ],
    }
    static_checks = {
        "solver_delegates_iteration_loop": "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body,
        "pre_selection_delegates_candidate_scoring_loop": (
            "_run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator(" in pre_selection_body
            and "_dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator("
            in pre_selection_pipeline_body
        ),
        "scoring_loop_delegates_single_candidate_flow": (
            "_run_one_click_solver_single_candidate_scoring_flow_coordinator(" in scoring_loop_body
        ),
        "single_candidate_flow_delegates_pre_metric_gate_flow": (
            "_run_one_click_solver_single_candidate_pre_metric_gate_flow_coordinator(" in single_candidate_body
        ),
        "helper_present": "def _handle_one_click_solver_non_governing_domain_prune_candidate_coordinator(" in source,
        "helper_preserves_cleanup_condition": "touches_shear and not shear_cleanup_needed" in helper,
        "helper_preserves_strengthening_condition": "if not shear_fail_for_strengthen:" in helper,
        "helper_preserves_cleanup_reason": '"non_governing_shear_cleanup_pruned"' in helper,
        "helper_preserves_strengthening_reason": '"non_governing_shear_strengthening_pruned"' in helper,
        "helper_delegates_domain_trace": helper.count(
            "_trace_candidate_eval_domain_pre_eval_rejection_solver_coordinator("
        )
        == 2,
        "pre_metric_flow_delegates_domain_prune_branch": (
            "_handle_one_click_solver_non_governing_domain_prune_candidate_coordinator(" in pre_metric_body
        ),
        "pre_metric_flow_rehydrates_counters": (
            'rejected_as_non_governing_cleanup = domain_prune_state[' in pre_metric_body
            and 'rejected_as_non_governing_shear_strengthening = domain_prune_state[' in pre_metric_body
        ),
        "pre_metric_flow_preserves_continue_gate": (
            'if domain_prune_state["should_continue"]:' in pre_metric_body
        ),
        "scoring_loop_no_longer_delegates_domain_prune_directly": (
            "_handle_one_click_solver_non_governing_domain_prune_candidate_coordinator(" not in scoring_loop_body
        ),
        "solver_no_longer_inlines_domain_prune_branch": (
            '"non_governing_shear_cleanup_pruned"' not in solve_body
            and '"non_governing_shear_strengthening_pruned"' not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_non_governing_domain_prune_candidate_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_non_governing_domain_prune_candidate_coordinator",
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
        "next_safe_slice": "extract shear-governing pre-eval prune branch",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_non_governing_domain_prune_candidate_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_non_governing_domain_prune_candidate_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Non-Governing Domain-Prune Candidate Coordinator Extraction",
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
