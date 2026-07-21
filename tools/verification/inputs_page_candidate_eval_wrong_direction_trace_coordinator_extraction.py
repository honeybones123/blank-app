"""Verify candidate-eval wrong-direction trace coordinator extraction."""

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
    original_in_band = getattr(module, "_candidate_in_target_band", None)
    calls: list[dict[str, Any]] = []

    def _fake_in_band(peval: dict, mode_config: dict) -> bool:
        return peval.get("band") == mode_config.get("mode")

    def _trace_cb(ev: str, dat: dict) -> None:
        calls.append({"ev": ev, "dat": dict(dat)})

    try:
        module._candidate_in_target_band = _fake_in_band
        module._trace_candidate_eval_wrong_direction_solver_coordinator(
            peval={
                "band": "tight",
                "overview": {"worst_util": 0.74, "statuses": {"bending": "PASS"}},
            },
            mode_config={"mode": "tight"},
            step_idx=8,
            rc={"title": "Wrong direction", "action_type": "loosen"},
            norm_u={"D": 550},
            new_d=0.15,
            direction={"is_reduction_candidate": False, "is_growth_only": True},
            governing_domain="bending",
            family_hint="depth",
            multi_domain_step_improves=False,
            all_pass_band_distance_improves=True,
            trace_callback=_trace_cb,
        )
    finally:
        if original_in_band is not None:
            module._candidate_in_target_band = original_in_band

    expected = [
        {
            "ev": "candidate_eval",
            "dat": {
                "step": 8,
                "label": "Wrong direction",
                "action_type": "loosen",
                "updates": {"D": 550},
                "preview_util": 0.74,
                "preview_statuses": {"bending": "PASS"},
                "reaches_target_band": True,
                "distance_to_band": 0.15,
                "duplicate_signature_rejected": False,
                "no_real_change_rejected": False,
                "evaluation_failed": False,
                "ranking_tuple": None,
                "tightening_mode_active": True,
                "reduction_candidate": False,
                "growth_candidate": True,
                "governing_domain": "bending",
                "candidate_family": "depth",
                "rejection_reason": "wrong_direction_reduction_mode",
                "multi_domain_step_improves": False,
                "all_pass_band_distance_improves": True,
            },
        }
    ]
    return {"calls": calls, "matches": calls == expected}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_trace_candidate_eval_wrong_direction_solver_coordinator",
    )
    gate_start, gate_end, gate_body = _function_segment(
        source,
        "_handle_one_click_solver_candidate_wrong_direction_gate_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _trace_candidate_eval_wrong_direction_solver_coordinator(" in source,
        "helper_emits_candidate_eval_trace": 'trace_callback(\n        "candidate_eval",' in helper,
        "helper_preserves_wrong_direction_reason": '"wrong_direction_reduction_mode"' in helper,
        "helper_preserves_multi_domain_flag": '"multi_domain_step_improves": bool(multi_domain_step_improves)' in helper,
        "helper_preserves_all_pass_flag": '"all_pass_band_distance_improves": bool(all_pass_band_distance_improves)' in helper,
        "gate_delegates_wrong_direction_trace": "_trace_candidate_eval_wrong_direction_solver_coordinator(" in gate_body,
        "gate_keeps_wrong_direction_condition": "and new_u < cur_u - 1e-6" in gate_body,
        "gate_keeps_growth_counter": "growth_candidates_rejected_in_tightening += 1" in gate_body,
        "solver_delegates_wrong_direction_gate": (
            "_handle_one_click_solver_candidate_wrong_direction_gate_coordinator(" in solve_body
        ),
        "solver_rehydrates_wrong_direction_counter": (
            'growth_candidates_rejected_in_tightening = wrong_direction_gate_state[' in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_eval_wrong_direction_trace_coordinator",
        "helper_segment": {
            "function": "_trace_candidate_eval_wrong_direction_solver_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "gate_segment": {
            "function": "_handle_one_click_solver_candidate_wrong_direction_gate_coordinator",
            "start_line": gate_start,
            "end_line": gate_end,
            "line_count": gate_end - gate_start + 1,
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
        "next_safe_slice": "extract non-material-improvement candidate trace coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_candidate_eval_wrong_direction_trace_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_candidate_eval_wrong_direction_trace_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Candidate Eval Wrong-Direction Trace Coordinator Extraction",
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
            f"- Wrong-direction trace matches: `{payload['runtime']['matches']}`",
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
