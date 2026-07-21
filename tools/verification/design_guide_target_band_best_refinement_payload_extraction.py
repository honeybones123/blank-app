"""Verify target-band best refinement payload selector extraction."""

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

from design_brain.candidate_evaluation import select_target_band_best_refinement_payload  # noqa: E402


INPUTS = ROOT / "inputs_page_app_contract_bridge.py"
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


def _old_select(current_best: dict[str, Any] | None, candidate_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    best_payload = dict(current_best) if isinstance(current_best, dict) else None
    payload = dict(candidate_payload) if isinstance(candidate_payload, dict) else None
    if payload is None:
        return best_payload
    if best_payload is None or float(payload["distance"]) < float(best_payload["distance"]) - 1e-9:
        best_payload = payload
    return best_payload


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, helper = _function_segment(inputs_source, "_one_click_best_next_hop_improving_candidate")
    cases = [
        ("first_candidate", None, {"distance": 0.2, "label": "first"}),
        ("better_candidate", {"distance": 0.4, "label": "old"}, {"distance": 0.2, "label": "new"}),
        ("worse_candidate", {"distance": 0.2, "label": "old"}, {"distance": 0.4, "label": "new"}),
        ("tie_candidate", {"distance": 0.2, "label": "old"}, {"distance": 0.2, "label": "new"}),
        ("within_margin_candidate", {"distance": 0.2, "label": "old"}, {"distance": 0.1999999995, "label": "new"}),
        ("missing_candidate", {"distance": 0.2, "label": "old"}, None),
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for name, current_best, candidate in cases:
        old = _old_select(current_best, candidate)
        new = select_target_band_best_refinement_payload(current_best, candidate)
        row = {
            "case": name,
            "old": old,
            "new": new,
            "matches": old == new,
        }
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    service_present = "def select_target_band_best_refinement_payload(" in candidate_source
    page_delegates = (
        "_select_target_band_best_refinement_payload(best_payload, payload)" in helper
        or "_select_best_target_band_refinement_candidate(" in helper
    )
    old_inline_selector_removed = "if best_payload is None or float(payload[\"distance\"])" not in helper
    generator_loop_retained = all(
        token in helper
        for token in (
            "for candidate_state in candidate_states:",
            "evaluate_candidate_full(",
        )
    ) or all(
        token in helper
        for token in (
            "_select_best_target_band_refinement_candidate(",
            "evaluator_fn=evaluate_candidate_full",
            "state_pack_fn=_build_canonical_design_state_pack",
            "target_domain_attachment_fn=_one_click_attach_eval_target_domains",
        )
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
        or not old_inline_selector_removed
        or not generator_loop_retained
        or forbidden_service_hits
    ):
        status = "FAIL"
    return {
        "status": status,
        "surface": "target_band_best_refinement_payload_selector",
        "inputs_segment": {"function": "_one_click_best_next_hop_improving_candidate", "start_line": start, "end_line": end},
        "case_count": len(cases),
        "mismatches": mismatches,
        "parity_rows": rows,
        "static_checks": {
            "service_present": service_present,
            "page_delegates": page_delegates,
            "old_inline_selector_removed": old_inline_selector_removed,
            "generator_loop_retained": generator_loop_retained,
            "forbidden_service_hits": forbidden_service_hits,
        },
        "ownership": {
            "moved_to_candidate_evaluation": ["best refinement payload selection by lower distance"],
            "remains_page_owned": [
                "auto-design context construction",
                "refinement candidate generation",
                "canonical state pack callback",
                "full candidate evaluator callback",
                "target-domain attachment callback",
                "spacing-envelope callback",
            ],
        },
        "product_behavior_changed": False,
        "next_safe_slice": "extract or bound auto-design context construction and refinement candidate generation",
    }


def write_artifacts(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_best_refinement_payload_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_target_band_best_refinement_payload_extraction_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Target-Band Best Refinement Payload Extraction",
        "",
        f"## Summary: {payload['status']}",
        "",
        "Moved best refinement payload selection by lower distance into `design_brain.candidate_evaluation.select_target_band_best_refinement_payload(...)`.",
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
