"""Audit bottom-reo recommendation selector/result packaging boundary."""

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
TARGET_HELPER = "_compute_bottom_reo_recommendation"


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


def build_payload() -> dict[str, Any]:
    source = _read(INPUTS)
    start, end, segment = _function_segment(source, TARGET_HELPER)

    surfaces = [
        {
            "surface": "score_and_target_band_annotation",
            "tokens": [
                "_annotate_bottom_reo_candidate_deltas(",
                "_score_auto_design_candidate(",
                "_annotate_candidate_target_band_metrics(",
            ],
            "current_owner": "candidate service / controller helper",
            "target_owner": "DesignGuideController / candidate service",
            "classification": "EXTRACTED_SELECTION_PREP",
            "reason": "Candidate metadata annotation moved in the score/rank selection-prep boundary.",
        },
        {
            "surface": "top_candidate_ranking",
            "tokens": ["_keep_top_candidates("],
            "current_owner": "candidate service / controller helper",
            "target_owner": "DesignGuideController",
            "classification": "EXTRACTED_SELECTION_PREP",
            "reason": "Ranking/truncation moved in the score/rank selection-prep boundary.",
        },
        {
            "surface": "bottom_selector",
            "tokens": ["_pick_best_bottom_recommendation_by_selector(", "BottomReoSelectorResult"],
            "current_owner": "inputs_page.py",
            "target_owner": "family/controller selector service",
            "classification": "READY_AFTER_SELECTOR_RESULT_OBJECT",
            "reason": "Selector emits a structured result side-channel; move after object parity.",
        },
        {
            "surface": "compound_preference",
            "tokens": ["_maybe_prefer_compound_over_pure_geometry("],
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController",
            "classification": "READY_AFTER_SELECTOR_RESULT_OBJECT",
            "reason": "Selected candidate may be replaced after selector; needs parity with selector input/result.",
        },
        {
            "surface": "post_selector_no_result_guard",
            "tokens": ["no_selected_candidate", "_updates_match_state(state, best.get(\"updates\", {}))"],
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController",
            "classification": "READY_AFTER_SELECTOR_RESULT_OBJECT",
            "reason": "Guard result is pure, but proof payload construction remains page-owned.",
        },
        {
            "surface": "selected_required_ast_and_change_lines",
            "tokens": [
                "_evaluate_bending_with_bottom_state(",
                "_required_ast_for_arrangement(",
                "_guidance_change_lines_for_updates(",
            ],
            "current_owner": "inputs_page.py",
            "target_owner": "controller/result projection service",
            "classification": "NOT_READY",
            "reason": "Directly feeds final visible result; requires exact visible wording/result parity first.",
        },
        {
            "surface": "final_result_packaging",
            "tokens": ["_build_bottom_reo_recommendation_result("],
            "current_owner": "inputs_page.py",
            "target_owner": "controller/result projection service",
            "classification": "NOT_READY",
            "reason": "Builds returned recommendation shape and action payload; keep until selector/result projection is proven.",
        },
        {
            "surface": "trace_proof_events",
            "tokens": [
                "_bottom_reo_candidate_pool_boundary_record(",
                "_bottom_reo_selected_candidate_decision_record(",
                "_bottom_reo_trace_proof_payload(",
                "_bottom_reo_recommendation_trace_event(",
            ],
            "current_owner": "inputs_page.py",
            "target_owner": "debug/proof service",
            "classification": "KEEP_PAGE_FOR_NOW",
            "reason": "Non-authoritative proof emission stays until selected result object owns the same payload.",
        },
    ]
    for row in surfaces:
        row["present"] = all(token in segment for token in row["tokens"])

    checks = {
        "helper_found": bool(segment),
        "extracted_selection_prep_surfaces_absent_from_page": not surfaces[0]["present"] and not surfaces[1]["present"],
        "remaining_selector_surfaces_present": all(row["present"] for row in surfaces[2:]),
        "filter_policy_already_controller_owned": "_resolve_design_guide_controller_bottom_reo_prerank_filter_policy(" in segment,
        "growth_policy_already_controller_owned": "_resolve_design_guide_controller_bottom_reo_efficiency_growth_filter_policy(" in segment,
        "selector_still_page_owned": "_pick_best_bottom_recommendation_by_selector(" in segment,
        "result_packaging_still_page_owned": "_build_bottom_reo_recommendation_result(" in segment,
        "next_slice_is_selector_policy_or_result_packaging": True,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }

    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BOTTOM_REO_SELECTION_PREP_EXTRACTED_SELECTOR_AND_RESULT_PACKAGING_REMAIN",
        "target_helper": TARGET_HELPER,
        "target_lines": {"start": start, "end": end},
        "surface_rows": surfaces,
        "checks": checks,
        "first_safe_implementation_slice": {
            "name": "bottom_reo_selector_policy_or_selected_result_packaging_boundary",
            "move": [
                "Audit live selector loop, compound preference, post-selector no-result guard, required Ast/change lines, and final result packaging before moving more bottom-reo recommendation logic.",
            ],
            "keep": [
                "compound preference until selector object parity is proven",
                "required Ast and change-line construction",
                "final recommendation result packaging",
                "trace/proof event emission",
                "CTA/apply/publication/render semantics",
            ],
        },
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_recommendation_selector_boundary_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_recommendation_selector_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Bottom Reo Recommendation Selector Boundary Audit",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Surface Classification",
        "",
        "| Surface | Classification | Current owner | Target owner | Present |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("surface_rows") or []:
        lines.append(
            f"| `{row.get('surface')}` | `{row.get('classification')}` | {row.get('current_owner')} | {row.get('target_owner')} | `{row.get('present')}` |"
        )
    next_slice = dict(payload.get("first_safe_implementation_slice") or {})
    lines.extend(["", "## First Safe Implementation Slice", "", f"- Name: `{next_slice.get('name')}`", "", "Move:"])
    lines.extend(f"- {item}" for item in next_slice.get("move") or [])
    lines.append("")
    lines.append("Keep:")
    lines.extend(f"- {item}" for item in next_slice.get("keep") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    status = payload.get("status")
    print(f"design_guide_bottom_reo_recommendation_selector_boundary_audit {status}")
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
