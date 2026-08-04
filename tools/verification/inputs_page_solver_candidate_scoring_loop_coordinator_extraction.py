"""Verify one-click solver candidate scoring loop coordinator extraction."""

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


def _run_case(module: Any) -> dict[str, Any]:
    calls: list[str] = []

    def _domain_prune(**kwargs: Any) -> dict[str, Any]:
        title = kwargs["rc"]["title"]
        calls.append(f"domain:{title}")
        return {
            "rejected_as_non_governing_cleanup": kwargs["rejected_as_non_governing_cleanup"] + 1,
            "rejected_as_non_governing_shear_strengthening": (
                kwargs["rejected_as_non_governing_shear_strengthening"] + 2
            ),
            "should_continue": title == "Pruned",
        }

    def _preview(**kwargs: Any) -> dict[str, Any]:
        title = kwargs["rc"]["title"]
        calls.append(f"preview:{title}")
        return {
            "peval": {"overview": {"all_key_pass": False}, "title": title},
            "preview": {"D": 650},
            "rejected_as_evaluation_failed": kwargs["rejected_as_evaluation_failed"] + 3,
            "should_continue": False,
        }

    def _target_domain(**kwargs: Any) -> dict[str, Any]:
        calls.append("target_domain")
        return {"peval": dict(kwargs["peval"], target_domains=["bending"]), "candidate_target_domains": ["bending"]}

    def _duplicate(**kwargs: Any) -> dict[str, Any]:
        calls.append("duplicate")
        return {
            "psig": ("accepted",),
            "rejected_as_duplicate_signature": kwargs["rejected_as_duplicate_signature"] + 4,
            "should_continue": False,
        }

    def _scalar(**kwargs: Any) -> dict[str, Any]:
        calls.append("scalar")
        return {
            "new_u": 0.9,
            "new_d": 0.04,
            "old_d": 0.08,
            "shear_preview": {"ok": True},
            "remove_links_candidate": True,
            "remove_links_truth_ok": True,
            "shear_util_preview": 0.71,
            "web_util_preview": 0.52,
        }

    def _shear_gate(**kwargs: Any) -> dict[str, Any]:
        calls.append("shear_gate")
        return {
            "remove_links_candidate": kwargs["remove_links_candidate"],
            "remove_links_truth_ok": kwargs["remove_links_truth_ok"],
            "shear_remove_links_candidate_seen": True,
            "shear_remove_links_candidate_truth_ok": True,
            "shear_remove_links_candidate_dropped_reason": "kept",
            "shear_remove_links_candidate_materiality": "material",
            "rejected_as_spacing_too_weak": kwargs["rejected_as_spacing_too_weak"] + 5,
            "rejected_as_web_crushing_marginal": kwargs["rejected_as_web_crushing_marginal"] + 6,
            "rejected_as_impractical_shear_layout": kwargs["rejected_as_impractical_shear_layout"] + 7,
            "should_continue": False,
        }

    def _direction_material(**kwargs: Any) -> dict[str, Any]:
        calls.append("direction_material")
        return {
            "growth_candidates_rejected_in_tightening": (
                kwargs["growth_candidates_rejected_in_tightening"] + 8
            ),
            "rejected_as_non_material_improvement": kwargs["rejected_as_non_material_improvement"] + 9,
            "shear_remove_links_candidate_dropped_reason": kwargs[
                "shear_remove_links_candidate_dropped_reason"
            ],
            "shear_remove_links_candidate_materiality": kwargs["shear_remove_links_candidate_materiality"],
            "should_continue": False,
        }

    def _scored_assembly(**kwargs: Any) -> dict[str, Any]:
        calls.append("scored_assembly")
        next_scored = list(kwargs["scored"])
        next_scored.append({"title": kwargs["rc"]["title"], "sig": kwargs["psig"]})
        return {
            "scored": next_scored,
            "web_crushing_penalty_applied": kwargs["web_crushing_penalty_applied"] + 10,
        }

    originals = _patch(
        module,
        {
            "_handle_one_click_solver_non_governing_domain_prune_candidate_coordinator": _domain_prune,
            "_prepare_one_click_solver_candidate_preview_eval_state_coordinator": _preview,
            "_prepare_one_click_solver_candidate_target_domain_attachment_state_coordinator": _target_domain,
            "_handle_one_click_solver_duplicate_signature_candidate_coordinator": _duplicate,
            "_prepare_one_click_solver_candidate_scalar_metric_state_coordinator": _scalar,
            "_handle_one_click_solver_candidate_shear_truth_and_preview_gate_coordinator": _shear_gate,
            "_handle_one_click_solver_candidate_direction_material_gate_chain_coordinator": _direction_material,
            "_handle_one_click_solver_candidate_scored_assembly_chain_coordinator": _scored_assembly,
        },
    )
    try:
        returned = module._run_one_click_solver_candidate_scoring_loop_coordinator(
            prepared=[
                {"rc": {"title": "Pruned"}, "raw_u": {}, "norm_u": {"D": 600}, "direction": {}, "family": "depth"},
                {"rc": {"title": "Accepted"}, "raw_u": {}, "norm_u": {"D": 650}, "direction": {}, "family": "depth"},
            ],
            step_idx=2,
            working={"D": 600},
            cur_eval={"overview": {}},
            mode_config=None,
            target_domains_for_band=["bending"],
            tightening_mode_active=True,
            governing_domain="bending",
            cur_shear_failing=False,
            target_band_domain="bending",
            seen_sigs=set(),
            cur_u=0.8,
            mixed_direction_mode=False,
            cur_has_td=True,
            cur_required_fail_count=1,
            cur_required_unsatisfied_count=2,
            material_improvement_threshold=0.01,
            scored=[],
            rejected_as_non_governing_cleanup=0,
            rejected_as_non_governing_shear_strengthening=0,
            rejected_as_evaluation_failed=0,
            rejected_as_duplicate_signature=0,
            rejected_as_non_material_improvement=0,
            growth_candidates_rejected_in_tightening=0,
            shear_remove_links_candidate_seen=False,
            shear_remove_links_candidate_truth_ok=False,
            shear_remove_links_candidate_dropped_reason=None,
            shear_remove_links_candidate_materiality="not_evaluated",
            rejected_as_spacing_too_weak=0,
            rejected_as_web_crushing_marginal=0,
            rejected_as_impractical_shear_layout=0,
            web_crushing_penalty_applied=0,
            trace_callback=lambda *_args, **_kwargs: None,
        )
    finally:
        _restore(module, originals)

    return {"calls": calls, "returned": returned}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_run_one_click_solver_candidate_scoring_loop_coordinator",
    )
    loop_result_start, loop_result_end, loop_result_helper = _function_segment(
        source,
        "_build_one_click_solver_candidate_scoring_loop_result_state_coordinator",
    )
    single_start, single_end, single_helper = _function_segment(
        source,
        "_run_one_click_solver_single_candidate_scoring_flow_coordinator",
    )
    _, _, single_result_helper = _function_segment(
        source,
        "_build_one_click_solver_single_candidate_scoring_flow_result_state_coordinator",
    )
    pre_metric_start, pre_metric_end, pre_metric_helper = _function_segment(
        source,
        "_run_one_click_solver_single_candidate_pre_metric_gate_flow_coordinator",
    )
    pre_metric_result_start, pre_metric_result_end, pre_metric_result_helper = _function_segment(
        source,
        "_build_one_click_solver_single_candidate_pre_metric_result_state_coordinator",
    )
    post_metric_start, post_metric_end, post_metric_helper = _function_segment(
        source,
        "_run_one_click_solver_single_candidate_post_metric_scoring_flow_coordinator",
    )
    _, _, post_metric_scalar_helper = _function_segment(
        source,
        "_prepare_one_click_solver_single_candidate_post_metric_scalar_state_coordinator",
    )
    post_metric_result_start, post_metric_result_end, post_metric_result_helper = _function_segment(
        source,
        "_build_one_click_solver_single_candidate_post_metric_scoring_result_state_coordinator",
    )
    _, _, post_metric_shear_dispatch_helper = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_shear_truth_preview_gate_from_post_metric_coordinator",
    )
    _, _, post_metric_direction_material_dispatch_helper = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_direction_material_gate_chain_from_post_metric_coordinator",
    )
    _, _, post_metric_scored_assembly_dispatch_helper = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_scored_assembly_chain_from_post_metric_coordinator",
    )
    loop_start, loop_end, loop_body = _function_segment(
        source,
        "_run_one_click_solver_iteration_loop_coordinator",
    )
    flow_start, flow_end, flow_body = _function_segment(
        source,
        "_run_one_click_solver_iteration_candidate_flow_coordinator",
    )
    pre_selection_start, pre_selection_end, pre_selection_body = _function_segment(
        source,
        "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator",
    )
    _, _, pre_selection_pipeline_and_scoring_body = _function_segment(
        source,
        "_run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator",
    )
    _, _, pre_selection_scoring_loop_dispatch_body = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    runtime_checks = {
        "continue_gate_and_accept_path_order_preserved": runtime["calls"]
        == [
            "domain:Pruned",
            "domain:Accepted",
            "preview:Accepted",
            "target_domain",
            "duplicate",
            "scalar",
            "shear_gate",
            "direction_material",
            "scored_assembly",
        ],
        "mutable_counters_and_scored_list_propagate": runtime["returned"]
        == {
            "scored": [{"title": "Accepted", "sig": ("accepted",)}],
            "rejected_as_non_governing_cleanup": 2,
            "rejected_as_non_governing_shear_strengthening": 4,
            "rejected_as_evaluation_failed": 3,
            "rejected_as_duplicate_signature": 4,
            "rejected_as_non_material_improvement": 9,
            "growth_candidates_rejected_in_tightening": 8,
            "shear_remove_links_candidate_seen": True,
            "shear_remove_links_candidate_truth_ok": True,
            "shear_remove_links_candidate_dropped_reason": "kept",
            "shear_remove_links_candidate_materiality": "material",
            "rejected_as_spacing_too_weak": 5,
            "rejected_as_web_crushing_marginal": 6,
            "rejected_as_impractical_shear_layout": 7,
            "web_crushing_penalty_applied": 10,
        },
    }
    pre_metric_tokens = [
        "_handle_one_click_solver_non_governing_domain_prune_candidate_coordinator(",
        "_prepare_one_click_solver_candidate_preview_eval_state_coordinator(",
        "_prepare_one_click_solver_candidate_target_domain_attachment_state_coordinator(",
        "_handle_one_click_solver_duplicate_signature_candidate_coordinator(",
    ]
    post_metric_tokens = [
        "_prepare_one_click_solver_single_candidate_post_metric_scalar_state_coordinator(",
        "_dispatch_one_click_solver_candidate_shear_truth_preview_gate_from_post_metric_coordinator(",
        "_dispatch_one_click_solver_candidate_direction_material_gate_chain_from_post_metric_coordinator(",
        "_dispatch_one_click_solver_candidate_scored_assembly_chain_from_post_metric_coordinator(",
    ]
    ordered_tokens = pre_metric_tokens + post_metric_tokens
    static_checks = {
        "helper_present": "def _run_one_click_solver_candidate_scoring_loop_coordinator(" in source,
        "single_helper_present": (
            "def _run_one_click_solver_single_candidate_scoring_flow_coordinator(" in source
        ),
        "pre_metric_helper_present": (
            "def _run_one_click_solver_single_candidate_pre_metric_gate_flow_coordinator(" in source
        ),
        "post_metric_helper_present": (
            "def _run_one_click_solver_single_candidate_post_metric_scoring_flow_coordinator(" in source
        ),
        "helper_owns_prepared_loop": "for entry in prepared:" in helper,
        "helper_delegates_single_candidate_flow": (
            "_run_one_click_solver_single_candidate_scoring_flow_coordinator(" in helper
        ),
        "helper_delegates_result_state_packing": (
            "_build_one_click_solver_candidate_scoring_loop_result_state_coordinator("
            in helper
            and "scoring_loop_scope=locals()" in helper
        ),
        "helper_no_longer_calls_candidate_gate_chain_directly": all(
            token not in helper for token in ordered_tokens
        ),
        "single_helper_delegates_pre_metric_gate_flow": (
            "_run_one_click_solver_single_candidate_pre_metric_gate_flow_coordinator(" in single_helper
        ),
        "single_helper_no_longer_calls_pre_metric_gates_directly": all(
            token not in single_helper for token in pre_metric_tokens
        ),
        "single_helper_delegates_post_metric_scoring_flow": (
            "_run_one_click_solver_single_candidate_post_metric_scoring_flow_coordinator(" in single_helper
        ),
        "single_helper_no_longer_calls_post_metric_gates_directly": all(
            token not in single_helper for token in post_metric_tokens
        ),
        "post_metric_helper_preserves_gate_order": (
            all(token in post_metric_helper for token in post_metric_tokens)
            and [post_metric_helper.index(token) for token in post_metric_tokens]
            == sorted(post_metric_helper.index(token) for token in post_metric_tokens)
            and "_prepare_one_click_solver_candidate_scalar_metric_state_coordinator("
            in post_metric_scalar_helper
        ),
        "post_metric_shear_dispatch_delegates_shear_truth_preview_gate": (
            "_handle_one_click_solver_candidate_shear_truth_and_preview_gate_coordinator("
            in post_metric_shear_dispatch_helper
            and "post_metric_scope[" in post_metric_shear_dispatch_helper
        ),
        "post_metric_direction_material_dispatch_delegates_gate_chain": (
            "_handle_one_click_solver_candidate_direction_material_gate_chain_coordinator("
            in post_metric_direction_material_dispatch_helper
            and "post_metric_scope[" in post_metric_direction_material_dispatch_helper
        ),
        "post_metric_scored_assembly_dispatch_delegates_gate_chain": (
            "_handle_one_click_solver_candidate_scored_assembly_chain_coordinator("
            in post_metric_scored_assembly_dispatch_helper
            and "post_metric_scope[" in post_metric_scored_assembly_dispatch_helper
        ),
        "pre_metric_helper_preserves_gate_order": (
            all(token in pre_metric_helper for token in pre_metric_tokens)
            and [pre_metric_helper.index(token) for token in pre_metric_tokens]
            == sorted(pre_metric_helper.index(token) for token in pre_metric_tokens)
        ),
        "loop_result_helper_returns_scoring_mutations": all(
            token in loop_result_helper
            for token in (
                '"scored": scoring_loop_scope["scored"]',
                '"rejected_as_non_governing_cleanup": scoring_loop_scope[',
                '"rejected_as_evaluation_failed": scoring_loop_scope[',
                '"rejected_as_duplicate_signature": scoring_loop_scope[',
                '"rejected_as_non_material_improvement": scoring_loop_scope[',
                '"growth_candidates_rejected_in_tightening": scoring_loop_scope[',
                '"web_crushing_penalty_applied": scoring_loop_scope[',
            )
        ),
        "single_helper_returns_scoring_mutations": (
            "_build_one_click_solver_single_candidate_scoring_flow_result_state_coordinator("
            in single_helper
            and all(
                token in single_result_helper
                for token in (
                    '"scored": scoring_flow_scope["scored"]',
                    '"rejected_as_non_governing_cleanup": scoring_flow_scope[',
                    '"rejected_as_evaluation_failed": scoring_flow_scope[',
                    '"rejected_as_duplicate_signature": scoring_flow_scope[',
                    '"rejected_as_non_material_improvement": scoring_flow_scope[',
                    '"growth_candidates_rejected_in_tightening": scoring_flow_scope[',
                    '"web_crushing_penalty_applied": scoring_flow_scope[',
                )
            )
        ),
        "pre_metric_helper_returns_gate_mutations": all(
            token in pre_metric_result_helper
            for token in (
                '"rc": pre_metric_scope["rc"]',
                '"norm_u": pre_metric_scope["norm_u"]',
                '"direction": pre_metric_scope["direction"]',
                '"family_hint": pre_metric_scope["family_hint"]',
                '"peval": peval',
                '"preview": preview',
                '"psig": psig',
                '"rejected_as_non_governing_cleanup": pre_metric_scope["rejected_as_non_governing_cleanup"]',
                '"rejected_as_evaluation_failed": pre_metric_scope["rejected_as_evaluation_failed"]',
                '"rejected_as_duplicate_signature": pre_metric_scope["rejected_as_duplicate_signature"]',
                '"should_continue": should_continue',
            )
        )
        and "_build_one_click_solver_single_candidate_pre_metric_result_state_coordinator("
        in pre_metric_helper,
        "post_metric_helper_delegates_result_state_packing": (
            "_build_one_click_solver_single_candidate_post_metric_scoring_result_state_coordinator("
            in post_metric_helper
            and "post_metric_scope=locals()" in post_metric_helper
        ),
        "post_metric_result_helper_returns_scoring_mutations": all(
            token in post_metric_result_helper
            for token in (
                '"scored": post_metric_scope["scored"]',
                '"rejected_as_non_governing_cleanup": post_metric_scope[',
                '"rejected_as_evaluation_failed": post_metric_scope[',
                '"rejected_as_duplicate_signature": post_metric_scope[',
                '"rejected_as_non_material_improvement": post_metric_scope[',
                '"growth_candidates_rejected_in_tightening": post_metric_scope[',
                '"web_crushing_penalty_applied": post_metric_scope[',
            )
        ),
        "pre_selection_delegates_candidate_scoring_loop": (
            "_run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator("
            in pre_selection_body
        ),
        "pre_selection_pipeline_and_scoring_delegates_scoring_loop": (
            "_dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator("
            in pre_selection_pipeline_and_scoring_body
        ),
        "pre_selection_scoring_loop_dispatch_delegates_candidate_scoring_loop": (
            "_run_one_click_solver_candidate_scoring_loop_coordinator("
            in pre_selection_scoring_loop_dispatch_body
            and "pre_selection_scope[" in pre_selection_scoring_loop_dispatch_body
        ),
        "pre_selection_rehydrates_scoring_loop_state": all(
            token in pre_selection_pipeline_and_scoring_body
            for token in (
                "scoring_loop_state = _dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator(",
                "pre_selection_scope.update(scoring_loop_state)",
                "_build_one_click_solver_pre_selection_candidate_evaluation_state_coordinator(",
            )
        ),
        "flow_delegates_pre_selection": (
            "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator(" in flow_body
        ),
        "flow_no_longer_calls_candidate_scoring_loop_directly": (
            "_run_one_click_solver_candidate_scoring_loop_coordinator(" not in flow_body
        ),
        "loop_delegates_candidate_flow": (
            "_dispatch_one_click_solver_iteration_candidate_flow_from_iteration_loop_coordinator("
            in loop_body
        ),
        "loop_no_longer_calls_candidate_scoring_loop_directly": (
            "_run_one_click_solver_candidate_scoring_loop_coordinator(" not in loop_body
        ),
        "solver_delegates_iteration_loop": "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body,
        "solver_no_longer_calls_candidate_scoring_loop_directly": (
            "_run_one_click_solver_candidate_scoring_loop_coordinator(" not in solve_body
        ),
        "solver_no_longer_owns_prepared_loop": "for entry in prepared:" not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_scoring_loop_coordinator",
        "helper_segment": {
            "function": "_run_one_click_solver_candidate_scoring_loop_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "loop_result_helper_segment": {
            "function": "_build_one_click_solver_candidate_scoring_loop_result_state_coordinator",
            "start_line": loop_result_start,
            "end_line": loop_result_end,
            "line_count": loop_result_end - loop_result_start + 1,
        },
        "single_helper_segment": {
            "function": "_run_one_click_solver_single_candidate_scoring_flow_coordinator",
            "start_line": single_start,
            "end_line": single_end,
            "line_count": single_end - single_start + 1,
        },
        "pre_metric_helper_segment": {
            "function": "_run_one_click_solver_single_candidate_pre_metric_gate_flow_coordinator",
            "start_line": pre_metric_start,
            "end_line": pre_metric_end,
            "line_count": pre_metric_end - pre_metric_start + 1,
        },
        "pre_metric_result_helper_segment": {
            "function": "_build_one_click_solver_single_candidate_pre_metric_result_state_coordinator",
            "start_line": pre_metric_result_start,
            "end_line": pre_metric_result_end,
            "line_count": pre_metric_result_end - pre_metric_result_start + 1,
        },
        "post_metric_helper_segment": {
            "function": "_run_one_click_solver_single_candidate_post_metric_scoring_flow_coordinator",
            "start_line": post_metric_start,
            "end_line": post_metric_end,
            "line_count": post_metric_end - post_metric_start + 1,
        },
        "post_metric_result_helper_segment": {
            "function": "_build_one_click_solver_single_candidate_post_metric_scoring_result_state_coordinator",
            "start_line": post_metric_result_start,
            "end_line": post_metric_result_end,
            "line_count": post_metric_result_end - post_metric_result_start + 1,
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
        "flow_segment": {
            "function": "_run_one_click_solver_iteration_candidate_flow_coordinator",
            "start_line": flow_start,
            "end_line": flow_end,
            "line_count": flow_end - flow_start + 1,
        },
        "pre_selection_segment": {
            "function": "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator",
            "start_line": pre_selection_start,
            "end_line": pre_selection_end,
            "line_count": pre_selection_end - pre_selection_start + 1,
        },
        "static_checks": static_checks,
        "runtime_checks": runtime_checks,
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "audit remaining solver loop into pre-scoring and selection orchestration slices",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_candidate_scoring_loop_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_candidate_scoring_loop_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Candidate Scoring Loop Coordinator Extraction",
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
    lines.extend(
        [
            "",
            "## Segments",
            f"- Helper lines: `{payload['helper_segment']['line_count']}`",
            f"- Solver lines: `{payload['solver_segment']['line_count']}`",
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
    print(f"status={payload['status']}")
    print(f"json={json_path}")
    print(f"md={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
