"""Verify initial blocked solver return coordinator extraction."""

from __future__ import annotations

import ast
import copy
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


def _old_payload(
    *,
    module: Any,
    initial_snapshot: dict[str, Any],
    initial_coherence: dict[str, Any],
    initial_pack_valid: bool,
    initial_stop_reason: str,
    rid: str | None,
    trace_callback,
) -> dict[str, Any]:
    trace_callback(
        "stop",
        {
            "stop_reason": initial_stop_reason,
            "status": "blocked",
            **module._coherence_debug_fields(initial_coherence),
            "canonical_pack_valid": initial_pack_valid,
            "canonical_pack_error": initial_snapshot.get("canonical_pack_error"),
            "canonical_pack_error_stage": initial_snapshot.get("canonical_pack_error_stage"),
        },
    )
    dbg_blocked = {
        "iteration_count": 0,
        "initial_worst_util": None,
        "final_worst_util": None,
        "target_band": {},
        "stop_reason": initial_stop_reason,
        "reached_target_band": False,
        "step_candidate_labels": [],
        "all_key_pass": False,
        "trace_run_id": rid,
        **module._coherence_debug_fields(initial_coherence),
        "canonical_pack_built": bool(initial_snapshot.get("canonical_pack_built")),
        "canonical_pack_valid": initial_pack_valid,
        "canonical_pack_source": initial_snapshot.get("canonical_pack_source"),
        "canonical_pack_error": initial_snapshot.get("canonical_pack_error"),
        "canonical_pack_error_stage": initial_snapshot.get("canonical_pack_error_stage"),
        "solver_blocked_by_incoherent_state": True,
    }
    return {
        "status": "blocked",
        "stop_reason": initial_stop_reason,
        "blocked_state_class": "hard_invalid",
        "step_count": 0,
        "initial_worst_util": None,
        "final_worst_util": None,
        "reached_target_band": False,
        "all_key_pass": False,
        "final_updates": {},
        "final_state_preview": copy.deepcopy(initial_snapshot),
        "step_trace": [],
        "winning_label": None,
        "winning_action_type": None,
        "one_click_solver_debug": dbg_blocked,
        "trace_run_id": rid,
    }


def _run_case(module: Any) -> dict[str, Any]:
    original_coherence_debug = getattr(module, "_coherence_debug_fields", None)
    original_copy = getattr(module, "copy", None)
    snapshot = {
        "canonical_pack_built": True,
        "canonical_pack_source": "unit",
        "canonical_pack_error": "bad_state",
        "canonical_pack_error_stage": "seed",
        "nested": {"value": 1},
    }
    coherence = {"coherence_should_block": True, "coherence_blocking_issues": ["bad_state"]}

    def _fake_coherence_debug_fields(value: dict[str, Any]) -> dict[str, Any]:
        return {
            "coherence_should_block": bool(value.get("coherence_should_block")),
            "coherence_blocking_issues": list(value.get("coherence_blocking_issues") or []),
        }

    old_traces: list[dict[str, Any]] = []
    new_traces: list[dict[str, Any]] = []

    def _old_trace(ev: str, dat: dict) -> None:
        old_traces.append({"ev": ev, "dat": dict(dat)})

    def _new_trace(ev: str, dat: dict) -> None:
        new_traces.append({"ev": ev, "dat": dict(dat)})

    try:
        module.copy = copy
        module._coherence_debug_fields = _fake_coherence_debug_fields
        old = _old_payload(
            module=module,
            initial_snapshot=snapshot,
            initial_coherence=coherence,
            initial_pack_valid=False,
            initial_stop_reason="bad_state",
            rid="trace-123",
            trace_callback=_old_trace,
        )
        new = module._build_initial_blocked_solver_return_coordinator(
            initial_snapshot=snapshot,
            initial_coherence=coherence,
            initial_pack_valid=False,
            initial_stop_reason="bad_state",
            rid="trace-123",
            trace_callback=_new_trace,
        )
    finally:
        if original_coherence_debug is not None:
            module._coherence_debug_fields = original_coherence_debug
        if original_copy is not None:
            module.copy = original_copy

    new["final_state_preview"]["nested"]["value"] = 2
    copy_isolated = snapshot["nested"]["value"] == 1
    new["final_state_preview"]["nested"]["value"] = 1
    return {
        "old": old,
        "new": new,
        "old_traces": old_traces,
        "new_traces": new_traces,
        "copy_isolated": copy_isolated,
        "matches": old == new and old_traces == new_traces and copy_isolated,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_build_initial_blocked_solver_return_coordinator")
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _build_initial_blocked_solver_return_coordinator(" in source,
        "helper_emits_stop_trace": 'trace_callback(\n        "stop"' in helper,
        "helper_preserves_blocked_status": '"status": "blocked"' in helper,
        "helper_preserves_hard_invalid_class": '"blocked_state_class": "hard_invalid"' in helper,
        "helper_preserves_debug_fields": all(
            token in helper
            for token in (
                "solver_blocked_by_incoherent_state",
                "canonical_pack_built",
                "canonical_pack_valid",
                "canonical_pack_source",
                "canonical_pack_error_stage",
            )
        ),
        "helper_preserves_deepcopy_preview": "copy.deepcopy(initial_snapshot)" in helper,
        "solver_delegates_initial_blocked_return": "_build_initial_blocked_solver_return_coordinator(" in solve_body,
        "solver_no_longer_assembles_dbg_blocked_inline": "dbg_blocked = {" not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_initial_blocked_return_coordinator",
        "helper_segment": {
            "function": "_build_initial_blocked_solver_return_coordinator",
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
        "runtime": {
            "matches": runtime["matches"],
            "trace_matches": runtime["old_traces"] == runtime["new_traces"],
            "copy_isolated": runtime["copy_isolated"],
        },
        "product_behavior_changed": False,
        "next_safe_slice": "extract evaluate_failed return assembly from _solve_one_click_to_target",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_initial_blocked_solver_return_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_initial_blocked_solver_return_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Initial Blocked Solver Return Coordinator Extraction",
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
            f"- Payload matches: `{payload['runtime']['matches']}`",
            f"- Trace matches: `{payload['runtime']['trace_matches']}`",
            f"- Preview copy isolated: `{payload['runtime']['copy_isolated']}`",
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
