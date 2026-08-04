"""Verify target-band selected-candidate acceptance service extraction."""

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

from design_brain.candidate_evaluation import resolve_target_band_selected_candidate_acceptance  # noqa: E402


AUTO_DESIGN_COMPUTE = ROOT / "inputs_page_modules" / "auto_design_compute.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
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


def _old_acceptance(*, candidate_improves: bool, allow_in_band_shear_cleanup_candidate: bool) -> dict[str, Any]:
    if (not bool(candidate_improves)) and (not bool(allow_in_band_shear_cleanup_candidate)):
        return {
            "accepted": False,
            "stop_reason": "no_improving_candidate",
            "reason_code": "ranked_candidate_no_improvement",
        }
    return {
        "accepted": True,
        "stop_reason": None,
        "reason_code": "ranked_candidate_improves",
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(AUTO_DESIGN_COMPUTE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, target_loop = _function_segment(inputs_source, "_solve_one_click_to_target")
    gate_start, gate_end, gate_body = _function_segment(
        inputs_source,
        "_handle_one_click_solver_selected_candidate_acceptance_gate_coordinator",
    )
    cases = [
        {"case": "improves", "candidate_improves": True, "allow_in_band_shear_cleanup_candidate": False},
        {"case": "no_improve_but_shear_override", "candidate_improves": False, "allow_in_band_shear_cleanup_candidate": True},
        {"case": "no_improve_no_override", "candidate_improves": False, "allow_in_band_shear_cleanup_candidate": False},
        {"case": "improves_and_override", "candidate_improves": True, "allow_in_band_shear_cleanup_candidate": True},
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in cases:
        kwargs = {key: value for key, value in case.items() if key != "case"}
        old = _old_acceptance(**kwargs)
        new = resolve_target_band_selected_candidate_acceptance(**kwargs)
        row = {
            "case": str(case["case"]),
            "old": old,
            "new": new,
            "matches": old == new,
        }
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    old_inline_condition_removed = (
        "if not _one_click_step_improves(best[\"eval\"], cur_eval, mode_config) and not allow_in_band_shear_cleanup_candidate:"
        not in target_loop
    )
    service_present = "def resolve_target_band_selected_candidate_acceptance(" in candidate_source
    page_delegates = "_resolve_target_band_selected_candidate_acceptance(" in gate_body
    solver_delegates_gate = "_handle_one_click_solver_selected_candidate_acceptance_gate_coordinator(" in target_loop
    page_keeps_override_calculation = "_one_click_in_band_shear_cleanup_candidate_allowed(" in gate_body
    page_keeps_trace_strings = (
        "rank_lexicographic_then_no_improvement_exit" in inputs_source
        and "rank_lexicographic_min_tuple_one_click_step_improves_true" in inputs_source
    )
    page_keeps_stop_trace = "_trace_rejected_best_candidate_solver_stop_coordinator(" in gate_body
    forbidden_service_hits = [
        token
        for token in (
            "one_click",
            "import inputs_page",
            "from inputs_page",
            "import streamlit",
            "from streamlit",
            "st.session_state",
        )
        if token in candidate_source
    ]
    status = "PASS"
    if (
        mismatches
        or not old_inline_condition_removed
        or not service_present
        or not page_delegates
        or not solver_delegates_gate
        or not page_keeps_override_calculation
        or not page_keeps_trace_strings
        or not page_keeps_stop_trace
        or forbidden_service_hits
    ):
        status = "FAIL"
    return {
        "status": status,
        "surface": "target_band_selected_candidate_acceptance",
        "inputs_segment": {
            "function": "_solve_one_click_to_target",
            "start_line": start,
            "end_line": end,
        },
        "acceptance_gate_segment": {
            "function": "_handle_one_click_solver_selected_candidate_acceptance_gate_coordinator",
            "start_line": gate_start,
            "end_line": gate_end,
        },
        "case_count": len(cases),
        "mismatches": mismatches,
        "parity_rows": rows,
        "static_checks": {
            "service_present": service_present,
            "page_delegates": page_delegates,
            "solver_delegates_gate": solver_delegates_gate,
            "old_inline_condition_removed": old_inline_condition_removed,
            "page_keeps_override_calculation": page_keeps_override_calculation,
            "page_keeps_trace_strings": page_keeps_trace_strings,
            "page_keeps_stop_trace": page_keeps_stop_trace,
            "forbidden_service_hits": forbidden_service_hits,
        },
        "ownership": {
            "moved_to_candidate_evaluation": ["pure selected-candidate accept/reject decision from boolean inputs"],
            "remains_page_owned": [
                "shear override calculation",
                "old trace reason strings",
                "stop trace emission",
                "post-selection evaluation and working-state mutation",
            ],
        },
        "product_behavior_changed": False,
        "next_safe_slice": "audit/extract fallback next-hop injection or post-selection evaluation boundary separately",
    }


def write_artifacts(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_selected_candidate_acceptance_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_target_band_selected_candidate_acceptance_service_extraction_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Target-Band Selected-Candidate Acceptance Service Extraction",
        "",
        f"## Summary: {payload['status']}",
        "",
        "Moved only the pure selected-candidate accept/reject decision into `design_brain.candidate_evaluation.resolve_target_band_selected_candidate_acceptance(...)`.",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Parity", f"- Cases checked: `{payload['case_count']}`", f"- Mismatches: `{len(payload['mismatches'])}`", ""])
    lines.extend(["## Remaining Page-Owned Logic"])
    for item in payload["ownership"]["remains_page_owned"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Next Safe Slice", "", str(payload["next_safe_slice"]), "", f"JSON artifact: `{json_path}`"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    write_artifacts(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
