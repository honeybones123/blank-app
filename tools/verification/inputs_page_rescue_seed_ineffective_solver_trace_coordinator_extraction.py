"""Verify rescue-seed-ineffective solver trace coordinator extraction."""

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

    module._trace_rescue_seed_ineffective_solver_coordinator(
        seed_key="seed-1",
        rescue_family="shear",
        rescue_tier_requested="wide",
        tier="narrow",
        fallback_count=3,
        trace_callback=_trace,
    )
    expected = [
        {
            "ev": "rescue_seed_ineffective",
            "dat": {
                "seed_key": "seed-1",
                "family": "shear",
                "requested_tier": "wide",
                "used_tier": "narrow",
                "fallback_count": 3,
            },
        }
    ]
    return {"calls": calls, "matches": calls == expected}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_trace_rescue_seed_ineffective_solver_coordinator")
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    seed_loop_start, seed_loop_end, seed_loop = _function_segment(
        source,
        "_prepare_one_click_solver_rescue_seed_loop_state_coordinator",
    )
    _, _, finalization = _function_segment(
        source,
        "_finalize_one_click_solver_result_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _trace_rescue_seed_ineffective_solver_coordinator(" in source,
        "helper_emits_seed_ineffective_trace": 'trace_callback(\n        "rescue_seed_ineffective",' in helper,
        "helper_preserves_fallback_count_cast": '"fallback_count": int(fallback_count)' in helper,
        "seed_loop_delegates_seed_ineffective_trace": (
            "_trace_rescue_seed_ineffective_solver_coordinator(" in seed_loop
        ),
        "solver_delegates_rescue_seed_loop": (
            "_dispatch_one_click_solver_rescue_seed_result_from_finalization_coordinator("
            in finalization
        ),
        "solver_no_longer_inlines_seed_ineffective_trace": '_t(\n                    "rescue_seed_ineffective",' not in solve_body,
        "seed_loop_keeps_not_improved_branch": "if not improved:" in seed_loop,
        "seed_loop_keeps_ineffective_seed_mutation": "ineffective_seeds.append(seed_key)" in seed_loop,
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_rescue_seed_ineffective_trace_coordinator",
        "helper_segment": {
            "function": "_trace_rescue_seed_ineffective_solver_coordinator",
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
        "seed_loop_segment": {
            "function": "_prepare_one_click_solver_rescue_seed_loop_state_coordinator",
            "start_line": seed_loop_start,
            "end_line": seed_loop_end,
            "line_count": seed_loop_end - seed_loop_start + 1,
        },
        "static_checks": static_checks,
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract rescue exit trace coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_rescue_seed_ineffective_solver_trace_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_rescue_seed_ineffective_solver_trace_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Rescue Seed Ineffective Solver Trace Coordinator Extraction",
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
            f"- Rescue seed ineffective trace matches: `{payload['runtime']['matches']}`",
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
