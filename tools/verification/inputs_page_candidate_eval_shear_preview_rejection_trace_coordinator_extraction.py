"""Verify candidate-eval shear preview rejection trace coordinator extraction."""

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
        module._trace_candidate_eval_shear_preview_rejection_solver_coordinator(
            peval={
                "band": "tight",
                "overview": {"worst_util": 1.08, "statuses": {"shear": "FAIL"}},
            },
            mode_config={"mode": "tight"},
            step_idx=7,
            rc={"title": "Weak spacing", "action_type": "tighten"},
            norm_u={"s_lig": 80},
            new_d=0.19,
            governing_domain="shear",
            family_hint="spacing_reduction",
            rejection_reason="spacing_too_weak_for_shear_recovery",
            trace_callback=_trace_cb,
        )
    finally:
        if original_in_band is not None:
            module._candidate_in_target_band = original_in_band

    expected = [
        {
            "ev": "candidate_eval",
            "dat": {
                "step": 7,
                "label": "Weak spacing",
                "action_type": "tighten",
                "updates": {"s_lig": 80},
                "preview_util": 1.08,
                "preview_statuses": {"shear": "FAIL"},
                "reaches_target_band": True,
                "distance_to_band": 0.19,
                "duplicate_signature_rejected": False,
                "no_real_change_rejected": False,
                "evaluation_failed": False,
                "ranking_tuple": None,
                "tightening_mode_active": True,
                "governing_domain": "shear",
                "candidate_family": "spacing_reduction",
                "rejection_reason": "spacing_too_weak_for_shear_recovery",
            },
        }
    ]
    return {"calls": calls, "matches": calls == expected}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_trace_candidate_eval_shear_preview_rejection_solver_coordinator",
    )
    gate_start, gate_end, gate_body = _function_segment(
        source,
        "_handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _trace_candidate_eval_shear_preview_rejection_solver_coordinator(" in source,
        "helper_emits_candidate_eval_trace": 'trace_callback(\n        "candidate_eval",' in helper,
        "helper_preserves_preview_util": '"preview_util": float((peval.get("overview") or {}).get("worst_util", 0.0) or 0.0)' in helper,
        "helper_preserves_tightening_true": '"tightening_mode_active": True' in helper,
        "gate_delegates_three_shear_preview_rejections": gate_body.count(
            "_trace_candidate_eval_shear_preview_rejection_solver_coordinator("
        )
        == 3,
        "gate_preserves_spacing_reason": '"spacing_too_weak_for_shear_recovery"' in gate_body,
        "gate_preserves_web_reason": '"web_crushing_marginal"' in gate_body,
        "gate_preserves_layout_reason": '"impractical_shear_layout"' in gate_body,
        "gate_keeps_spacing_condition": "shear_util_preview is not None and shear_util_preview > 1.04" in gate_body,
        "gate_keeps_web_condition": "web_util_preview is not None and web_util_preview > 0.98" in gate_body,
        "gate_keeps_layout_condition": "s_new < 90.0 and legs_new >= 6 and dia_new >= 16 and not has_geometry_change" in gate_body,
        "solver_delegates_shear_preview_rejection_gate": (
            "_handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator(" in solve_body
        ),
        "solver_rehydrates_shear_preview_rejection_counters": (
            'rejected_as_spacing_too_weak = shear_preview_rejection_gate_state[' in solve_body
            and 'rejected_as_web_crushing_marginal = shear_preview_rejection_gate_state[' in solve_body
            and 'rejected_as_impractical_shear_layout = shear_preview_rejection_gate_state[' in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_eval_shear_preview_rejection_trace_coordinator",
        "helper_segment": {
            "function": "_trace_candidate_eval_shear_preview_rejection_solver_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "gate_segment": {
            "function": "_handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator",
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
        "next_safe_slice": "extract wrong-direction candidate trace coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_candidate_eval_shear_preview_rejection_trace_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_candidate_eval_shear_preview_rejection_trace_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Candidate Eval Shear Preview Rejection Trace Coordinator Extraction",
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
            f"- Shear preview rejection trace matches: `{payload['runtime']['matches']}`",
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
