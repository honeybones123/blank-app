"""Verify auto-design post-current-eval response context coordinator extraction."""

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
    originals = {
        "_publish_current_normalized_shear_truth_coordinator": getattr(
            module,
            "_publish_current_normalized_shear_truth_coordinator",
            None,
        ),
        "_build_one_click_base_steps_coordinator": getattr(module, "_build_one_click_base_steps_coordinator", None),
    }
    publishes: list[dict[str, Any]] = []
    base_calls: list[dict[str, Any]] = []
    try:
        module._publish_current_normalized_shear_truth_coordinator = lambda stage, dbg: publishes.append(
            {"stage": stage, "dbg": dict(dbg)},
        )
        module._build_one_click_base_steps_coordinator = lambda **kwargs: (
            base_calls.append(dict(kwargs)) or ["step-a", "step-b"]
        )
        result = module._prepare_auto_design_post_current_eval_response_context_coordinator(
            stop_reason="target_reached",
            step_count=4,
            init_u=1.4,
            fin_u=0.92,
            reached=True,
            dbg={"seed": "kept"},
            win_l="Winner",
            solver_final_updates={"D": 650},
            commit_blocked_reason=None,
            commit_rejected=False,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
    return {
        "result": result,
        "publishes": publishes,
        "base_calls": base_calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_auto_design_post_current_eval_response_context_coordinator",
    )
    tail_start, tail_end, tail = _function_segment(
        source,
        "_finish_auto_design_post_current_eval_and_dispatch_coordinator",
    )
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    base_call = runtime["base_calls"][0]
    runtime_checks = {
        "publish_stage_preserved": runtime["publishes"] == [
            {"stage": "run_one_click_auto_design:post_current_eval", "dbg": {"seed": "kept"}},
        ],
        "base_steps_args_preserved": base_call == {
            "stop_reason": "target_reached",
            "step_count": 4,
            "init_u": 1.4,
            "fin_u": 0.92,
            "reached": True,
            "dbg": {"seed": "kept"},
            "win_l": "Winner",
            "solver_final_updates": {"D": 650},
            "commit_blocked_reason": None,
            "commit_rejected": False,
        },
        "base_steps_returned": runtime["result"]["base_steps"] == ["step-a", "step-b"],
    }
    static_checks = {
        "helper_present": "def _prepare_auto_design_post_current_eval_response_context_coordinator(" in source,
        "helper_preserves_publish_stage": "run_one_click_auto_design:post_current_eval" in helper,
        "helper_preserves_base_steps_call": "_build_one_click_base_steps_coordinator(" in helper,
        "tail_delegates_post_current_eval_context": (
            "_prepare_auto_design_post_current_eval_response_context_coordinator(" in tail
        ),
        "tail_delegates_final_response_dispatch": (
            "_dispatch_auto_design_final_response_coordinator(" in tail
        ),
        "tail_preserves_post_current_before_dispatch_order": (
            tail.index("_prepare_auto_design_post_current_eval_response_context_coordinator(")
            < tail.index("_dispatch_auto_design_final_response_coordinator(")
        ),
        "run_delegates_final_tail": (
            "_finish_auto_design_post_current_eval_and_dispatch_coordinator(" in run_body
        ),
        "run_no_longer_delegates_post_current_eval_context_directly": (
            "_prepare_auto_design_post_current_eval_response_context_coordinator(" not in run_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_post_current_eval_response_context_coordinator",
        "helper_segment": {
            "function": "_prepare_auto_design_post_current_eval_response_context_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "tail_segment": {
            "function": "_finish_auto_design_post_current_eval_and_dispatch_coordinator",
            "start_line": tail_start,
            "end_line": tail_end,
            "line_count": tail_end - tail_start + 1,
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
        "next_safe_slice": "extract commit-rejected return branch from run_one_click_auto_design",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_auto_design_post_current_eval_response_context_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_auto_design_post_current_eval_response_context_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto Design Post-Current-Eval Response Context Coordinator Extraction",
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
