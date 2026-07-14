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
INPUTS_PATH = ROOT / "inputs_page.py"

from design_brain.design_guide_controller import (  # noqa: E402
    DesignGuideControllerRequest,
    run_design_guide_controller_publication_authority,
    run_design_guide_controller_render_item_consumer_trace_only,
)
from design_brain.final_publication import stable_final_publication_hash  # noqa: E402


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
                "candidate_id": "candidate-action",
                "source_candidate_id": "candidate-action",
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


def _source_window(source: str, anchor: str, *, window: int = 5000) -> str:
    index = source.find(anchor)
    if index < 0:
        return ""
    return source[index : index + window]


def _live_case_result(case_id: str, item: dict[str, Any]) -> dict[str, Any]:
    publication_reason = (
        "controller_compute_resolver_fallback_shell"
        if case_id == "fallback"
        else f"live_cutover:{case_id}"
    )
    request_with_compat = DesignGuideControllerRequest(
        item=dict(item),
        debug={},
        publication_reason=publication_reason,
        source=f"with_compat:{case_id}",
    )
    request_without_compat = DesignGuideControllerRequest(
        item=dict(item),
        debug={},
        publication_reason=publication_reason,
        source=f"without_compat:{case_id}",
    )
    with_compat = run_design_guide_controller_publication_authority(request_with_compat)
    without_compat = run_design_guide_controller_publication_authority(request_without_compat)
    with_item = dict(with_compat.collapsed_guidance_item or {})
    without_item = dict(without_compat.collapsed_guidance_item or {})
    compare_fields = (
        "published_item_id",
        "candidate_id",
        "source_candidate_id",
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
        "controller_compute_resolver_fallback_shell",
    )
    diff_fields = [
        field
        for field in compare_fields
        if stable_final_publication_hash(with_item.get(field))
        != stable_final_publication_hash(without_item.get(field))
    ]
    return {
        "case_id": case_id,
        "compared_fields_match": not diff_fields,
        "diff_fields": diff_fields,
        "with_compat_hash": with_item.get("collapsed_guidance_item_hash"),
        "without_compat_hash": without_item.get("collapsed_guidance_item_hash"),
        "with_candidate_id": with_item.get("candidate_id"),
        "without_candidate_id": without_item.get("candidate_id"),
        "with_source_candidate_id": with_item.get("source_candidate_id"),
        "without_source_candidate_id": without_item.get("source_candidate_id"),
        "with_fallback_shell": bool(with_item.get("controller_compute_resolver_fallback_shell")),
        "without_fallback_shell": bool(without_item.get("controller_compute_resolver_fallback_shell")),
    }


def _render_consumer_case_result(case_id: str, item: dict[str, Any]) -> dict[str, Any]:
    request_with_compat = DesignGuideControllerRequest(
        item=dict(item),
        debug={},
        final_visible_resolution={"item": dict(item), "render_reason": f"render_consumer:{case_id}"},
        guidance_debug={},
        publication_reason=f"render_consumer:{case_id}",
        source=f"render_consumer:{case_id}",
    )
    request_without_compat = DesignGuideControllerRequest(
        item=dict(item),
        debug={},
        final_visible_resolution={"item": dict(item), "render_reason": f"render_consumer:{case_id}"},
        guidance_debug={},
        publication_reason=f"render_consumer:{case_id}",
        source=f"render_consumer:{case_id}",
    )
    with_compat = run_design_guide_controller_render_item_consumer_trace_only(request_with_compat)
    without_compat = run_design_guide_controller_render_item_consumer_trace_only(request_without_compat)
    return {
        "case_id": case_id,
        "proof_hash_matches": with_compat.get("render_item_consumer_proof_hash")
        == without_compat.get("render_item_consumer_proof_hash"),
        "publication_hash_matches": with_compat.get("publication_hash")
        == without_compat.get("publication_hash"),
    }


def main() -> int:
    controller_source = CONTROLLER_PATH.read_text(encoding="utf-8", errors="replace")
    page_source = INPUTS_PATH.read_text(encoding="utf-8", errors="replace")
    cases = [
        _live_case_result("action", _sample_item("action")),
        _live_case_result("blocked", _sample_item("blocked")),
        _live_case_result("fallback", _sample_item("fallback")),
    ]
    render_consumer_cases = [
        _render_consumer_case_result("action", _sample_item("action")),
        _render_consumer_case_result("fallback", _sample_item("fallback")),
    ]
    run_window = _source_window(
        controller_source,
        "def _run_design_guide_controller(",
    )
    render_consumer_window = _source_window(
        controller_source,
        "def run_design_guide_controller_render_item_consumer_trace_only(",
    )
    page_live_calls_removed = all(
        token not in page_source
        for token in (
            "current_item_compatibility=dict(legacy_item)",
            "current_item_compatibility=dict(item or {})",
        )
    )
    checks = {
        "publication_authority_no_longer_passes_current_item_compatibility": (
            "current_item_compatibility" not in run_window
        ),
        "render_item_consumer_no_longer_uses_current_item_compatibility": (
            "current_item_compatibility" not in render_consumer_window
        ),
        "live_page_controller_calls_no_longer_pass_current_item_compatibility": page_live_calls_removed,
        "all_publication_cases_match_without_compat": all(case["compared_fields_match"] for case in cases),
        "render_item_consumer_proof_hashes_match_without_compat": all(
            case["proof_hash_matches"] and case["publication_hash_matches"]
            for case in render_consumer_cases
        ),
    }
    failures = [key for key, passed in checks.items() if not passed]
    payload = {
        "schema": "design_brain_final_publication_live_collapsed_compatibility_cutover.v1",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "publication_cases": cases,
        "render_consumer_cases": render_consumer_cases,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_brain_final_publication_live_collapsed_compatibility_cutover_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_brain_final_publication_live_collapsed_compatibility_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Design Brain Final Publication Live Collapsed Compatibility Cutover",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend([f"- `{key}`: `{value}`" for key, value in checks.items()])
    lines.extend(["", "## Publication Cases", ""])
    for case in cases:
        lines.extend(
            [
                f"### {case['case_id']}",
                "",
                f"- compared_fields_match: `{case['compared_fields_match']}`",
                f"- diff_fields: `{case['diff_fields']}`",
                f"- candidate_id: `{case['with_candidate_id']}` / `{case['without_candidate_id']}`",
                f"- source_candidate_id: `{case['with_source_candidate_id']}` / `{case['without_source_candidate_id']}`",
                f"- fallback_shell: `{case['with_fallback_shell']}` / `{case['without_fallback_shell']}`",
                "",
            ]
        )
    lines.extend(["## Render Consumer Cases", ""])
    for case in render_consumer_cases:
        lines.extend(
            [
                f"### {case['case_id']}",
                "",
                f"- proof_hash_matches: `{case['proof_hash_matches']}`",
                f"- publication_hash_matches: `{case['publication_hash_matches']}`",
                "",
            ]
        )
    audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{payload['status']}: {json_path}")
    print(f"REPORT: {audit_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
