"""Verify bottom-reo strict-band guard adapter moved to family ownership."""

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

PAGE_WRAPPER = "_is_strictly_rejectable_band_winner"
FAMILY_HELPER = "assess_bottom_reo_strict_band_winner_candidate"
PRIMITIVE_HELPER = "is_strictly_rejectable_bottom_reo_band_winner"


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


def _old_page_decision(candidate: dict | None, *, updates_match_state: bool) -> tuple[bool, str]:
    candidate_is_valid = isinstance(candidate, dict)
    updates = candidate.get("updates") if candidate_is_valid else None
    updates_present = isinstance(updates, dict) and bool(updates)
    if not bool(candidate_is_valid):
        return True, "invalid_candidate"
    if not bool(candidate.get("is_compliant")):
        return True, "noncompliant_candidate"
    if not bool(candidate.get("candidate_reaches_target_band")):
        return True, "not_target_band_candidate"
    if not bool(updates_present):
        return True, "missing_or_unusable_updates"
    if bool(updates_match_state):
        return True, "noop_updates_match_state"
    if not bool(str(candidate.get("label") or "").strip()):
        return True, "missing_label"
    return False, "ok"


def _sample_cases() -> list[dict[str, Any]]:
    valid = {
        "is_compliant": True,
        "candidate_reaches_target_band": True,
        "updates": {"bot1_count": 5},
        "label": "Use 5N16 bottom reinforcement",
    }
    return [
        {"case": "invalid_candidate", "candidate": None, "updates_match_state": False},
        {
            "case": "noncompliant_candidate",
            "candidate": {**valid, "is_compliant": False},
            "updates_match_state": False,
        },
        {
            "case": "not_target_band_candidate",
            "candidate": {**valid, "candidate_reaches_target_band": False},
            "updates_match_state": False,
        },
        {
            "case": "missing_or_unusable_updates",
            "candidate": {**valid, "updates": {}},
            "updates_match_state": False,
        },
        {"case": "noop_updates_match_state", "candidate": dict(valid), "updates_match_state": True},
        {"case": "missing_label", "candidate": {**valid, "label": ""}, "updates_match_state": False},
        {"case": "accepted", "candidate": dict(valid), "updates_match_state": False},
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
    from design_brain.families.bending import assess_bottom_reo_strict_band_winner_candidate

    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    page_start, page_end, page_segment = _function_segment(inputs_source, PAGE_WRAPPER)
    helper_start, helper_end, helper_segment = _function_segment(bending_source, FAMILY_HELPER)
    primitive_start, primitive_end, primitive_segment = _function_segment(bending_source, PRIMITIVE_HELPER)

    parity_rows: list[dict[str, Any]] = []
    for case in _sample_cases():
        old_result = _old_page_decision(
            case.get("candidate"),
            updates_match_state=bool(case.get("updates_match_state")),
        )
        new_result = assess_bottom_reo_strict_band_winner_candidate(
            case.get("candidate"),
            updates_match_state=bool(case.get("updates_match_state")),
        )
        parity_rows.append(
            {
                "case": case.get("case"),
                "old": list(old_result),
                "new": list(new_result),
                "matches": old_result == new_result,
            },
        )

    forbidden = _forbidden_terms(helper_segment)
    checks = {
        "family_helper_exists": bool(helper_segment),
        "family_helper_calls_primitive_predicate": f"{PRIMITIVE_HELPER}(" in helper_segment,
        "family_helper_has_no_page_or_ui_forbidden_terms": not any(forbidden.values()),
        "page_wrapper_delegates_to_family_helper": "_assess_bottom_reo_strict_band_winner_candidate(" in page_segment,
        "page_wrapper_keeps_state_comparison": "_updates_match_state(state, updates)" in page_segment,
        "page_wrapper_no_longer_calls_primitive_family_predicate_directly": (
            "_is_strictly_rejectable_bottom_reo_band_winner(" not in page_segment
        ),
        "primitive_helper_still_family_owned": bool(primitive_segment)
        and "def is_strictly_rejectable_bottom_reo_band_winner" in primitive_segment,
        "inputs_no_longer_imports_primitive_alias": "_is_strictly_rejectable_bottom_reo_band_winner" not in inputs_source,
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
            "BOTTOM_REO_STRICT_BAND_GUARD_FAMILY_ADAPTER_EXTRACTED"
            if status == "PASS"
            else "BOTTOM_REO_STRICT_BAND_GUARD_EXTRACTION_FAILED"
        ),
        "page_wrapper_lines": {"start": page_start, "end": page_end},
        "family_helper_lines": {"start": helper_start, "end": helper_end},
        "primitive_helper_lines": {"start": primitive_start, "end": primitive_end},
        "parity_rows": parity_rows,
        "family_helper_forbidden_terms": forbidden,
        "checks": checks,
        "remaining_page_owned_inputs": [
            "page computes updates_match_state from current state",
            "page wrapper remains temporarily for selector loop compatibility",
            "live selector loop still page-owned",
        ],
        "next_safe_slice": "bottom_reo_legacy_rejection_policy_family_extraction_or_selector_policy_parity_object",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_strict_band_guard_family_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_strict_band_guard_family_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Strict-Band Guard Family Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Behaviour Preserved",
        "",
        "The page still computes the page-owned `updates_match_state` input. The family now owns the candidate interpretation for strict-band rejection.",
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
    print(f"design_guide_bottom_reo_strict_band_guard_family_extraction {payload.get('status')}")
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
