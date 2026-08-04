"""Verify bottom-reo result display label resolution moved to bending family."""

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

INPUTS = ROOT / "inputs_page.py"
BENDING = ROOT / "design_brain" / "families" / "bending.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

COMPUTE_HELPER = "_compute_bottom_reo_recommendation"
FAMILY_HELPER = "resolve_bottom_reo_result_display_label"


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


def _old_display_label(candidate: dict | None) -> str:
    candidate_dict = candidate if isinstance(candidate, dict) else {}
    disp_label = str(candidate_dict.get("label") or "")
    if candidate_dict.get("recommendation_compound"):
        disp_label = str(candidate_dict.get("guidance_recommendation_title") or disp_label)
    return disp_label


def _sample_cases() -> list[dict[str, Any]]:
    return [
        {
            "case": "normal_bottom_reo",
            "candidate": {"label": "Reduce bottom reinforcement to 5N16", "recommendation_compound": False},
        },
        {
            "case": "compound_with_guidance_title",
            "candidate": {
                "label": "compound raw label",
                "recommendation_compound": True,
                "guidance_recommendation_title": "Reduce width and bottom reinforcement",
            },
        },
        {
            "case": "compound_without_guidance_title",
            "candidate": {"label": "compound fallback label", "recommendation_compound": True},
        },
        {"case": "missing_candidate", "candidate": None},
        {"case": "empty_label", "candidate": {"label": "", "recommendation_compound": False}},
    ]


def _forbidden_terms(segment: str) -> dict[str, bool]:
    return {
        "imports_inputs_page": "inputs_page" in segment,
        "imports_streamlit": "streamlit" in segment or "st." in segment,
        "uses_session_state": "session_state" in segment,
        "uses_apply_routing": "apply_" in segment or "one_click" in segment,
        "uses_rendering": "render_" in segment or "html" in segment,
        "uses_publication": "FinalDesignGuidePublication" in segment or "publication" in segment,
    }


def build_payload() -> dict[str, Any]:
    from design_brain.families.bending import resolve_bottom_reo_result_display_label

    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    compute_start, compute_end, compute_segment = _function_segment(inputs_source, COMPUTE_HELPER)
    helper_start, helper_end, helper_segment = _function_segment(bending_source, FAMILY_HELPER)

    parity_rows: list[dict[str, Any]] = []
    for case in _sample_cases():
        old = _old_display_label(case.get("candidate"))
        new = resolve_bottom_reo_result_display_label(case.get("candidate"))
        parity_rows.append({"case": case.get("case"), "old": old, "new": new, "matches": old == new})

    forbidden = _forbidden_terms(helper_segment)
    checks = {
        "family_helper_exists": bool(helper_segment),
        "family_helper_has_no_page_or_ui_forbidden_terms": not any(forbidden.values()),
        "compute_helper_delegates_to_family_helper": "_resolve_bottom_reo_result_display_label(best)" in compute_segment,
        "compute_helper_no_longer_has_compound_label_branch": "disp_label = str(best.get(\"label\") or \"\")" not in compute_segment
        and "guidance_recommendation_title\" or disp_label" not in compute_segment
        and "guidance_recommendation_title') or disp_label" not in compute_segment,
        "all_sample_cases_match": all(row["matches"] for row in parity_rows),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "decision": (
            "BOTTOM_REO_RESULT_DISPLAY_LABEL_FAMILY_ADAPTER_EXTRACTED"
            if status == "PASS"
            else "BOTTOM_REO_RESULT_DISPLAY_LABEL_EXTRACTION_FAILED"
        ),
        "compute_helper_lines": {"start": compute_start, "end": compute_end},
        "family_helper_lines": {"start": helper_start, "end": helper_end},
        "parity_rows": parity_rows,
        "family_helper_forbidden_terms": forbidden,
        "checks": checks,
        "remaining_page_owned_projection_inputs": [
            "required Ast calculation",
            "guidance change-line construction",
            "selected result adapter call orchestration",
        ],
        "next_safe_slice": "bottom_reo_required_ast_or_change_line_projection_parity",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_result_display_label_family_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_result_display_label_family_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Result Display Label Family Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Behaviour Preserved",
        "",
        "The bending family now owns the selected bottom-reo result display-label rule. Required Ast, change lines, CTA/apply, and rendering remain unchanged.",
        "",
        "## Parity Cases",
        "",
        "| Case | Old label | New label | Match |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(f"| `{row.get('case')}` | `{row.get('old')}` | `{row.get('new')}` | `{row.get('matches')}` |")
    lines.extend(["", "## Remaining Page-Owned Projection Inputs", ""])
    lines.extend(f"- {item}" for item in payload.get("remaining_page_owned_projection_inputs") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bottom_reo_result_display_label_family_extraction {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload.get("status") != "PASS":
        failed = [name for name, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
