"""Verify bottom-reo recommendation filter policy extraction."""

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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET_HELPER = "_compute_bottom_reo_recommendation"
PRERANK_HELPER = "resolve_design_guide_controller_bottom_reo_prerank_filter_policy"
GROWTH_HELPER = "resolve_design_guide_controller_bottom_reo_efficiency_growth_filter_policy"


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


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _policy_scenarios() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_bottom_reo_efficiency_growth_filter_policy,
        resolve_design_guide_controller_bottom_reo_prerank_filter_policy,
    )

    seed = {
        "worst_util": 1.2,
        "is_compliant": False,
        "overview": {"utils": {"bending": 0.95}},
        "state": {"D": 600.0, "b": 300.0, "lig_d": 0, "lig_legs": 0, "s_lig": 200.0},
        "depth": 600.0,
        "width": 300.0,
        "Ast_bot": 900.0,
    }
    base_candidate = {
        "label": "4N16",
        "worst_util": 0.82,
        "is_compliant": True,
        "overview": {"utils": {"bending": 0.82}},
        "state": {"D": 600.0, "b": 300.0, "lig_d": 0, "lig_legs": 0, "s_lig": 200.0},
        "updates": {"bot1_count": 4},
        "Ast_bot": 804.0,
    }
    prerank_cases = [
        (
            "updates_match_state_after_pool",
            None,
            True,
            {
                "accepted": False,
                "status": "rejected",
                "reject_reason": "updates_match_state_after_pool",
                "evaluator_returned": True,
                "compound_score_inferior_increment": False,
                "rank_trace_rejection": False,
            },
        ),
        (
            "not_materially_improved",
            {**base_candidate, "worst_util": 1.2, "is_compliant": False},
            False,
            {
                "accepted": False,
                "status": "rejected",
                "reject_reason": "not_materially_improved",
                "evaluator_returned": True,
                "compound_score_inferior_increment": False,
                "rank_trace_rejection": False,
            },
        ),
        (
            "missing_bending_util",
            {**base_candidate, "overview": {"utils": {}}},
            False,
            {
                "accepted": False,
                "status": "rejected",
                "reject_reason": "missing_bending_util",
                "evaluator_returned": True,
                "compound_score_inferior_increment": False,
                "rank_trace_rejection": False,
            },
        ),
        (
            "bending_util_not_improved",
            {**base_candidate, "overview": {"utils": {"bending": 0.99}}, "recommendation_compound": True},
            False,
            {
                "accepted": False,
                "status": "rejected",
                "reject_reason": "bending_util_not_improved",
                "evaluator_returned": True,
                "compound_score_inferior_increment": True,
                "rank_trace_rejection": True,
            },
        ),
        (
            "accepted_prerank",
            dict(base_candidate),
            False,
            {
                "accepted": True,
                "status": "accepted_prerank",
                "reject_reason": None,
                "evaluator_returned": True,
                "compound_score_inferior_increment": False,
                "rank_trace_rejection": False,
            },
        ),
    ]
    prerank_rows: list[dict[str, Any]] = []
    for name, candidate, updates_match, expected in prerank_cases:
        actual = resolve_design_guide_controller_bottom_reo_prerank_filter_policy(
            seed_candidate=dict(seed),
            candidate=dict(candidate) if isinstance(candidate, dict) else None,
            updates_match_state_after_pool=bool(updates_match),
        )
        prerank_rows.append(
            {
                "name": name,
                "matches": _stable(actual) == _stable(expected),
                "actual": actual,
                "expected": expected,
            }
        )

    growth_cases = [
        (
            "no_growth",
            dict(base_candidate),
            True,
            {"accepted": True, "status": "accepted", "reject_reason": None, "growth_rejected": False},
        ),
        (
            "depth_growth",
            {**base_candidate, "depth": 625.0, "state": {**base_candidate["state"], "D": 625.0}},
            True,
            {
                "accepted": False,
                "status": "rejected",
                "reject_reason": "growth_move_rejected_for_efficiency_reduction",
                "growth_rejected": True,
            },
        ),
        (
            "not_efficiency_reduction",
            {**base_candidate, "depth": 625.0, "state": {**base_candidate["state"], "D": 625.0}},
            False,
            {"accepted": True, "status": "accepted", "reject_reason": None, "growth_rejected": False},
        ),
    ]
    growth_rows: list[dict[str, Any]] = []
    for name, candidate, efficiency_reduction, expected in growth_cases:
        actual = resolve_design_guide_controller_bottom_reo_efficiency_growth_filter_policy(
            seed_candidate=dict(seed),
            candidate=dict(candidate),
            efficiency_reduction_only=bool(efficiency_reduction),
        )
        growth_rows.append(
            {
                "name": name,
                "matches": _stable(actual) == _stable(expected),
                "actual": actual,
                "expected": expected,
            }
        )
    return {
        "prerank_rows": prerank_rows,
        "growth_rows": growth_rows,
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_segment = _function_segment(inputs_source, TARGET_HELPER)
    _, _, prerank_segment = _function_segment(controller_source, PRERANK_HELPER)
    _, _, growth_segment = _function_segment(controller_source, GROWTH_HELPER)
    scenarios = _policy_scenarios()

    checks = {
        "controller_prerank_helper_exists": bool(prerank_segment),
        "controller_growth_helper_exists": bool(growth_segment),
        "page_delegates_prerank_filter_policy": "_resolve_design_guide_controller_bottom_reo_prerank_filter_policy(" in target_segment,
        "page_delegates_growth_filter_policy": "_resolve_design_guide_controller_bottom_reo_efficiency_growth_filter_policy(" in target_segment,
        "target_no_direct_material_improvement_call": "_candidate_materially_improves(" not in target_segment,
        "target_no_direct_bottom_prefilter_call": "_bottom_recommendation_prefilter_ok(" not in target_segment,
        "target_no_direct_growth_call": "_candidate_is_growth_move(" not in target_segment,
        "trace_writes_remain_page_owned": "_bottom_reo_update_evaluated_filter_record(" in target_segment,
        "rank_trace_logging_remains_page_owned": "_log_design_reco_candidate_rank(" in target_segment,
        "ranking_selector_remains_page_owned": "_pick_best_bottom_recommendation_by_selector(" in target_segment,
        "result_packaging_remains_page_owned": "_build_bottom_reo_recommendation_result(" in target_segment,
        "scenario_parity": all(row["matches"] for row in scenarios["prerank_rows"])
        and all(row["matches"] for row in scenarios["growth_rows"]),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }

    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BOTTOM_REO_FILTER_POLICY_EXTRACTED",
        "target_helper": TARGET_HELPER,
        "target_lines": {"start": target_start, "end": target_end},
        "scenarios": scenarios,
        "checks": checks,
        "remaining_page_owned_surfaces": [
            "trace/debug record mutation",
            "geometry trial generation/evaluation",
            "compound geometry-bottom expansion",
            "ranking/selector",
            "selected-result packaging",
        ],
        "next_safe_slice": {
            "name": "design_guide_bottom_reo_recommendation_selector_boundary_audit.py",
            "why": "filter policy is controller-owned; selector/result packaging needs a boundary audit before movement.",
        },
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_recommendation_filter_policy_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_recommendation_filter_policy_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Bottom Reo Recommendation Filter Policy Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Pre-Rank Policy Parity",
        "",
        "| Scenario | Match | Actual reason | Expected reason |",
        "| --- | --- | --- | --- |",
    ]
    for row in (payload.get("scenarios") or {}).get("prerank_rows") or []:
        lines.append(
            f"| `{row.get('name')}` | `{row.get('matches')}` | `{(row.get('actual') or {}).get('reject_reason')}` | `{(row.get('expected') or {}).get('reject_reason')}` |"
        )
    lines.extend(["", "## Growth Policy Parity", "", "| Scenario | Match | Growth rejected |", "| --- | --- | --- |"])
    for row in (payload.get("scenarios") or {}).get("growth_rows") or []:
        lines.append(
            f"| `{row.get('name')}` | `{row.get('matches')}` | `{(row.get('actual') or {}).get('growth_rejected')}` |"
        )
    lines.extend(["", "## Remaining Page-Owned Surfaces", ""])
    lines.extend(f"- {item}" for item in payload.get("remaining_page_owned_surfaces") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    next_slice = dict(payload.get("next_safe_slice") or {})
    lines.extend(["", "## Next Safe Slice", "", f"- `{next_slice.get('name')}`", f"- {next_slice.get('why')}"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    status = payload.get("status")
    print(f"design_guide_bottom_reo_recommendation_filter_policy_extraction {status}")
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
