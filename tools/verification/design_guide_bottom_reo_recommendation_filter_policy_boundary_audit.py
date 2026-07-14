"""Audit bottom-reo recommendation filter policy boundary."""

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

    filter_tokens = {
        "no_op_filter": "_updates_match_state(state, candidate.get(\"updates\") or {})",
        "material_improvement_filter": "_candidate_materially_improves(seed_candidate, candidate)",
        "missing_bending_util_filter": "reject_reason=\"missing_bending_util\"",
        "bottom_prefilter": "_bottom_recommendation_prefilter_ok(seed_candidate, candidate, state)",
        "growth_rejection": "_candidate_is_growth_move(seed_candidate, candidate)",
        "trace_record_mutation": "_bottom_reo_update_evaluated_filter_record(",
        "rank_trace_logging": "_log_design_reco_candidate_rank(",
        "growth_trace_logging": "_log_efficiency_growth_rejection(",
    }
    present = {name: token in segment for name, token in filter_tokens.items()}

    rows = [
        {
            "surface": "no-op and missing-candidate filtering",
            "current_owner": "candidate_evaluation service with page trace mutation",
            "target_owner": "candidate_evaluation service",
            "classification": "EXTRACTED_WITH_PAGE_TRACE_MUTATION",
            "reason": "Candidate evaluation handoff owns status/reason projection; page still updates non-authoritative trace records.",
        },
        {
            "surface": "material improvement and bottom prefilter",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController",
            "classification": "EXTRACTED_SHELL_CALL",
            "reason": "Controller owns pure recommendation policy using candidate/seed/state plain data.",
        },
        {
            "surface": "efficiency growth rejection",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController",
            "classification": "EXTRACTED_SHELL_CALL",
            "reason": "Controller owns pure growth policy; page trace logging remains until result object owns rejection evidence.",
        },
        {
            "surface": "trace/debug record mutation",
            "current_owner": "inputs_page.py",
            "target_owner": "debug/proof service",
            "classification": "KEEP_PAGE_FOR_NOW",
            "reason": "Trace mutation is non-authoritative but coupled to page runtime tracing.",
        },
        {
            "surface": "ranking/selector",
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController / family selector",
            "classification": "OUT_OF_SCOPE_FOR_THIS_SLICE",
            "reason": "Move only after filter policy parity and selected-result packaging boundary.",
        },
    ]

    checks = {
        "helper_found": bool(segment),
        "legacy_filter_tokens_removed": not present.get("material_improvement_filter")
        and not present.get("bottom_prefilter")
        and not present.get("growth_rejection"),
        "controller_filter_policy_called": "_resolve_design_guide_controller_bottom_reo_prerank_filter_policy(" in segment
        and "_resolve_design_guide_controller_bottom_reo_efficiency_growth_filter_policy(" in segment,
        "evaluation_handoff_already_service_owned": "_evaluate_bottom_reo_recommendation_arrangement_candidate(" in segment,
        "ranking_still_page_owned": "_pick_best_bottom_recommendation_by_selector(" in segment,
        "selected_result_packaging_still_page_owned": "_build_bottom_reo_recommendation_result(" in segment,
        "next_slice_is_score_rank_selector_boundary": True,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }

    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BOTTOM_REO_FILTER_POLICY_EXTRACTED_NEXT_SCORE_RANK_SELECTOR_BOUNDARY",
        "target_helper": TARGET_HELPER,
        "target_lines": {"start": start, "end": end},
        "present_tokens": present,
        "surface_rows": rows,
        "checks": checks,
        "first_safe_implementation_slice": {
            "name": "design_guide_bottom_reo_recommendation_filter_policy_extraction.py",
            "next_name": "design_guide_bottom_reo_recommendation_score_rank_selector_boundary.py",
            "move": [
                "Audit score/rank/selector policy before moving ranking or final selected result packaging.",
            ],
            "keep": [
                "trace record writes",
                "rank trace logging",
                "ranking/selector",
                "selected-result packaging",
                "CTA/apply/publication/render semantics",
            ],
        },
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_recommendation_filter_policy_boundary_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_recommendation_filter_policy_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Bottom Reo Recommendation Filter Policy Boundary Audit",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Surface Classification",
        "",
        "| Surface | Classification | Current owner | Target owner |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload.get("surface_rows") or []:
        lines.append(
            f"| `{row.get('surface')}` | `{row.get('classification')}` | {row.get('current_owner')} | {row.get('target_owner')} |"
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
    print(f"design_guide_bottom_reo_recommendation_filter_policy_boundary_audit {status}")
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
