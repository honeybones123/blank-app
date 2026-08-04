"""Verify candidate-eval duplicate-signature trace coordinator extraction."""

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
    original_trace = getattr(module, "_one_click_trace_eval_domain_payload", None)
    original_in_band = getattr(module, "_candidate_in_target_band", None)
    calls: list[dict[str, Any]] = []

    def _fake_trace(peval: dict, mode_config: dict) -> dict[str, Any]:
        return {"domain_payload": [peval.get("domain"), mode_config.get("mode")]}

    def _fake_in_band(peval: dict, mode_config: dict) -> bool:
        return peval.get("band") == mode_config.get("mode")

    def _trace_cb(ev: str, dat: dict) -> None:
        calls.append({"ev": ev, "dat": dict(dat)})

    try:
        module._one_click_trace_eval_domain_payload = _fake_trace
        module._candidate_in_target_band = _fake_in_band
        module._trace_candidate_eval_duplicate_signature_solver_coordinator(
            peval={
                "domain": "shear",
                "band": "tight",
                "overview": {"worst_util": 0.91, "statuses": {"shear": "PASS"}},
            },
            mode_config={"mode": "tight"},
            step_idx=6,
            rc={"title": "Duplicate", "action_type": "tighten"},
            norm_u={"D": 700},
            new_d=0.04,
            direction={"is_reduction_candidate": True, "is_growth_only": False},
            tightening_mode_active=True,
            governing_domain="shear",
            family_hint="depth",
            trace_callback=_trace_cb,
        )
    finally:
        if original_trace is not None:
            module._one_click_trace_eval_domain_payload = original_trace
        if original_in_band is not None:
            module._candidate_in_target_band = original_in_band

    expected = [
        {
            "ev": "candidate_eval",
            "dat": {
                "domain_payload": ["shear", "tight"],
                "step": 6,
                "label": "Duplicate",
                "action_type": "tighten",
                "updates": {"D": 700},
                "preview_util": 0.91,
                "preview_statuses": {"shear": "PASS"},
                "reaches_target_band": True,
                "distance_to_band": 0.04,
                "duplicate_signature_rejected": True,
                "no_real_change_rejected": False,
                "evaluation_failed": False,
                "ranking_tuple": None,
                "tightening_mode_active": True,
                "reduction_candidate": True,
                "growth_candidate": False,
                "governing_domain": "shear",
                "candidate_family": "depth",
                "rejection_reason": "duplicate_signature",
            },
        }
    ]
    return {"calls": calls, "matches": calls == expected}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_trace_candidate_eval_duplicate_signature_solver_coordinator",
    )
    branch_start, branch_end, branch_helper = _function_segment(
        source,
        "_handle_one_click_solver_duplicate_signature_candidate_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _trace_candidate_eval_duplicate_signature_solver_coordinator(" in source,
        "helper_emits_candidate_eval_trace": 'trace_callback(\n        "candidate_eval",' in helper,
        "helper_preserves_domain_payload": "_one_click_trace_eval_domain_payload(peval, mode_config)" in helper,
        "helper_preserves_duplicate_marker": '"duplicate_signature_rejected": True' in helper,
        "helper_preserves_rejection_reason": '"duplicate_signature"' in helper,
        "branch_helper_delegates_duplicate_signature_trace": (
            "_trace_candidate_eval_duplicate_signature_solver_coordinator(" in branch_helper
        ),
        "branch_helper_keeps_signature_gate": "if psig and psig in seen_sigs:" in branch_helper,
        "branch_helper_keeps_duplicate_counter": "rejected_as_duplicate_signature += 1" in branch_helper,
        "solver_delegates_duplicate_signature_branch": (
            "_handle_one_click_solver_duplicate_signature_candidate_coordinator(" in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_eval_duplicate_signature_trace_coordinator",
        "helper_segment": {
            "function": "_trace_candidate_eval_duplicate_signature_solver_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "branch_helper_segment": {
            "function": "_handle_one_click_solver_duplicate_signature_candidate_coordinator",
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
        "next_safe_slice": "extract shear preview candidate rejection trace coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_candidate_eval_duplicate_signature_trace_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_candidate_eval_duplicate_signature_trace_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Candidate Eval Duplicate-Signature Trace Coordinator Extraction",
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
            f"- Duplicate-signature trace matches: `{payload['runtime']['matches']}`",
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
