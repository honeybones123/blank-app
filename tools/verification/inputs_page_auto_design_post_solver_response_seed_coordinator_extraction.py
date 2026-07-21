"""Verify auto-design post-solver response seed coordinator extraction."""

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


def _run_case(module: Any) -> dict[str, Any]:
    solve = {
        "final_updates": {"D": 650, "b": 300},
        "stop_reason": "target_reached",
        "step_count": 4,
        "initial_worst_util": 1.32,
        "final_worst_util": 0.96,
        "reached_target_band": True,
        "winning_label": "Increase depth",
        "winning_action_type": "geometry",
    }
    return module._prepare_auto_design_post_solver_response_seed_coordinator(solve=solve)


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_auto_design_post_solver_response_seed_coordinator",
    )
    post_solver_commit_start, post_solver_commit_end, post_solver_commit_body = _function_segment(
        source,
        "_run_auto_design_post_solver_commit_orchestration_coordinator",
    )
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    runtime_checks = {
        "commit_defaults_preserved": runtime["commit_audit"] is None
        and runtime["commit_rejected"] is False
        and runtime["commit_reject_reason"] is None
        and runtime["commit_blocked_reason"] is None
        and runtime["pre_commit_worst_util"] is None,
        "solver_updates_preserved": runtime["solver_final_updates"] == {"D": 650, "b": 300}
        and runtime["final_updates"] == {"D": 650, "b": 300}
        and runtime["solver_final_updates"] is runtime["final_updates"],
        "stop_reason_preserved": runtime["stop_reason"] == "target_reached"
        and runtime["solver_stop_reason"] == "target_reached",
        "solver_metrics_preserved": runtime["step_count"] == 4
        and runtime["init_u"] == 1.32
        and runtime["fin_u"] == 0.96
        and runtime["reached"] is True
        and runtime["win_l"] == "Increase depth"
        and runtime["win_at"] == "geometry",
    }
    static_checks = {
        "helper_present": "def _prepare_auto_design_post_solver_response_seed_coordinator(" in source,
        "helper_preserves_final_updates_copy": 'dict(solve.get("final_updates") or {})' in helper,
        "helper_preserves_stop_reason_normalization": 'str(solve.get("stop_reason") or "")' in helper,
        "helper_preserves_step_count_normalization": 'int(solve.get("step_count") or 0)' in helper,
        "helper_preserves_reached_normalization": 'bool(solve.get("reached_target_band"))' in helper,
        "post_solver_commit_delegates_post_solver_response_seed": (
            "_prepare_auto_design_post_solver_response_seed_coordinator(" in post_solver_commit_body
        ),
        "post_solver_commit_rehydrates_seed_fields": (
            'commit_audit: dict | None = post_solver_response_seed["commit_audit"]'
            in post_solver_commit_body
            and 'solver_final_updates = post_solver_response_seed["solver_final_updates"]'
            in post_solver_commit_body
            and 'win_at = post_solver_response_seed["win_at"]' in post_solver_commit_body
        ),
        "run_delegates_post_solver_commit_orchestration": (
            "_run_auto_design_post_solver_commit_orchestration_coordinator(" in run_body
        ),
        "run_no_longer_inlines_seed_dict_copy": 'solver_final_updates = dict(solve.get("final_updates") or {})'
        not in run_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_post_solver_response_seed_coordinator",
        "helper_segment": {
            "function": "_prepare_auto_design_post_solver_response_seed_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "post_solver_commit_segment": {
            "function": "_run_auto_design_post_solver_commit_orchestration_coordinator",
            "start_line": post_solver_commit_start,
            "end_line": post_solver_commit_end,
            "line_count": post_solver_commit_end - post_solver_commit_start + 1,
        },
        "run_segment": {
            "function": "run_one_click_auto_design",
            "start_line": run_start,
            "end_line": run_end,
            "line_count": run_end - run_start + 1,
        },
        "static_checks": static_checks,
        "runtime_checks": runtime_checks,
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "audit run_one_click_auto_design commit-orchestration block for mechanical extraction",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_post_solver_response_seed_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_post_solver_response_seed_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Post-Solver Response Seed Coordinator Extraction",
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
            "## Next Safe Slice",
            "",
            str(payload["next_safe_slice"]),
        ],
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
