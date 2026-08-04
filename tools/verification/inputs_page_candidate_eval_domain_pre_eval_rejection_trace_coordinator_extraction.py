"""Verify candidate-eval domain pre-eval rejection trace coordinator extraction."""

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
    original_target_domains = getattr(module, "_one_click_target_domains_for_eval", None)
    calls: list[dict[str, Any]] = []

    def _fake_target_domains(target_domains_for_band: list[str], norm_u: dict) -> list[str]:
        return [f"{','.join(target_domains_for_band)}:{','.join(sorted(norm_u))}"]

    def _trace(ev: str, dat: dict) -> None:
        calls.append({"ev": ev, "dat": dict(dat)})

    try:
        module._one_click_target_domains_for_eval = _fake_target_domains
        module._trace_candidate_eval_domain_pre_eval_rejection_solver_coordinator(
            step_idx=4,
            rc={"title": "Domain prune", "action_type": "cleanup"},
            norm_u={"lig_d": 0},
            direction={"is_reduction_candidate": False, "is_growth_only": True},
            target_domains_for_band=["shear"],
            tightening_mode_active=False,
            governing_domain="bending",
            family_hint="shear",
            rejection_reason="non_governing_shear_strengthening_pruned",
            trace_callback=_trace,
        )
    finally:
        if original_target_domains is not None:
            module._one_click_target_domains_for_eval = original_target_domains

    expected = [
        {
            "ev": "candidate_eval",
            "dat": {
                "step": 4,
                "label": "Domain prune",
                "action_type": "cleanup",
                "updates": {"lig_d": 0},
                "preview_util": None,
                "preview_statuses": None,
                "reaches_target_band": None,
                "distance_to_band": None,
                "duplicate_signature_rejected": False,
                "no_real_change_rejected": False,
                "evaluation_failed": False,
                "ranking_tuple": None,
                "tightening_mode_active": False,
                "reduction_candidate": False,
                "growth_candidate": True,
                "governing_domain": "bending",
                "candidate_family": "shear",
                "rejection_reason": "non_governing_shear_strengthening_pruned",
                "target_domains_for_band": ["shear:lig_d"],
                "target_domain_for_band": None,
                "candidate_domain_utils": {},
            },
        }
    ]
    return {"calls": calls, "matches": calls == expected}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_trace_candidate_eval_domain_pre_eval_rejection_solver_coordinator",
    )
    branch_start, branch_end, branch_helper = _function_segment(
        source,
        "_handle_one_click_solver_non_governing_domain_prune_candidate_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _trace_candidate_eval_domain_pre_eval_rejection_solver_coordinator(" in source,
        "helper_delegates_to_pre_eval_rejection": "_trace_candidate_eval_pre_eval_rejection_solver_coordinator(" in helper,
        "helper_preserves_target_domains": "_one_click_target_domains_for_eval(target_domains_for_band, norm_u)" in helper,
        "helper_preserves_target_domain_none": '"target_domain_for_band": None' in helper,
        "helper_preserves_empty_domain_utils": '"candidate_domain_utils": {}' in helper,
        "branch_helper_delegates_domain_pre_eval_rejections": branch_helper.count(
            "_trace_candidate_eval_domain_pre_eval_rejection_solver_coordinator("
        )
        == 2,
        "branch_helper_preserves_cleanup_reason": '"non_governing_shear_cleanup_pruned"' in branch_helper,
        "branch_helper_preserves_strengthening_reason": '"non_governing_shear_strengthening_pruned"' in branch_helper,
        "branch_helper_keeps_cleanup_condition": "touches_shear and not shear_cleanup_needed" in branch_helper,
        "branch_helper_keeps_strengthening_condition": "if not shear_fail_for_strengthen:" in branch_helper,
        "solver_delegates_domain_prune_branch": (
            "_handle_one_click_solver_non_governing_domain_prune_candidate_coordinator(" in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_eval_domain_pre_eval_rejection_trace_coordinator",
        "helper_segment": {
            "function": "_trace_candidate_eval_domain_pre_eval_rejection_solver_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "branch_helper_segment": {
            "function": "_handle_one_click_solver_non_governing_domain_prune_candidate_coordinator",
            "start_line": branch_start,
            "end_line": branch_end,
            "line_count": branch_end - branch_start + 1,
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
        "next_safe_slice": "extract evaluation-failed candidate trace coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_candidate_eval_domain_pre_eval_rejection_trace_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_candidate_eval_domain_pre_eval_rejection_trace_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Candidate Eval Domain Pre-Eval Rejection Trace Coordinator Extraction",
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
            f"- Domain pre-eval rejection trace matches: `{payload['runtime']['matches']}`",
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
