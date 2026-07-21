"""Verify candidate-eval pre-eval rejection trace coordinator extraction."""

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
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _run_case(module: Any) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []

    def _trace(ev: str, dat: dict) -> None:
        calls.append({"ev": ev, "dat": dict(dat)})

    module._trace_candidate_eval_pre_eval_rejection_solver_coordinator(
        step_idx=3,
        rc={"title": "Candidate A", "action_type": "tighten"},
        norm_u={"D": 650},
        direction={"is_reduction_candidate": True, "is_growth_only": False},
        tightening_mode_active=True,
        governing_domain="shear",
        family_hint="spacing",
        rejection_reason="shear_governing_pruned_non_shear_primary",
        extra_fields={"domain_match_prune_used": True},
        trace_callback=_trace,
    )
    expected = [
        {
            "ev": "candidate_eval",
            "dat": {
                "step": 3,
                "label": "Candidate A",
                "action_type": "tighten",
                "updates": {"D": 650},
                "preview_util": None,
                "preview_statuses": None,
                "reaches_target_band": None,
                "distance_to_band": None,
                "duplicate_signature_rejected": False,
                "no_real_change_rejected": False,
                "evaluation_failed": False,
                "ranking_tuple": None,
                "tightening_mode_active": True,
                "reduction_candidate": True,
                "growth_candidate": False,
                "governing_domain": "shear",
                "candidate_family": "spacing",
                "rejection_reason": "shear_governing_pruned_non_shear_primary",
                "domain_match_prune_used": True,
            },
        }
    ]
    return {"calls": calls, "matches": calls == expected}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_trace_candidate_eval_pre_eval_rejection_solver_coordinator",
    )
    pre_scoring_start, pre_scoring_end, pre_scoring_helper = _function_segment(
        source,
        "_handle_one_click_solver_pre_scoring_domain_prune_candidate_coordinator",
    )
    shear_cleanup_start, shear_cleanup_end, shear_cleanup_helper = _function_segment(
        source,
        "_handle_one_click_solver_shear_cleanup_pre_eval_prune_candidate_coordinator",
    )
    growth_start, growth_end, growth_helper = _function_segment(
        source,
        "_handle_one_click_solver_growth_blocked_pre_eval_prune_candidate_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _trace_candidate_eval_pre_eval_rejection_solver_coordinator(" in source,
        "helper_emits_candidate_eval_trace": 'trace_callback("candidate_eval", payload)' in helper,
        "helper_preserves_preview_none": '"preview_util": None' in helper,
        "helper_preserves_ranking_none": '"ranking_tuple": None' in helper,
        "helper_supports_extra_fields": "payload.update(extra_fields)" in helper,
        "solver_delegates_pre_eval_rejections": solve_body.count(
            "_trace_candidate_eval_pre_eval_rejection_solver_coordinator("
        )
        == 0,
        "pre_scoring_helper_delegates_pre_eval_rejections": pre_scoring_helper.count(
            "_trace_candidate_eval_pre_eval_rejection_solver_coordinator("
        )
        == 2,
        "shear_cleanup_helper_delegates_pre_eval_rejection": shear_cleanup_helper.count(
            "_trace_candidate_eval_pre_eval_rejection_solver_coordinator("
        )
        == 1,
        "growth_helper_delegates_pre_eval_rejection": growth_helper.count(
            "_trace_candidate_eval_pre_eval_rejection_solver_coordinator("
        )
        == 1,
        "pre_scoring_helper_preserves_shear_prune_reason": (
            '"shear_governing_pruned_non_shear_primary"' in pre_scoring_helper
        ),
        "pre_scoring_helper_preserves_bending_prune_reason": (
            '"non_governing_cleanup_pruned"' in pre_scoring_helper
        ),
        "shear_cleanup_helper_preserves_cleanup_reason": (
            '"shear_cleanup_family_pruned"' in shear_cleanup_helper
        ),
        "growth_helper_preserves_growth_reason": (
            '"growth_blocked_in_tightening_mode"' in growth_helper
        ),
        "solver_moved_each_pre_eval_reason_once": (
            pre_scoring_helper.count('"shear_governing_pruned_non_shear_primary"') == 1
            and pre_scoring_helper.count('"non_governing_cleanup_pruned"') == 1
            and shear_cleanup_helper.count('"shear_cleanup_family_pruned"') == 1
            and growth_helper.count('"growth_blocked_in_tightening_mode"') == 1
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_eval_pre_eval_rejection_trace_coordinator",
        "helper_segment": {
            "function": "_trace_candidate_eval_pre_eval_rejection_solver_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "pre_scoring_helper_segment": {
            "function": "_handle_one_click_solver_pre_scoring_domain_prune_candidate_coordinator",
            "start_line": pre_scoring_start,
            "end_line": pre_scoring_end,
            "line_count": pre_scoring_end - pre_scoring_start + 1,
        },
        "shear_cleanup_helper_segment": {
            "function": "_handle_one_click_solver_shear_cleanup_pre_eval_prune_candidate_coordinator",
            "start_line": shear_cleanup_start,
            "end_line": shear_cleanup_end,
            "line_count": shear_cleanup_end - shear_cleanup_start + 1,
        },
        "growth_helper_segment": {
            "function": "_handle_one_click_solver_growth_blocked_pre_eval_prune_candidate_coordinator",
            "start_line": growth_start,
            "end_line": growth_end,
            "line_count": growth_end - growth_start + 1,
        },
        "solver_segment": {
            "function": "_solve_one_click_to_target",
            "start_line": solve_start,
            "end_line": solve_end,
            "line_count": solve_end - solve_start + 1,
        },
        "static_checks": static_checks,
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract domain pre-eval candidate rejection trace coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_candidate_eval_pre_eval_rejection_trace_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_candidate_eval_pre_eval_rejection_trace_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Candidate Eval Pre-Eval Rejection Trace Coordinator Extraction",
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
            f"- Pre-eval rejection trace matches: `{payload['runtime']['matches']}`",
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
