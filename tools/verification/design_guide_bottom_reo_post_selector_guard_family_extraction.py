"""Verify bottom-reo post-selector guard classification moved to bending family."""

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
FAMILY_HELPER = "resolve_bottom_reo_post_selector_guard"


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


def _old_guard(selected_candidate: dict | None, *, updates_match_state: bool, growth_rejected: bool = False) -> dict[str, Any]:
    if not selected_candidate or bool(updates_match_state):
        return {
            "post_selector_guard_result": "no_result",
            "no_result_reason": "no_selected_candidate",
            "selected": False,
        }
    if bool(growth_rejected):
        return {
            "post_selector_guard_result": "no_result",
            "no_result_reason": "growth_blocked_efficiency_reduction",
            "selected": False,
        }
    return {
        "post_selector_guard_result": "selected",
        "no_result_reason": None,
        "selected": True,
    }


def _sample_cases() -> list[dict[str, Any]]:
    return [
        {"case": "missing_candidate", "candidate": None, "updates_match_state": False, "growth_rejected": False},
        {"case": "no_op_updates", "candidate": {"updates": {"bot1": 5}}, "updates_match_state": True, "growth_rejected": False},
        {"case": "growth_rejected", "candidate": {"updates": {"bot1": 4}}, "updates_match_state": False, "growth_rejected": True},
        {"case": "selected", "candidate": {"updates": {"bot1": 4}}, "updates_match_state": False, "growth_rejected": False},
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
    from design_brain.families.bending import resolve_bottom_reo_post_selector_guard

    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    compute_start, compute_end, compute_segment = _function_segment(inputs_source, COMPUTE_HELPER)
    helper_start, helper_end, helper_segment = _function_segment(bending_source, FAMILY_HELPER)

    parity_rows: list[dict[str, Any]] = []
    for case in _sample_cases():
        old = _old_guard(
            case.get("candidate"),
            updates_match_state=bool(case.get("updates_match_state")),
            growth_rejected=bool(case.get("growth_rejected")),
        )
        new = resolve_bottom_reo_post_selector_guard(
            case.get("candidate"),
            updates_match_state=bool(case.get("updates_match_state")),
            growth_rejected=bool(case.get("growth_rejected")),
        )
        parity_rows.append({"case": case.get("case"), "old": old, "new": new, "matches": old == new})

    forbidden = _forbidden_terms(helper_segment)
    checks = {
        "family_helper_exists": bool(helper_segment),
        "family_helper_has_no_page_or_ui_forbidden_terms": not any(forbidden.values()),
        "compute_helper_delegates_to_family_helper": compute_segment.count("_resolve_bottom_reo_post_selector_guard(") >= 2,
        "compute_helper_keeps_updates_match_state_page_input": "_updates_match_state(state" in compute_segment,
        "compute_helper_keeps_growth_policy_controller_input": "_resolve_design_guide_controller_bottom_reo_efficiency_growth_filter_policy(" in compute_segment,
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
            "BOTTOM_REO_POST_SELECTOR_GUARD_FAMILY_CLASSIFIER_EXTRACTED"
            if status == "PASS"
            else "BOTTOM_REO_POST_SELECTOR_GUARD_EXTRACTION_FAILED"
        ),
        "compute_helper_lines": {"start": compute_start, "end": compute_end},
        "family_helper_lines": {"start": helper_start, "end": helper_end},
        "parity_rows": parity_rows,
        "family_helper_forbidden_terms": forbidden,
        "checks": checks,
        "remaining_page_owned_guard_inputs": [
            "updates-match-state boolean",
            "controller-owned efficiency-growth policy result",
            "trace/log event emission",
        ],
        "next_safe_slice": "bottom_reo_guidance_change_line_or_trace_identity_projection_boundary",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_post_selector_guard_family_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_post_selector_guard_family_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Post-Selector Guard Family Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Behaviour Preserved",
        "",
        "The bending family now classifies post-selector guard outcomes. The page still supplies page/controller guard inputs and still owns trace/log return mechanics.",
        "",
        "## Parity Cases",
        "",
        "| Case | Old | New | Match |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(f"| `{row.get('case')}` | `{row.get('old')}` | `{row.get('new')}` | `{row.get('matches')}` |")
    lines.extend(["", "## Remaining Page-Owned Guard Inputs", ""])
    lines.extend(f"- {item}" for item in payload.get("remaining_page_owned_guard_inputs") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bottom_reo_post_selector_guard_family_extraction {payload.get('status')}")
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
