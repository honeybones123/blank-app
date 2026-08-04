"""Verify target-band fallback scored-candidate extraction."""

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

from design_brain.candidate_evaluation import build_target_band_fallback_scored_candidate  # noqa: E402


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


def _old_row(next_hop_payload: dict[str, Any] | None, updates: dict[str, Any] | None, signature: Any = None) -> dict[str, Any] | None:
    if not updates:
        return None
    hop_eval = dict((next_hop_payload or {}).get("eval") or {})
    return {
        "sort_key": (-1,),
        "eval": hop_eval,
        "updates": dict(updates or {}),
        "label": "Fallback multi-domain cleanup",
        "action_type": "fallback_next_hop_cleanup",
        "signature": signature,
        "change_summary": None,
        "worst_util": float((hop_eval.get("overview") or {}).get("worst_util", 0.0) or 0.0),
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(AUTO_DESIGN_COMPUTE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, solve = _function_segment(inputs_source, "_solve_one_click_to_target")
    helper_start, helper_end, fallback_helper = _function_segment(
        inputs_source,
        "_handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator",
    )
    cases = [
        {
            "case": "standard_fallback",
            "next_hop_payload": {"eval": {"overview": {"worst_util": 0.74}}, "state": {"D": 650}},
            "updates": {"D": 650},
            "signature": "abc123",
        },
        {
            "case": "missing_worst_util_defaults_zero",
            "next_hop_payload": {"eval": {"overview": {}}, "state": {"b": 350}},
            "updates": {"b": 350},
            "signature": None,
        },
        {
            "case": "empty_updates_no_row",
            "next_hop_payload": {"eval": {"overview": {"worst_util": 0.8}}},
            "updates": {},
            "signature": "empty",
        },
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in cases:
        old = _old_row(case["next_hop_payload"], case["updates"], case["signature"])
        new = build_target_band_fallback_scored_candidate(
            next_hop_payload=case["next_hop_payload"],
            updates=case["updates"],
            signature=case["signature"],
        )
        row = {
            "case": str(case["case"]),
            "old": old,
            "new": new,
            "matches": old == new,
        }
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    service_present = "def build_target_band_fallback_scored_candidate(" in candidate_source
    page_delegates = "_build_target_band_fallback_scored_candidate(" in fallback_helper
    literal_row_removed = all(
        token not in solve
        for token in (
            '"label": "Fallback multi-domain cleanup"',
            '"action_type": "fallback_next_hop_cleanup"',
            '"sort_key": (-1,)',
            '"change_summary": None',
        )
    )
    page_keeps_injection_gate = (
        "fallback_next_hop_injected = True" in fallback_helper
        and "fallback_next_hop_reason =" in fallback_helper
    )
    page_keeps_signature_input = "_candidate_state_signature(hop_eval)" in fallback_helper
    page_keeps_update_diff_fallback = "_one_click_diff_accumulated_updates(" in fallback_helper
    solver_delegates_injection = (
        "_handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator(" in solve
    )
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
        or not service_present
        or not page_delegates
        or not literal_row_removed
        or not page_keeps_injection_gate
        or not page_keeps_signature_input
        or not page_keeps_update_diff_fallback
        or not solver_delegates_injection
        or forbidden_service_hits
    ):
        status = "FAIL"
    return {
        "status": status,
        "surface": "target_band_fallback_scored_candidate",
        "inputs_segment": {"function": "_solve_one_click_to_target", "start_line": start, "end_line": end},
        "fallback_injection_segment": {
            "function": "_handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
        },
        "case_count": len(cases),
        "mismatches": mismatches,
        "parity_rows": rows,
        "static_checks": {
            "service_present": service_present,
            "page_delegates": page_delegates,
            "literal_row_removed": literal_row_removed,
            "page_keeps_injection_gate": page_keeps_injection_gate,
            "page_keeps_signature_input": page_keeps_signature_input,
            "page_keeps_update_diff_fallback": page_keeps_update_diff_fallback,
            "solver_delegates_injection": solver_delegates_injection,
            "forbidden_service_hits": forbidden_service_hits,
        },
        "ownership": {
            "moved_to_candidate_evaluation": ["fallback scored-row materialisation"],
            "remains_page_owned": [
                "next-hop candidate generation and evaluation",
                "missing update diff fallback",
                "candidate signature input",
                "fallback injection trace flags",
            ],
            "temporary_solver_coordinator": [
                "_handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator",
            ],
        },
        "product_behavior_changed": False,
        "next_safe_slice": "audit next-hop candidate generation/evaluation boundary",
    }


def write_artifacts(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_fallback_scored_candidate_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_target_band_fallback_scored_candidate_extraction_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Target-Band Fallback Scored-Candidate Extraction",
        "",
        f"## Summary: {payload['status']}",
        "",
        "Moved fallback scored-row materialisation into `design_brain.candidate_evaluation.build_target_band_fallback_scored_candidate(...)`.",
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
