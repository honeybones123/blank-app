"""Verify pre-scoring prune pass solver coordinator extraction."""

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
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
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


def _run_case(module: Any) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []

    prepared = [
        {
            "family": "no_real",
            "rc": {"title": "A", "raw_updates": {"source": "rc-no-real"}},
            "raw_u": {"source": "entry-no-real"},
            "norm_u": {"A": 1},
            "direction": {"kind": "same"},
        },
        {
            "family": "domain",
            "rc": {"title": "B", "raw_updates": {"source": "rc-domain"}},
            "raw_u": {"source": "entry-domain"},
            "norm_u": {"B": 2},
            "direction": {"kind": "domain"},
        },
        {
            "family": "cleanup",
            "rc": {"title": "C", "raw_updates": {"source": "rc-cleanup"}},
            "raw_u": {"source": "entry-cleanup"},
            "norm_u": {"C": 3},
            "direction": {"kind": "cleanup"},
        },
        {
            "family": "growth",
            "rc": {"title": "D", "raw_updates": {"source": "rc-growth"}},
            "raw_u": {"source": "entry-growth"},
            "norm_u": {"D": 4},
            "direction": {"kind": "growth"},
        },
        {
            "family": "pass",
            "rc": {"title": "E", "raw_updates": {"source": "rc-pass"}},
            "raw_u": {"source": "entry-pass"},
            "norm_u": {"E": 5},
            "direction": {"kind": "pass"},
        },
    ]

    def _family(kwargs: dict[str, Any]) -> str:
        return str(kwargs.get("family_hint") or "")

    def _no_real(**kwargs: Any) -> dict[str, Any]:
        family = _family(kwargs)
        calls.append({"helper": "no_real", "family": family, "raw_u": dict(kwargs["raw_u"])})
        rejected = int(kwargs["rejected_as_no_real_change"])
        if family == "no_real":
            return {
                "rejected_as_no_real_change": rejected + 1,
                "shear_remove_links_candidate_seen": True,
                "shear_remove_links_candidate_dropped_reason": "no_real_change",
                "should_continue": True,
            }
        return {
            "rejected_as_no_real_change": rejected,
            "shear_remove_links_candidate_seen": kwargs["shear_remove_links_candidate_seen"],
            "shear_remove_links_candidate_dropped_reason": kwargs[
                "shear_remove_links_candidate_dropped_reason"
            ],
            "should_continue": False,
        }

    def _domain(**kwargs: Any) -> dict[str, Any]:
        family = _family(kwargs)
        calls.append({"helper": "domain", "family": family})
        cleanup = int(kwargs["rejected_as_non_governing_cleanup"])
        pruned = int(kwargs["pruned_non_shear_family_count"])
        if family == "domain":
            return {
                "rejected_as_non_governing_cleanup": cleanup + 1,
                "pruned_non_shear_family_count": pruned + 1,
                "domain_match_prune_used": True,
                "shear_prune_rule_source": "domain_matcher",
                "should_continue": True,
            }
        return {
            "rejected_as_non_governing_cleanup": cleanup,
            "pruned_non_shear_family_count": pruned,
            "domain_match_prune_used": kwargs["domain_match_prune_used"],
            "shear_prune_rule_source": kwargs["shear_prune_rule_source"],
            "should_continue": False,
        }

    def _shear_cleanup(**kwargs: Any) -> dict[str, Any]:
        family = _family(kwargs)
        calls.append({"helper": "shear_cleanup", "family": family})
        cleanup = int(kwargs["rejected_as_non_governing_cleanup"])
        if family == "cleanup":
            return {"rejected_as_non_governing_cleanup": cleanup + 1, "should_continue": True}
        return {"rejected_as_non_governing_cleanup": cleanup, "should_continue": False}

    def _growth(**kwargs: Any) -> dict[str, Any]:
        family = _family(kwargs)
        calls.append({"helper": "growth", "family": family})
        rejected = int(kwargs["growth_candidates_rejected_in_tightening"])
        if family == "growth":
            return {"growth_candidates_rejected_in_tightening": rejected + 1, "should_continue": True}
        return {"growth_candidates_rejected_in_tightening": rejected, "should_continue": False}

    replacements = {
        "_handle_one_click_solver_no_real_change_candidate_coordinator": _no_real,
        "_handle_one_click_solver_pre_scoring_domain_prune_candidate_coordinator": _domain,
        "_handle_one_click_solver_shear_cleanup_pre_eval_prune_candidate_coordinator": _shear_cleanup,
        "_handle_one_click_solver_growth_blocked_pre_eval_prune_candidate_coordinator": _growth,
    }
    originals = _patch(module, replacements)
    try:
        returned = module._run_one_click_solver_pre_scoring_prune_pass_coordinator(
            prepared=prepared,
            step_idx=2,
            working={"D": 600},
            cur_eval={"overview": {}},
            mode_config={"mode": "tight"},
            tightening_mode_active=True,
            governing_domain="shear",
            should_apply_domain_prune=True,
            shear_domain_prune_active=True,
            reduction_candidates_considered=3,
            rejected_as_no_real_change=10,
            shear_remove_links_candidate_seen=False,
            shear_remove_links_candidate_dropped_reason=None,
            rejected_as_non_governing_cleanup=20,
            pruned_non_shear_family_count=30,
            domain_match_prune_used=False,
            shear_prune_rule_source=None,
            growth_candidates_rejected_in_tightening=40,
            trace_callback=lambda ev, dat: None,
        )
    finally:
        _restore(module, originals)

    expected_order = [
        ("no_real", "no_real"),
        ("no_real", "domain"),
        ("domain", "domain"),
        ("no_real", "cleanup"),
        ("domain", "cleanup"),
        ("shear_cleanup", "cleanup"),
        ("no_real", "growth"),
        ("domain", "growth"),
        ("shear_cleanup", "growth"),
        ("growth", "growth"),
        ("no_real", "pass"),
        ("domain", "pass"),
        ("shear_cleanup", "pass"),
        ("growth", "pass"),
    ]
    raw_precedence_ok = calls[0]["raw_u"] == {"source": "rc-no-real"}
    expected_return = {
        "rejected_as_no_real_change": 11,
        "shear_remove_links_candidate_seen": True,
        "shear_remove_links_candidate_dropped_reason": "no_real_change",
        "rejected_as_non_governing_cleanup": 22,
        "pruned_non_shear_family_count": 31,
        "domain_match_prune_used": True,
        "shear_prune_rule_source": "domain_matcher",
        "growth_candidates_rejected_in_tightening": 41,
    }
    return {
        "calls": calls,
        "returned": returned,
        "matches": (
            [(call["helper"], call["family"]) for call in calls] == expected_order
            and raw_precedence_ok
            and returned == expected_return
        ),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_run_one_click_solver_pre_scoring_prune_pass_coordinator",
    )
    result_helper_start, result_helper_end, result_helper = _function_segment(
        source,
        "_build_one_click_solver_pre_scoring_prune_pass_result_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    candidate_pipeline_start, candidate_pipeline_end, candidate_pipeline_body = _function_segment(
        source, "_prepare_one_click_solver_candidate_pipeline_state_coordinator"
    )
    _, _, after_collection_body = _function_segment(
        source,
        "_run_one_click_solver_candidate_pipeline_after_collection_coordinator",
    )
    _, _, pre_scoring_body = _function_segment(
        source,
        "_prepare_one_click_solver_candidate_pipeline_pre_scoring_state_coordinator",
    )

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "solver_delegates_iteration_loop": "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body,
        "helper_present": "def _run_one_click_solver_pre_scoring_prune_pass_coordinator(" in source,
        "helper_iterates_prepared": "for entry in prepared:" in helper,
        "helper_preserves_rc_raw_update_precedence": 'raw_u = dict(rc["raw_updates"])' in helper,
        "helper_delegates_no_real_change": "_handle_one_click_solver_no_real_change_candidate_coordinator(" in helper,
        "helper_delegates_pre_scoring_domain_prune": (
            "_handle_one_click_solver_pre_scoring_domain_prune_candidate_coordinator(" in helper
        ),
        "helper_delegates_shear_cleanup_prune": (
            "_handle_one_click_solver_shear_cleanup_pre_eval_prune_candidate_coordinator(" in helper
        ),
        "helper_delegates_growth_prune": (
            "_handle_one_click_solver_growth_blocked_pre_eval_prune_candidate_coordinator(" in helper
        ),
        "helper_returns_all_mutated_counters": all(
            token in result_helper
            for token in (
                '"rejected_as_no_real_change"',
                '"shear_remove_links_candidate_seen"',
                '"shear_remove_links_candidate_dropped_reason"',
                '"rejected_as_non_governing_cleanup"',
                '"pruned_non_shear_family_count"',
                '"domain_match_prune_used"',
                '"shear_prune_rule_source"',
                '"growth_candidates_rejected_in_tightening"',
            )
        )
        and "_build_one_click_solver_pre_scoring_prune_pass_result_state_coordinator("
        in helper,
        "candidate_pipeline_delegates_pre_scoring_state": (
            "_prepare_one_click_solver_candidate_pipeline_pre_scoring_state_coordinator("
            in after_collection_body
        ),
        "pre_scoring_state_delegates_pre_scoring_prune_pass": (
            "_run_one_click_solver_pre_scoring_prune_pass_coordinator(" in pre_scoring_body
        ),
        "candidate_pipeline_rehydrates_prune_pass_state": (
            "candidate_pipeline_after_collection_scope.update(pre_scoring_state)"
            in after_collection_body
        )
        and all(
            token in source
            for token in (
                '"rejected_as_no_real_change": candidate_pipeline_scope[',
                '"shear_remove_links_candidate_seen": candidate_pipeline_scope[',
                '"rejected_as_non_governing_cleanup": candidate_pipeline_scope[',
                '"growth_candidates_rejected_in_tightening": candidate_pipeline_scope[',
            )
        ),
        "solver_no_longer_inlines_no_real_change_pass": (
            "_handle_one_click_solver_no_real_change_candidate_coordinator(" not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_pre_scoring_prune_pass_coordinator",
        "helper_segment": {
            "function": "_run_one_click_solver_pre_scoring_prune_pass_coordinator",
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
        "result_helper_segment": {
            "function": "_build_one_click_solver_pre_scoring_prune_pass_result_state_coordinator",
            "start_line": result_helper_start,
            "end_line": result_helper_end,
            "line_count": result_helper_end - result_helper_start + 1,
        },
        "static_checks": static_checks,
        "runtime": {"matches": runtime["matches"]},
        "product_behavior_changed": False,
        "next_safe_slice": "extract candidate scoring loop coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_pre_scoring_prune_pass_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_pre_scoring_prune_pass_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Pre-Scoring Prune Pass Coordinator Extraction",
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
            f"- Pre-scoring prune pass matches: `{payload['runtime']['matches']}`",
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
