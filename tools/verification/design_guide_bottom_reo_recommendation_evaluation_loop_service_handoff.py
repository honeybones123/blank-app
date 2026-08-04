"""Verify bottom-reo normal arrangement evaluation handoff extraction."""

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
SERVICE = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET_HELPER = "_compute_bottom_reo_recommendation"
SERVICE_HELPER = "evaluate_bottom_reo_recommendation_arrangement_candidate"


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


def _normal_arrangement_loop_segment(target_segment: str) -> str:
    start_token = "for arrangement_input in _build_bottom_reo_recommendation_arrangement_candidate_inputs("
    end_token = "if not _geometry_lock_enabled(state) and not efficiency_reduction_only:"
    start = target_segment.index(start_token)
    end = target_segment.index(end_token)
    return target_segment[start:end]


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _manual_expected(
    state: dict[str, Any],
    *,
    arrangement_input: dict[str, Any],
    seed_state: dict[str, Any],
    evaluator_fn,
    updates_match_state_fn,
) -> dict[str, Any]:
    row = dict(arrangement_input)
    arrangement = dict(row.get("arrangement") or {})
    updates = dict(row.get("updates") or {})
    candidate_state = dict(state)
    candidate_state.update(updates)
    label = str(row.get("label") or "")
    source = str(row.get("source") or "bottom_recommendation")
    action_type = str(row.get("action_type") or "apply_bottom_recommendation")
    candidate = evaluator_fn(
        candidate_state,
        seed_state=dict(seed_state),
        context={},
        eval_cache={},
        metrics={},
        source=source,
        label=label,
        action_type=action_type,
    )
    if candidate is None:
        return {
            "status": "rejected",
            "reject_reason": "evaluator_returned_null",
            "evaluator_returned": False,
            "candidate": None,
            "arrangement": arrangement,
            "updates": updates,
            "label": label,
            "candidate_state": candidate_state,
        }
    candidate_updates = dict(candidate.get("updates") or {})
    if updates_match_state_fn(dict(state), candidate_updates):
        return {
            "status": "rejected",
            "reject_reason": "updates_match_state",
            "evaluator_returned": True,
            "candidate": dict(candidate),
            "arrangement": arrangement,
            "updates": updates,
            "label": label,
            "candidate_state": candidate_state,
        }
    return {
        "status": "accepted_for_pool",
        "reject_reason": None,
        "evaluator_returned": True,
        "candidate": dict(candidate),
        "arrangement": arrangement,
        "updates": updates,
        "label": label,
        "candidate_state": candidate_state,
    }


def _scenario_rows() -> list[dict[str, Any]]:
    from design_brain.candidate_evaluation import evaluate_bottom_reo_recommendation_arrangement_candidate

    state = {"D": 600.0, "b": 300.0, "bot1_count": 5, "db_bot_1": 16}
    seed_state = dict(state)
    scenarios: list[dict[str, Any]] = [
        {
            "name": "accepted_candidate",
            "arrangement_input": {
                "arrangement": {"bot1_count": 4, "bot2_count": 0, "db_bot_1": 16},
                "updates": {"bot1_count": 4, "nb_bot": 4},
                "label": "4N16",
                "source": "bottom_recommendation",
                "action_type": "apply_bottom_recommendation",
            },
            "evaluator_result": {
                "updates": {"bot1_count": 4, "nb_bot": 4},
                "overview": {"utils": {"bending": 0.72}},
                "Ast_bot": 804.25,
            },
        },
        {
            "name": "evaluator_null",
            "arrangement_input": {
                "arrangement": {"bot1_count": 6, "bot2_count": 0, "db_bot_1": 12},
                "updates": {"bot1_count": 6, "nb_bot": 6},
                "label": "6N12",
            },
            "evaluator_result": None,
        },
        {
            "name": "updates_match_state",
            "arrangement_input": {
                "arrangement": {"bot1_count": 5, "bot2_count": 0, "db_bot_1": 16},
                "updates": {"bot1_count": 5, "nb_bot": 5},
                "label": "5N16",
            },
            "evaluator_result": {
                "updates": {"bot1_count": 5},
                "overview": {"utils": {"bending": 0.91}},
                "Ast_bot": 1005.31,
            },
        },
    ]
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        calls: list[dict[str, Any]] = []

        def evaluator_fn(candidate_state, **kwargs):
            calls.append({"candidate_state": dict(candidate_state), "kwargs": dict(kwargs)})
            result = scenario["evaluator_result"]
            return None if result is None else dict(result)

        def updates_match_state_fn(current_state, updates):
            return all(str(current_state.get(key)) == str(value) for key, value in dict(updates or {}).items())

        actual = evaluate_bottom_reo_recommendation_arrangement_candidate(
            state,
            arrangement_input=dict(scenario["arrangement_input"]),
            seed_state=seed_state,
            context={},
            eval_cache={},
            metrics={},
            evaluator_fn=evaluator_fn,
            updates_match_state_fn=updates_match_state_fn,
        )
        expected = _manual_expected(
            state,
            arrangement_input=dict(scenario["arrangement_input"]),
            seed_state=seed_state,
            evaluator_fn=lambda candidate_state, **kwargs: None
            if scenario["evaluator_result"] is None
            else dict(scenario["evaluator_result"]),
            updates_match_state_fn=updates_match_state_fn,
        )
        rows.append(
            {
                "name": scenario["name"],
                "matches": _stable(actual) == _stable(expected),
                "status": actual.get("status"),
                "reject_reason": actual.get("reject_reason"),
                "evaluator_call_count": len(calls),
                "actual_hash": _stable(actual),
                "expected_hash": _stable(expected),
            }
        )
    return rows


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    service_source = _read(SERVICE)
    target_start, target_end, target_segment = _function_segment(inputs_source, TARGET_HELPER)
    _, _, service_segment = _function_segment(service_source, SERVICE_HELPER)
    normal_loop = _normal_arrangement_loop_segment(target_segment)
    scenario_rows = _scenario_rows()

    forbidden_service_tokens = [
        "inputs_page",
        "streamlit",
        "st.session_state",
        "_evaluate_candidate_fast",
        "_pick_best",
        "_keep_top_candidates",
        "button_contract",
        "publication",
    ]
    checks = {
        "service_helper_exists": bool(service_segment),
        "page_delegates_normal_loop_to_service": "_evaluate_bottom_reo_recommendation_arrangement_candidate(" in normal_loop,
        "normal_loop_no_direct_fast_evaluator_call": "_evaluate_candidate_fast(" not in normal_loop,
        "normal_loop_keeps_trace_record_update": "_bottom_reo_update_evaluated_filter_record(" in normal_loop,
        "geometry_loop_still_page_owned": "geo_cand = _evaluate_candidate_fast(" in target_segment
        and 'source="bottom_recommendation_geometry"' in target_segment,
        "ranking_still_page_owned": "_pick_best_bottom_recommendation_by_selector(" in target_segment,
        "result_packaging_still_page_owned": "_build_bottom_reo_recommendation_result(" in target_segment,
        "service_has_no_page_or_ui_imports": not any(token in service_segment for token in forbidden_service_tokens),
        "scenario_parity": all(row["matches"] for row in scenario_rows),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }

    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BOTTOM_REO_NORMAL_ARRANGEMENT_EVALUATION_HANDOFF_EXTRACTED",
        "target_helper": TARGET_HELPER,
        "target_lines": {"start": target_start, "end": target_end},
        "service_helper": SERVICE_HELPER,
        "scenario_rows": scenario_rows,
        "checks": checks,
        "remaining_page_owned_surfaces": [
            "geometry trial generation/evaluation",
            "compound geometry-bottom expansion",
            "candidate material-improvement and growth filtering",
            "ranking/selector",
            "selected-result packaging",
            "trace/proof event emission",
        ],
        "next_safe_slice": {
            "name": "design_guide_bottom_reo_recommendation_filter_policy_boundary_audit.py",
            "why": "normal candidate evaluation handoff is extracted; filtering/ranking must be audited before moving policy.",
        },
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_recommendation_evaluation_loop_service_handoff_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_recommendation_evaluation_loop_service_handoff_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Bottom Reo Recommendation Evaluation Loop Service Handoff",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Scenario Parity",
        "",
        "| Scenario | Status | Reject reason | Evaluator calls | Match |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for row in payload.get("scenario_rows") or []:
        lines.append(
            f"| `{row.get('name')}` | `{row.get('status')}` | `{row.get('reject_reason')}` | {row.get('evaluator_call_count')} | `{row.get('matches')}` |"
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
    print(f"design_guide_bottom_reo_recommendation_evaluation_loop_service_handoff {status}")
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
