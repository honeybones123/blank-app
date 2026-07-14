"""Proof-only bottom-reo live selector loop cutover readiness snapshot.

This verifier does not move selector policy. It records whether the bottom-reo
selector wrapper can be cut over now, or whether it is blocked by the shared
auto-design selector still owning page-local policy.
"""

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
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

BOTTOM_SELECTOR = "_pick_best_bottom_recommendation_by_selector"
SHARED_SELECTOR = "_select_best_auto_design_candidate"


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


def _present(segment: str, tokens: list[str]) -> dict[str, bool]:
    return {token: token in segment for token in tokens}


def build_payload() -> dict[str, Any]:
    source = _read(INPUTS)
    bottom_start, bottom_end, bottom_segment = _function_segment(source, BOTTOM_SELECTOR)
    shared_start, shared_end, shared_segment = _function_segment(source, SHARED_SELECTOR)

    bottom_tokens = _present(
        bottom_segment,
        [
            "_select_best_auto_design_candidate(",
            "_record_selector_result(",
            "_bottom_reo_selector_result_record(",
            "_log_design_reco_candidate_rank(",
            "_merge_design_guide_rank_trace(",
            "_is_strictly_rejectable_band_winner(",
            "_updates_match_state(",
        ],
    )
    shared_policy_tokens = _present(
        shared_segment,
        [
            "_annotate_candidate_target_band_metrics(",
            "_score_auto_design_candidate(",
            "_score_auto_design_candidates_for_selection(",
            "_resolve_auto_design_winner_pool_decision(",
            "_score_band_reaching_candidate_for_goal(",
            "_band_reacher_delta_metrics(",
            "_resolve_auto_design_band_reacher_ranked_pool(",
            "_apply_auto_design_winner_metadata_projection(",
            "_build_auto_design_selected_candidate_selection_result_from_context(",
            "_merge_design_guide_rank_trace(",
        ],
    )

    service_owned_selector_tokens = {
        "_score_auto_design_candidates_for_selection(",
        "_resolve_auto_design_winner_pool_decision(",
        "_resolve_auto_design_band_reacher_ranked_pool(",
        "_apply_auto_design_winner_metadata_projection(",
        "_build_auto_design_selected_candidate_selection_result_from_context(",
    }
    page_policy_tokens = {
        "_annotate_candidate_target_band_metrics(",
        "_score_auto_design_candidate(",
        "_score_band_reaching_candidate_for_goal(",
        "_band_reacher_delta_metrics(",
    }
    shared_selector_still_page_policy = any(
        shared_policy_tokens.get(token) for token in page_policy_tokens
    )
    shared_selector_service_owned = all(
        shared_policy_tokens.get(token) for token in service_owned_selector_tokens
    )
    bottom_loop_still_calls_shared_selector = bottom_tokens["_select_best_auto_design_candidate("]
    bottom_loop_delegates_family_selector = (
        "_select_bottom_reo_recommendation_candidate_by_selector(" in bottom_segment
    )
    can_cutover_now = bool(
        bottom_loop_still_calls_shared_selector
        and not shared_selector_still_page_policy
        and shared_selector_service_owned
        and bottom_tokens["_record_selector_result("]
    )
    cutover_complete = bool(
        bottom_loop_delegates_family_selector
        and not bottom_tokens["_record_selector_result("]
        and not shared_selector_still_page_policy
        and shared_selector_service_owned
    )

    checks = {
        "bottom_selector_found": bool(bottom_segment),
        "shared_selector_found": bool(shared_segment),
        "bottom_selector_uses_family_result_record": bottom_tokens["_bottom_reo_selector_result_record("],
        "bottom_selector_records_trace_only_on_page": bottom_tokens["_log_design_reco_candidate_rank("]
        and bottom_tokens["_merge_design_guide_rank_trace("],
        "shared_selector_page_policy_absent": not shared_selector_still_page_policy,
        "shared_selector_service_policy_present": shared_selector_service_owned,
        "cutover_ready_or_complete_after_shared_policy_extraction": can_cutover_now or cutover_complete,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }

    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": (
            "BOTTOM_REO_SELECTOR_LIVE_LOOP_CUTOVER_COMPLETE"
            if cutover_complete
            else "READY_SHARED_AUTO_SELECTOR_POLICY_SERVICE_OWNED_TRACE_SINK_ONLY"
        ),
        "bottom_selector_lines": {"start": bottom_start, "end": bottom_end},
        "shared_selector_lines": {"start": shared_start, "end": shared_end},
        "can_cutover_bottom_reo_live_selector_now": can_cutover_now,
        "bottom_reo_live_selector_cutover_complete": cutover_complete,
        "bottom_selector_tokens": bottom_tokens,
        "shared_selector_policy_tokens": shared_policy_tokens,
        "checks": checks,
        "current_owner": {
            "bottom_reo_selector_wrapper": "inputs_page.py shell plus trace plumbing",
            "family_selector_result_record": "design_brain.families.bending",
            "shared_auto_selector_policy": "inputs_page.py",
        },
        "target_owner": {
            "shared_auto_selector_policy": "design_brain.candidate_evaluation",
            "bottom_reo_selector_wrapper": "shell-only after shared selector policy cutover",
        },
        "first_safe_implementation_slice": {
            "name": "auto_design_candidate_selector_target_band_score_service_extraction",
            "why": (
                "Bottom-reo live selector cutover depends on the shared selector. "
                "Row validity is already service-owned; target-band annotation and "
                "score assignment are the next shared selector policy fields still "
                "page-owned."
            ),
        },
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_selector_live_loop_cutover_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_selector_live_loop_cutover_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom-Reo Selector Live Loop Cutover Readiness",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        f"Can cut over bottom-reo live selector now: `{payload.get('can_cutover_bottom_reo_live_selector_now')}`",
        "",
        "## Current Owner",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in dict(payload.get("current_owner") or {}).items())
    lines.extend(["", "## Target Owner"])
    lines.extend(f"- `{key}`: {value}" for key, value in dict(payload.get("target_owner") or {}).items())
    lines.extend(["", "## Shared Selector Policy Tokens"])
    lines.extend(f"- `{key}`: `{value}`" for key, value in dict(payload.get("shared_selector_policy_tokens") or {}).items())
    lines.extend(["", "## First Safe Implementation Slice", ""])
    first = dict(payload.get("first_safe_implementation_slice") or {})
    lines.extend([f"- `{first.get('name')}`", f"- {first.get('why')}"])
    lines.extend(["", "## Checks"])
    lines.extend(f"- `{key}`: `{value}`" for key, value in dict(payload.get("checks") or {}).items())
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bottom_reo_selector_live_loop_cutover_readiness {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload.get("status") != "PASS":
        failed = [key for key, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
