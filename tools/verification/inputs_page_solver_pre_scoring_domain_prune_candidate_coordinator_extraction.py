"""Verify one-click solver pre-scoring domain-prune coordinator extraction."""

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
        "_one_click_candidate_is_shear_governing_for_prune": getattr(
            module,
            "_one_click_candidate_is_shear_governing_for_prune",
            None,
        ),
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
                "extra_fields": dict(kwargs.get("extra_fields") or {}),
            }
        )

    try:
        module._COMPOUND_SHEAR_UPDATE_KEYS = frozenset({"lig_d", "lig_legs", "s_lig"})
        module._trace_candidate_eval_pre_eval_rejection_solver_coordinator = _trace

        disabled = module._handle_one_click_solver_pre_scoring_domain_prune_candidate_coordinator(
            step_idx=0,
            rc={"title": "Disabled prune", "action_type": "noop"},
            norm_u={"D": 650},
            direction={},
            cur_eval={"overview": {"statuses": {"shear": "PASS"}}},
            mode_config=None,
            tightening_mode_active=False,
            governing_domain="bending",
            family_hint="shear",
            should_apply_domain_prune=False,
            shear_domain_prune_active=False,
            rejected_as_non_governing_cleanup=1,
            pruned_non_shear_family_count=2,
            domain_match_prune_used=False,
            shear_prune_rule_source=None,
            trace_callback=lambda *_args, **_kwargs: None,
        )

        bending_pruned = module._handle_one_click_solver_pre_scoring_domain_prune_candidate_coordinator(
            step_idx=1,
            rc={"title": "Bending rejects shear cleanup", "action_type": "cleanup"},
            norm_u={"lig_d": 0},
            direction={"is_reduction_candidate": True},
            cur_eval={"overview": {"statuses": {"shear": "PASS"}}},
            mode_config=None,
            tightening_mode_active=False,
            governing_domain="bending",
            family_hint="shear",
            should_apply_domain_prune=True,
            shear_domain_prune_active=False,
            rejected_as_non_governing_cleanup=1,
            pruned_non_shear_family_count=2,
            domain_match_prune_used=False,
            shear_prune_rule_source=None,
            trace_callback=lambda *_args, **_kwargs: None,
        )

        module._one_click_domain_needs_cleanup = lambda *_args, **_kwargs: True
        module._one_click_candidate_is_shear_governing_for_prune = lambda **_kwargs: False
        shear_cleanup_allowed = module._handle_one_click_solver_pre_scoring_domain_prune_candidate_coordinator(
            step_idx=2,
            rc={"title": "Shear cleanup needed", "action_type": "cleanup"},
            norm_u={"lig_d": 0},
            direction={"is_reduction_candidate": True},
            cur_eval={"overview": {"statuses": {"shear": "FAIL"}}},
            mode_config=None,
            tightening_mode_active=True,
            governing_domain="shear",
            family_hint="non_governing_cleanup",
            should_apply_domain_prune=True,
            shear_domain_prune_active=True,
            rejected_as_non_governing_cleanup=1,
            pruned_non_shear_family_count=2,
            domain_match_prune_used=False,
            shear_prune_rule_source=None,
            trace_callback=lambda *_args, **_kwargs: None,
        )

        module._one_click_domain_needs_cleanup = lambda *_args, **_kwargs: False
        module._one_click_candidate_is_shear_governing_for_prune = lambda **_kwargs: False
        shear_pruned = module._handle_one_click_solver_pre_scoring_domain_prune_candidate_coordinator(
            step_idx=3,
            rc={"title": "Non shear primary", "action_type": "geometry"},
            norm_u={"D": 650},
            direction={"is_growth_only": True},
            cur_eval={"overview": {"statuses": {"shear": "FAIL"}}},
            mode_config=None,
            tightening_mode_active=False,
            governing_domain="shear",
            family_hint="bottom_reo",
            should_apply_domain_prune=True,
            shear_domain_prune_active=True,
            rejected_as_non_governing_cleanup=1,
            pruned_non_shear_family_count=2,
            domain_match_prune_used=False,
            shear_prune_rule_source=None,
            trace_callback=lambda *_args, **_kwargs: None,
        )

        module._one_click_candidate_is_shear_governing_for_prune = lambda **_kwargs: True
        shear_allowed = module._handle_one_click_solver_pre_scoring_domain_prune_candidate_coordinator(
            step_idx=4,
            rc={"title": "Shear primary", "action_type": "shear"},
            norm_u={"lig_d": 12},
            direction={"is_growth_only": True},
            cur_eval={"overview": {"statuses": {"shear": "FAIL"}}},
            mode_config=None,
            tightening_mode_active=False,
            governing_domain="shear",
            family_hint="shear",
            should_apply_domain_prune=True,
            shear_domain_prune_active=True,
            rejected_as_non_governing_cleanup=1,
            pruned_non_shear_family_count=2,
            domain_match_prune_used=False,
            shear_prune_rule_source=None,
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
            elif hasattr(module, name):
                delattr(module, name)

    return {
        "disabled": disabled,
        "bending_pruned": bending_pruned,
        "shear_cleanup_allowed": shear_cleanup_allowed,
        "shear_pruned": shear_pruned,
        "shear_allowed": shear_allowed,
        "calls": calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_pre_scoring_domain_prune_candidate_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    _, _, pre_scoring_body = _function_segment(
        source,
        "_run_one_click_solver_pre_scoring_prune_pass_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    unchanged = {
        "rejected_as_non_governing_cleanup": 1,
        "pruned_non_shear_family_count": 2,
        "domain_match_prune_used": False,
        "shear_prune_rule_source": None,
        "should_continue": False,
    }
    runtime_checks = {
        "disabled_pass_through_preserved": runtime["disabled"] == unchanged,
        "bending_prune_preserved": runtime["bending_pruned"] == {
            "rejected_as_non_governing_cleanup": 2,
            "pruned_non_shear_family_count": 2,
            "domain_match_prune_used": False,
            "shear_prune_rule_source": None,
            "should_continue": True,
        },
        "shear_cleanup_allowed_preserved": runtime["shear_cleanup_allowed"] == unchanged,
        "shear_domain_prune_preserved": runtime["shear_pruned"] == {
            "rejected_as_non_governing_cleanup": 2,
            "pruned_non_shear_family_count": 3,
            "domain_match_prune_used": True,
            "shear_prune_rule_source": "domain_matcher",
            "should_continue": True,
        },
        "shear_candidate_allowed_preserved": runtime["shear_allowed"] == unchanged,
        "trace_reasons_preserved": runtime["calls"] == [
            {
                "reason": "non_governing_cleanup_pruned",
                "family": "shear",
                "governing_domain": "bending",
                "updates": {"lig_d": 0},
                "tightening": True,
                "extra_fields": {},
            },
            {
                "reason": "shear_governing_pruned_non_shear_primary",
                "family": "bottom_reo",
                "governing_domain": "shear",
                "updates": {"D": 650},
                "tightening": True,
                "extra_fields": {
                    "shear_prune_rule_source": "domain_matcher",
                    "domain_match_prune_used": True,
                },
            },
        ],
    }
    static_checks = {
        "helper_present": "def _handle_one_click_solver_pre_scoring_domain_prune_candidate_coordinator(" in source,
        "helper_preserves_bending_prune_families": "shear_spacing_layout_cleanup" in helper
        and "shear_adjust" in helper,
        "helper_preserves_shear_cleanup_candidate_gate": "shear_cleanup_candidate = bool(" in helper
        and "_one_click_domain_needs_cleanup(cur_eval, \"shear\", mode_config)" in helper,
        "helper_preserves_shear_governing_prune_gate": (
            "not _one_click_candidate_is_shear_governing_for_prune(" in helper
        ),
        "helper_preserves_domain_match_flags": 'domain_match_prune_used = True' in helper
        and 'shear_prune_rule_source = "domain_matcher"' in helper,
        "helper_preserves_trace_reasons": '"non_governing_cleanup_pruned"' in helper
        and '"shear_governing_pruned_non_shear_primary"' in helper,
        "solver_delegates_pre_scoring_domain_prune_branch": (
            "_handle_one_click_solver_pre_scoring_domain_prune_candidate_coordinator(" in pre_scoring_body
        ),
        "solver_rehydrates_flags": (
            'pruned_non_shear_family_count = pre_scoring_domain_prune_state[' in pre_scoring_body
            and 'domain_match_prune_used = pre_scoring_domain_prune_state["domain_match_prune_used"]' in pre_scoring_body
            and 'shear_prune_rule_source = pre_scoring_domain_prune_state["shear_prune_rule_source"]' in pre_scoring_body
        ),
        "solver_preserves_continue_gate": 'if pre_scoring_domain_prune_state["should_continue"]:' in pre_scoring_body,
        "solver_no_longer_inlines_pre_scoring_domain_prune_reasons": (
            '"non_governing_cleanup_pruned"' not in solve_body
            and '"shear_governing_pruned_non_shear_primary"' not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_pre_scoring_domain_prune_candidate_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_pre_scoring_domain_prune_candidate_coordinator",
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
        "next_safe_slice": "extract generic shear cleanup pre-eval prune branch",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_pre_scoring_domain_prune_candidate_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_pre_scoring_domain_prune_candidate_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Pre-Scoring Domain-Prune Candidate Coordinator Extraction",
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
