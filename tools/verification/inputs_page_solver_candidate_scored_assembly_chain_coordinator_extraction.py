"""Verify candidate scored assembly chain coordinator extraction."""

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
    calls: list[dict[str, Any]] = []
    scored: list[dict[str, Any]] = [{"existing": True}]

    def _scoring(**kwargs: Any) -> dict[str, Any]:
        calls.append({"helper": "scoring", "web": kwargs["web_crushing_penalty_applied"]})
        return {
            "okp": True,
            "nib": True,
            "tier": 0,
            "has_target_domains": True,
            "new_max": 0.03,
            "new_total": 0.11,
            "prefer_total_before_max": True,
            "domain_progress": {"required_fail_count": 0},
            "required_fail_count": 0,
            "required_unsatisfied_count": 1,
            "mixed_rank": {"active": False},
            "sort_key": ("sort", 1),
            "dk": 0.12,
            "web_crushing_penalty_applied": int(kwargs["web_crushing_penalty_applied"]) + 1,
        }

    def _append(**kwargs: Any) -> dict[str, Any]:
        calls.append(
            {
                "helper": "append",
                "sort_key": kwargs["sort_key"],
                "nib": kwargs["nib"],
                "tier": kwargs["tier"],
                "domain_progress": kwargs["domain_progress"],
                "has_target_domains": kwargs["has_target_domains"],
                "dk": kwargs["dk"],
                "mixed_rank": kwargs["mixed_rank"],
            }
        )
        next_scored = list(kwargs["scored"])
        next_scored.append({"label": kwargs["rc"]["title"], "sort_key": kwargs["sort_key"]})
        return {"scored": next_scored}

    originals = _patch(
        module,
        {
            "_prepare_one_click_solver_candidate_scoring_state_coordinator": _scoring,
            "_handle_one_click_solver_candidate_scored_append_trace_coordinator": _append,
        },
    )
    try:
        returned = module._handle_one_click_solver_candidate_scored_assembly_chain_coordinator(
            scored=scored,
            peval={"overview": {}},
            cur_eval={"overview": {}},
            preview={"D": 650},
            mode_config={"mode": "tight"},
            step_idx=4,
            rc={"title": "Candidate"},
            norm_u={"D": 650},
            direction={"is_growth_only": True},
            psig=("sig",),
            new_u=0.91,
            cur_u=0.88,
            new_d=0.03,
            mixed_direction_mode=False,
            tightening_mode_active=True,
            governing_domain="bending",
            family_hint="depth",
            shear_util_preview=None,
            web_util_preview=None,
            cur_has_td=False,
            cur_required_fail_count=1,
            cur_required_unsatisfied_count=2,
            web_crushing_penalty_applied=5,
            material_improvement_threshold=0.01,
            trace_callback=lambda ev, dat: None,
        )
    finally:
        _restore(module, originals)

    return {
        "calls": calls,
        "returned": returned,
        "matches": (
            calls
            == [
                {"helper": "scoring", "web": 5},
                {
                    "helper": "append",
                    "sort_key": ("sort", 1),
                    "nib": True,
                    "tier": 0,
                    "domain_progress": {"required_fail_count": 0},
                    "has_target_domains": True,
                    "dk": 0.12,
                    "mixed_rank": {"active": False},
                },
            ]
            and returned == {
                "scored": [{"existing": True}, {"label": "Candidate", "sort_key": ("sort", 1)}],
                "web_crushing_penalty_applied": 6,
            }
        ),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_candidate_scored_assembly_chain_coordinator",
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
    _, _, scored_assembly_dispatch_body = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_scored_assembly_chain_from_post_metric_coordinator",
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
        "helper_present": "def _handle_one_click_solver_candidate_scored_assembly_chain_coordinator(" in source,
        "helper_delegates_scoring_before_append": (
            "_prepare_one_click_solver_candidate_scoring_state_coordinator(" in helper
            and "_handle_one_click_solver_candidate_scored_append_trace_coordinator(" in helper
            and helper.index("_prepare_one_click_solver_candidate_scoring_state_coordinator(")
            < helper.index("_handle_one_click_solver_candidate_scored_append_trace_coordinator(")
        ),
        "helper_rehydrates_ranking_fields_for_append": all(
            token in helper
            for token in (
                'nib = scoring_state["nib"]',
                'tier = scoring_state["tier"]',
                'has_target_domains = scoring_state["has_target_domains"]',
                'domain_progress = scoring_state["domain_progress"]',
                'mixed_rank = scoring_state["mixed_rank"]',
                'sort_key = scoring_state["sort_key"]',
                'dk = scoring_state["dk"]',
            )
        ),
        "helper_propagates_web_crushing_penalty": (
            'web_crushing_penalty_applied = scoring_state["web_crushing_penalty_applied"]' in helper
            and '"web_crushing_penalty_applied": web_crushing_penalty_applied' in helper
        ),
        "helper_returns_scored": '"scored": scored_append_trace_state["scored"]' in helper,
        "post_metric_flow_delegates_scored_assembly_chain": (
            "_dispatch_one_click_solver_candidate_scored_assembly_chain_from_post_metric_coordinator("
            in post_metric_body
        ),
        "post_metric_scored_assembly_dispatch_delegates_chain": (
            "_handle_one_click_solver_candidate_scored_assembly_chain_coordinator("
            in scored_assembly_dispatch_body
            and "post_metric_scope[" in scored_assembly_dispatch_body
        ),
        "post_metric_flow_rehydrates_scored_and_web_penalty": (
            'scored = scored_assembly_chain_state["scored"]' in post_metric_body
            and 'web_crushing_penalty_applied = scored_assembly_chain_state[' in post_metric_body
        ),
        "scoring_loop_no_longer_delegates_scored_assembly_chain_directly": (
            "_handle_one_click_solver_candidate_scored_assembly_chain_coordinator(" not in scoring_loop_body
        ),
        "solver_no_longer_inlines_scoring_or_append": (
            "_prepare_one_click_solver_candidate_scoring_state_coordinator(" not in solve_body
            and "_handle_one_click_solver_candidate_scored_append_trace_coordinator(" not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_scored_assembly_chain_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_candidate_scored_assembly_chain_coordinator",
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
        "next_safe_slice": "extract fallback candidate pool and trace block",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_candidate_scored_assembly_chain_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_candidate_scored_assembly_chain_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Candidate Scored Assembly Chain Coordinator Extraction",
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
            f"- Scored assembly chain matches: `{payload['runtime']['matches']}`",
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
