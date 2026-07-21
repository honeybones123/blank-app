"""Verify one-click solver shear cleanup pre-eval prune coordinator extraction."""

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
        "_COMPOUND_SHEAR_UPDATE_KEYS": getattr(module, "_COMPOUND_SHEAR_UPDATE_KEYS", None),
        "_one_click_domain_needs_cleanup": getattr(module, "_one_click_domain_needs_cleanup", None),
        "_trace_candidate_eval_pre_eval_rejection_solver_coordinator": getattr(
            module,
            "_trace_candidate_eval_pre_eval_rejection_solver_coordinator",
            None,
        ),
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
        module._COMPOUND_SHEAR_UPDATE_KEYS = frozenset({"lig_d", "lig_legs", "s_lig"})
        module._trace_candidate_eval_pre_eval_rejection_solver_coordinator = _trace

        module._one_click_domain_needs_cleanup = lambda *_args, **_kwargs: False
        pruned = module._handle_one_click_solver_shear_cleanup_pre_eval_prune_candidate_coordinator(
            step_idx=1,
            rc={"title": "Cleanup not needed", "action_type": "cleanup"},
            norm_u={"lig_d": 0},
            direction={"is_reduction_candidate": True},
            cur_eval={"overview": {"statuses": {"shear": "PASS"}}},
            mode_config=None,
            tightening_mode_active=False,
            governing_domain="shear",
            family_hint="non_governing_cleanup",
            rejected_as_non_governing_cleanup=4,
            trace_callback=lambda *_args, **_kwargs: None,
        )

        module._one_click_domain_needs_cleanup = lambda *_args, **_kwargs: True
        allowed = module._handle_one_click_solver_shear_cleanup_pre_eval_prune_candidate_coordinator(
            step_idx=2,
            rc={"title": "Cleanup needed", "action_type": "cleanup"},
            norm_u={"lig_d": 0},
            direction={"is_reduction_candidate": True},
            cur_eval={"overview": {"statuses": {"shear": "FAIL"}}},
            mode_config=None,
            tightening_mode_active=True,
            governing_domain="shear",
            family_hint="non_governing_cleanup",
            rejected_as_non_governing_cleanup=4,
            trace_callback=lambda *_args, **_kwargs: None,
        )

        non_shear = module._handle_one_click_solver_shear_cleanup_pre_eval_prune_candidate_coordinator(
            step_idx=3,
            rc={"title": "Bending candidate", "action_type": "geometry"},
            norm_u={"D": 650},
            direction={"is_growth_only": True},
            cur_eval={"overview": {"statuses": {"shear": "PASS"}}},
            mode_config=None,
            tightening_mode_active=False,
            governing_domain="bending",
            family_hint="non_governing_cleanup",
            rejected_as_non_governing_cleanup=4,
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
            elif hasattr(module, name):
                delattr(module, name)

    return {
        "pruned": pruned,
        "allowed": allowed,
        "non_shear": non_shear,
        "calls": calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_shear_cleanup_pre_eval_prune_candidate_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    unchanged = {
        "rejected_as_non_governing_cleanup": 4,
        "should_continue": False,
    }
    runtime_checks = {
        "prune_preserved": runtime["pruned"] == {
            "rejected_as_non_governing_cleanup": 5,
            "should_continue": True,
        },
        "cleanup_needed_allowed": runtime["allowed"] == unchanged,
        "non_shear_pass_through": runtime["non_shear"] == unchanged,
        "trace_reason_preserved": runtime["calls"] == [
            {
                "reason": "shear_cleanup_family_pruned",
                "family": "non_governing_cleanup",
                "governing_domain": "shear",
                "updates": {"lig_d": 0},
                "tightening": False,
            }
        ],
    }
    static_checks = {
        "helper_present": "def _handle_one_click_solver_shear_cleanup_pre_eval_prune_candidate_coordinator("
        in source,
        "helper_preserves_cleanup_family_detection": 'family_hint == "non_governing_cleanup"' in helper
        and '"cleanup" in family_hint' in helper
        and 'family_hint.endswith("_cleanup")' in helper,
        "helper_preserves_shear_touch_gate": "touches_shear_cleanup = bool(set(norm_u) & _COMPOUND_SHEAR_UPDATE_KEYS)"
        in helper,
        "helper_preserves_cleanup_needed_gate": '_one_click_domain_needs_cleanup(cur_eval, "shear", mode_config)'
        in helper,
        "helper_preserves_counter_and_trace": "rejected_as_non_governing_cleanup += 1" in helper
        and '"shear_cleanup_family_pruned"' in helper
        and "_trace_candidate_eval_pre_eval_rejection_solver_coordinator(" in helper,
        "solver_delegates_shear_cleanup_prune_branch": (
            "_handle_one_click_solver_shear_cleanup_pre_eval_prune_candidate_coordinator(" in solve_body
        ),
        "solver_rehydrates_counter": (
            'rejected_as_non_governing_cleanup = shear_cleanup_prune_state[' in solve_body
        ),
        "solver_preserves_continue_gate": 'if shear_cleanup_prune_state["should_continue"]:' in solve_body,
        "solver_no_longer_inlines_shear_cleanup_prune_reason": (
            '"shear_cleanup_family_pruned"' not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_shear_cleanup_pre_eval_prune_candidate_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_shear_cleanup_pre_eval_prune_candidate_coordinator",
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
        "next_safe_slice": "extract growth-blocked-in-tightening pre-eval prune branch",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_shear_cleanup_pre_eval_prune_candidate_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_shear_cleanup_pre_eval_prune_candidate_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Shear Cleanup Pre-Eval Prune Candidate Coordinator Extraction",
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
