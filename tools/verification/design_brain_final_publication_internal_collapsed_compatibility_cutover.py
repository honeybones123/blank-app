from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTROLLER_PATH = ROOT / "design_brain" / "design_guide_controller.py"

from design_brain.final_publication import (  # noqa: E402
    build_collapsed_guidance_item_from_final_publication,
    build_final_design_guide_publication,
    stable_final_publication_authority_hash,
    stable_final_publication_hash,
)


TARGETS = {
    "compute_publication_handoff": "def run_design_guide_controller_compute_publication_handoff_trace_only(",
    "compute_rebound_publication_item": "def run_design_guide_controller_compute_rebound_publication_item_trace_only(",
    "compute_resolver_fallback_shell": "def build_design_guide_controller_compute_resolver_fallback_shell(",
}


def _sample_item(case: str) -> dict[str, Any]:
    if case == "action":
        return {
            "published_item_id": "candidate-action",
            "selected_family_id": "BENDING_FAIL_GOVERNS",
            "family": "BENDING_FAIL_GOVERNS",
            "title_main": "Strengthening required",
            "title": "Strengthening required",
            "summary_line": "Increase bottom reinforcement.",
            "status": "ACTION",
            "bucket": "fail",
            "display_state": "ACTION",
            "button_contract": {
                "enabled": True,
                "actionable": True,
                "label": "Apply",
                "action_type": "apply_resolved_candidate",
                "family": "BENDING_FAIL_GOVERNS",
                "updates": {"bot_row_1_bars": 4, "bot_row_1_dia": 20},
                "candidate_id": "candidate-action",
                "source_candidate_id": "candidate-action",
                "executor_backed": True,
            },
            "action_payload": {
                "action_type": "apply_resolved_candidate",
                "family": "BENDING_FAIL_GOVERNS",
                "updates": {"bot_row_1_bars": 4, "bot_row_1_dia": 20},
            },
            "candidate_search_evidence": {
                "family": "BENDING_FAIL_GOVERNS",
                "selected_candidate_id": "candidate-action",
                "selected_candidate_updates": {"bot_row_1_bars": 4, "bot_row_1_dia": 20},
                "safe_executor_backed_candidates_count": 1,
            },
            "candidate_id": "candidate-action",
            "source_candidate_id": "candidate-action",
        }
    if case == "blocked":
        return {
            "published_item_id": "candidate-blocked",
            "selected_family_id": "SHEAR_FAIL_GOVERNS",
            "family": "SHEAR_FAIL_GOVERNS",
            "title_main": "No valid repair",
            "title": "No valid repair",
            "summary_line": "Spacing and geometry prevent a compliant repair.",
            "status": "BLOCKED",
            "bucket": "fail",
            "display_state": "BLOCKED",
            "blocker_reason": "No valid repair remains.",
            "button_contract": {
                "enabled": False,
                "actionable": False,
                "label": "Apply",
                "action_type": "apply_resolved_candidate",
                "family": "SHEAR_FAIL_GOVERNS",
                "disabled_reason": "No valid repair remains.",
            },
            "action_payload": {},
            "candidate_search_evidence": {
                "family": "SHEAR_FAIL_GOVERNS",
                "selected_candidate_id": None,
                "safe_executor_backed_candidates_count": 0,
            },
        }
    return {
        "published_item_id": "candidate-fallback",
        "selected_family_id": "general",
        "family": "general",
        "title_main": "Design Guide publication pending",
        "title": "Design Guide publication pending",
        "summary_line": "Waiting for a controller result.",
        "status": "PROOF_PENDING",
        "bucket": "warn",
        "display_state": "PROOF_PENDING",
        "button_contract": {
            "enabled": False,
            "actionable": False,
            "label": "Apply",
            "action_type": "apply_resolved_candidate",
            "family": "general",
            "disabled_reason": "Fallback shell only.",
        },
        "action_payload": {},
        "candidate_search_evidence": {},
        "controller_compute_resolver_fallback_shell": True,
    }


def _publication(item: dict[str, Any], *, reason: str) -> Any:
    return build_final_design_guide_publication(
        item=dict(item),
        debug={},
        publication_reason=reason,
    )


def _case_result(case_id: str, item: dict[str, Any]) -> dict[str, Any]:
    publication = _publication(item, reason=f"cutover:{case_id}")
    without_compat = build_collapsed_guidance_item_from_final_publication(publication)
    compared_fields = (
        "published_item_id",
        "selected_family_id",
        "family",
        "outcome_state",
        "publication_reason",
        "blocker_reason",
        "title_main",
        "title",
        "pill",
        "summary_line",
        "status",
        "bucket",
        "display_state",
        "publication_hash",
        "final_publication_cta_hash",
        "final_publication_display_hash",
        "final_publication_evidence_hash",
    )
    expected = {
        "published_item_id": publication.published_item_id,
        "selected_family_id": publication.selected_family,
        "family": publication.selected_family,
        "outcome_state": publication.outcome_state,
        "publication_reason": publication.publication_reason,
        "blocker_reason": publication.blocker_reason,
        "title_main": publication.display.title,
        "title": publication.display.title,
        "pill": publication.display.badge,
        "summary_line": publication.display.summary,
        "status": publication.display.status or publication.outcome_state,
        "bucket": publication.display.bucket,
        "display_state": publication.display.display_state or publication.outcome_state,
        "publication_hash": publication.publication_hash,
        "final_publication_cta_hash": stable_final_publication_authority_hash(publication.cta.to_dict()),
        "final_publication_display_hash": stable_final_publication_authority_hash(publication.display.to_dict()),
        "final_publication_evidence_hash": stable_final_publication_authority_hash(publication.evidence.to_dict()),
    }
    diffs = [
        field
        for field in compared_fields
        if stable_final_publication_hash(expected.get(field))
        != stable_final_publication_hash(without_compat.get(field))
    ]
    return {
        "case_id": case_id,
        "publication_hash": publication.publication_hash,
        "without_compat_hash": without_compat.get("collapsed_guidance_item_hash"),
        "compared_fields_match": not diffs,
        "diff_fields": diffs,
        "button_contract_present_without_compat": bool(without_compat.get("button_contract")),
        "action_payload_present_without_compat": bool(without_compat.get("action_payload") is not None),
    }


def _source_window(source: str, anchor: str, *, window: int = 6000) -> str:
    index = source.find(anchor)
    if index < 0:
        return ""
    return source[index : index + window]


def main() -> int:
    source = CONTROLLER_PATH.read_text(encoding="utf-8", errors="replace")
    cases = [
        _case_result("compute_publication_handoff", _sample_item("action")),
        _case_result("compute_rebound_publication_item", _sample_item("blocked")),
        _case_result("compute_resolver_fallback_shell", _sample_item("fallback")),
    ]
    target_rows = []
    for target_id, anchor in TARGETS.items():
        window = _source_window(source, anchor)
        target_rows.append(
            {
                "target_id": target_id,
                "anchor": anchor,
                "callsite_found": bool(window),
                "collapsed_builder_called": "build_collapsed_guidance_item_from_final_publication(" in window,
                "passes_current_item_compatibility": "current_item_compatibility=" in window,
                "window_hash": stable_final_publication_hash(window),
            }
        )
    checks = {
        "all_target_callsites_found": all(row["callsite_found"] for row in target_rows),
        "all_target_callsites_still_call_builder": all(row["collapsed_builder_called"] for row in target_rows),
        "all_target_callsites_do_not_pass_current_item_compatibility": all(
            not row["passes_current_item_compatibility"] for row in target_rows
        ),
        "all_case_truth_fields_match_without_compat": all(case["compared_fields_match"] for case in cases),
        "without_compat_still_builds_button_contracts": all(
            case["button_contract_present_without_compat"] for case in cases
        ),
    }
    failures = [key for key, passed in checks.items() if not passed]
    payload = {
        "schema": "design_brain_final_publication_internal_collapsed_compatibility_cutover.v1",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "targets": target_rows,
        "cases": cases,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_brain_final_publication_internal_collapsed_compatibility_cutover_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_brain_final_publication_internal_collapsed_compatibility_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Design Brain Final Publication Internal Collapsed Compatibility Cutover",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend([f"- `{key}`: `{value}`" for key, value in checks.items()])
    lines.extend(["", "## Targets", ""])
    for row in target_rows:
        lines.extend(
            [
                f"### {row['target_id']}",
                "",
                f"- anchor: `{row['anchor']}`",
                f"- callsite_found: `{row['callsite_found']}`",
                f"- collapsed_builder_called: `{row['collapsed_builder_called']}`",
                f"- passes_current_item_compatibility: `{row['passes_current_item_compatibility']}`",
                "",
            ]
        )
    lines.extend(["## Cases", ""])
    for case in cases:
        lines.extend(
            [
                f"### {case['case_id']}",
                "",
                f"- compared_fields_match: `{case['compared_fields_match']}`",
                f"- diff_fields: `{case['diff_fields']}`",
            ]
        )
    audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{payload['status']}: {json_path}")
    print(f"REPORT: {audit_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
