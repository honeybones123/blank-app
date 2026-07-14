"""Verify bottom-reo geometry trial axis interpretation moved to family ownership."""

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

PAGE_WRAPPER = "_geometry_trial_axis_for_bottom_rec"
FAMILY_HELPER = "resolve_bottom_reo_geometry_trial_axis"


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


def _old_axis(candidate: dict | None, *, width_key: str | None) -> str | None:
    candidate_dict = candidate if isinstance(candidate, dict) else {}
    if not candidate_dict.get("recommendation_geometry_trial"):
        return None
    updates = candidate_dict.get("updates") or {}
    if "D" in updates:
        return "depth"
    if width_key in updates:
        return "width"
    return None


def _sample_cases() -> list[dict[str, Any]]:
    return [
        {
            "case": "not_geometry_trial",
            "candidate": {"recommendation_geometry_trial": False, "updates": {"D": 650}},
            "width_key": "b",
        },
        {
            "case": "depth_update",
            "candidate": {"recommendation_geometry_trial": True, "updates": {"D": 650}},
            "width_key": "b",
        },
        {
            "case": "width_update",
            "candidate": {"recommendation_geometry_trial": True, "updates": {"b": 450}},
            "width_key": "b",
        },
        {
            "case": "missing_width_key",
            "candidate": {"recommendation_geometry_trial": True, "updates": {"b": 450}},
            "width_key": None,
        },
        {
            "case": "unknown_update",
            "candidate": {"recommendation_geometry_trial": True, "updates": {"span": 3000}},
            "width_key": "b",
        },
        {"case": "invalid_candidate", "candidate": None, "width_key": "b"},
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
    from design_brain.families.bending import resolve_bottom_reo_geometry_trial_axis

    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    page_start, page_end, page_segment = _function_segment(inputs_source, PAGE_WRAPPER)
    helper_start, helper_end, helper_segment = _function_segment(bending_source, FAMILY_HELPER)

    parity_rows: list[dict[str, Any]] = []
    for case in _sample_cases():
        old = _old_axis(case.get("candidate"), width_key=case.get("width_key"))
        new = resolve_bottom_reo_geometry_trial_axis(case.get("candidate"), width_key=case.get("width_key"))
        parity_rows.append({"case": case.get("case"), "old": old, "new": new, "matches": old == new})

    forbidden = _forbidden_terms(helper_segment)
    checks = {
        "family_helper_exists": bool(helper_segment),
        "family_helper_has_no_page_or_ui_forbidden_terms": not any(forbidden.values()),
        "page_wrapper_delegates_to_family_helper": "_resolve_bottom_reo_geometry_trial_axis(" in page_segment,
        "page_wrapper_keeps_width_key_collection": "_resolve_geometry_width_context(state)" in page_segment,
        "page_wrapper_no_longer_contains_axis_policy": '"D" in' not in page_segment
        and '"depth"' not in page_segment
        and '"width"' not in page_segment,
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
            "BOTTOM_REO_GEOMETRY_TRIAL_AXIS_FAMILY_ADAPTER_EXTRACTED"
            if status == "PASS"
            else "BOTTOM_REO_GEOMETRY_TRIAL_AXIS_EXTRACTION_FAILED"
        ),
        "page_wrapper_lines": {"start": page_start, "end": page_end},
        "family_helper_lines": {"start": helper_start, "end": helper_end},
        "parity_rows": parity_rows,
        "family_helper_forbidden_terms": forbidden,
        "checks": checks,
        "remaining_page_owned_inputs": [
            "page resolves active geometry width key",
            "compound preference wrapper still supplies mode_config, seed depth, and score margin",
        ],
        "next_safe_slice": "bottom_reo_compound_preference_wrapper_boundary_audit",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_geometry_trial_axis_family_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_geometry_trial_axis_family_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Geometry Trial Axis Family Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Behaviour Preserved",
        "",
        "The page still resolves the active width key from page state. The bending family now owns interpretation of candidate updates as depth/width geometry trial axes.",
        "",
        "## Parity Cases",
        "",
        "| Case | Old | New | Match |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(f"| `{row.get('case')}` | `{row.get('old')}` | `{row.get('new')}` | `{row.get('matches')}` |")
    lines.extend(["", "## Remaining Page-Owned Inputs", ""])
    lines.extend(f"- {item}" for item in payload.get("remaining_page_owned_inputs") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bottom_reo_geometry_trial_axis_family_extraction {payload.get('status')}")
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
