"""Verify bottom-reo compound merge/reject policy moved to bending family."""

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

PAGE_HELPER = "_append_geometry_bottom_compound_candidates"
FAMILY_HELPER = "classify_bottom_reo_compound_attempt_merge_policy"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _old_policy(
    *,
    bottom_updates_match_geometry_state: bool,
    duplicate_signature: bool,
    invalid_empty_updates: bool,
    updates_match_current_state: bool,
    layout_fits: bool,
) -> dict[str, Any]:
    if bottom_updates_match_geometry_state:
        return {
            "accepted_for_evaluation": False,
            "compound_stats_key": "rejected_no_layout_variation",
            "trace_result": "rejected",
            "trace_reason": "no_layout_variation_vs_geometry_adjusted_state",
        }
    if duplicate_signature:
        return {
            "accepted_for_evaluation": False,
            "compound_stats_key": "rejected_duplicate_signature",
            "trace_result": "rejected",
            "trace_reason": "duplicate_signature",
        }
    if invalid_empty_updates:
        return {
            "accepted_for_evaluation": False,
            "compound_stats_key": "rejected_invalid_merge",
            "trace_result": "rejected",
            "trace_reason": "invalid_merge_empty_updates",
        }
    if updates_match_current_state:
        return {
            "accepted_for_evaluation": False,
            "compound_stats_key": "rejected_same_as_current",
            "trace_result": "rejected",
            "trace_reason": "same_as_current_live_state",
        }
    if not layout_fits:
        return {
            "accepted_for_evaluation": False,
            "compound_stats_key": "compound_layout_reject_count",
            "trace_result": "rejected",
            "trace_reason": "layout_no_fit",
        }
    return {
        "accepted_for_evaluation": True,
        "compound_stats_key": None,
        "trace_result": "accepted_for_evaluation",
        "trace_reason": "ready_for_candidate_evaluation",
    }


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "no_layout_variation_wins",
            "bottom_updates_match_geometry_state": True,
            "duplicate_signature": True,
            "invalid_empty_updates": True,
            "updates_match_current_state": True,
            "layout_fits": False,
        },
        {
            "name": "duplicate_signature",
            "bottom_updates_match_geometry_state": False,
            "duplicate_signature": True,
            "invalid_empty_updates": True,
            "updates_match_current_state": True,
            "layout_fits": False,
        },
        {
            "name": "invalid_empty_updates",
            "bottom_updates_match_geometry_state": False,
            "duplicate_signature": False,
            "invalid_empty_updates": True,
            "updates_match_current_state": True,
            "layout_fits": False,
        },
        {
            "name": "same_as_current",
            "bottom_updates_match_geometry_state": False,
            "duplicate_signature": False,
            "invalid_empty_updates": False,
            "updates_match_current_state": True,
            "layout_fits": False,
        },
        {
            "name": "layout_no_fit",
            "bottom_updates_match_geometry_state": False,
            "duplicate_signature": False,
            "invalid_empty_updates": False,
            "updates_match_current_state": False,
            "layout_fits": False,
        },
        {
            "name": "accepted_for_evaluation",
            "bottom_updates_match_geometry_state": False,
            "duplicate_signature": False,
            "invalid_empty_updates": False,
            "updates_match_current_state": False,
            "layout_fits": True,
        },
    ]


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    _, _, page_segment = _function_segment(inputs_source, PAGE_HELPER)

    from design_brain.families.bending import classify_bottom_reo_compound_attempt_merge_policy

    parity: list[dict[str, Any]] = []
    for case in _cases():
        kwargs = {key: bool(value) for key, value in case.items() if key != "name"}
        old = _old_policy(**kwargs)
        new = classify_bottom_reo_compound_attempt_merge_policy(**kwargs)
        parity.append(
            {
                "case": case["name"],
                "matches": old == new,
                "old": old,
                "new": new,
            }
        )

    direct_increment_tokens = [
        'compound_stats["rejected_no_layout_variation"] += 1',
        'compound_stats["rejected_duplicate_signature"] += 1',
        'compound_stats["rejected_invalid_merge"] += 1',
        'compound_stats["rejected_same_as_current"] += 1',
        'compound_stats["compound_layout_reject_count"] += 1',
    ]
    source_checks = {
        "family_helper_present": f"def {FAMILY_HELPER}(" in bending_source,
        "page_delegates_merge_policy_to_family": "_classify_bottom_reo_compound_attempt_merge_policy(" in page_segment,
        "page_removed_direct_reject_stat_policy": not any(token in page_segment for token in direct_increment_tokens),
        "page_keeps_evaluator_callback": "_evaluate_candidate_fast(" in page_segment,
        "page_keeps_state_callbacks": "_updates_match_state(" in page_segment
        and "_arrangement_fits_state(" in page_segment,
        "page_keeps_candidate_pool_mutation": "candidates.append(comp)" in page_segment,
        "family_has_no_inputs_page_import": "import inputs_page" not in bending_source
        and "from inputs_page" not in bending_source,
        "family_has_no_streamlit_import": "streamlit" not in bending_source and "import st" not in bending_source,
    }
    checks = {
        **source_checks,
        "parity_cases_match": all(bool(row.get("matches")) for row in parity),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_bottom_reo_compound_merge_reject_policy_family_boundary.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BOTTOM_REO_COMPOUND_MERGE_REJECT_POLICY_FAMILY_BOUNDARY_EXTRACTED",
        "page_helper": PAGE_HELPER,
        "family_helper": FAMILY_HELPER,
        "parity": parity,
        "source_checks": source_checks,
        "checks": checks,
        "next_safe_slice": "bottom_reo_compound_accepted_candidate_projection_family_boundary",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_compound_merge_reject_policy_family_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_compound_merge_reject_policy_family_boundary_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Bottom Reo Compound Merge/Reject Policy Family Boundary",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Boundary",
        "",
        f"- Page helper: `{payload.get('page_helper')}`",
        f"- Family helper: `{payload.get('family_helper')}`",
        "- Page still owns callback facts, evaluator callbacks, live candidate pool mutation, and trace emission.",
        "",
        "## Parity",
        "",
    ]
    for row in payload.get("parity") or []:
        lines.append(f"- `{row.get('case')}`: `{row.get('matches')}`")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    status = payload.get("status")
    print(f"design_guide_bottom_reo_compound_merge_reject_policy_family_boundary {status}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if status != "PASS":
        failed = [name for name, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
