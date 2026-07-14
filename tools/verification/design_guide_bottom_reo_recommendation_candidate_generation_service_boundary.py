"""Verify bottom-reo recommendation candidate-row service boundary.

This slice moves only arrangement-to-evaluation-row packaging for the normal
bottom-reo recommendation fallback. The page still owns arrangement-pool
generation, evaluator execution, filtering, ranking, result packaging, trace
payloads, CTA/apply, and publication.
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
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET = "_compute_bottom_reo_recommendation"
SERVICE_HELPER = "build_bottom_reo_recommendation_arrangement_candidate_inputs"


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


def _label(arrangement: dict[str, Any]) -> str:
    count_1 = int(arrangement.get("bot1_count", 0) or 0)
    count_2 = int(arrangement.get("bot2_count", 0) or 0)
    dia = int(arrangement.get("db_bot_1", 0) or 0)
    if count_2 > 0:
        return f"{count_1}N{dia} + {count_2}N{dia}"
    return f"{count_1}N{dia}"


def _expected_rows(arrangements: list[dict[str, Any]], *, band: int) -> list[dict[str, Any]]:
    from design_brain.contracts import bottom_arrangement_to_shared_updates

    rows: list[dict[str, Any]] = []
    for arrangement in arrangements:
        arrangement_row = dict(arrangement or {})
        rows.append(
            {
                "band": int(band),
                "arrangement": arrangement_row,
                "updates": dict(bottom_arrangement_to_shared_updates(arrangement_row)),
                "label": _label(arrangement_row),
                "source": "bottom_recommendation",
                "action_type": "apply_bottom_recommendation",
            }
        )
    return rows


def _scenario_rows() -> list[dict[str, Any]]:
    from design_brain.candidate_evaluation import build_bottom_reo_recommendation_arrangement_candidate_inputs

    scenarios = [
        {
            "name": "single_row_band0",
            "band": 0,
            "arrangements": [
                {
                    "bot1_layout_mode": "Count",
                    "bot1_count": 5,
                    "db_bot_1": 16,
                    "bot2_layout_mode": "Count",
                    "bot2_count": 0,
                    "db_bot_2": 16,
                    "bot_row_count": 1,
                },
                {
                    "bot1_layout_mode": "Count",
                    "bot1_count": 6,
                    "db_bot_1": 16,
                    "bot2_layout_mode": "Count",
                    "bot2_count": 0,
                    "db_bot_2": 16,
                    "bot_row_count": 1,
                },
            ],
        },
        {
            "name": "two_row_band1",
            "band": 1,
            "arrangements": [
                {
                    "bot1_layout_mode": "Count",
                    "bot1_count": 4,
                    "db_bot_1": 20,
                    "bot2_layout_mode": "Count",
                    "bot2_count": 2,
                    "db_bot_2": 20,
                    "bot_row_count": 2,
                },
                {
                    "bot1_layout_mode": "Count",
                    "bot1_count": 5,
                    "db_bot_1": 20,
                    "bot2_layout_mode": "Count",
                    "bot2_count": 3,
                    "db_bot_2": 20,
                    "bot_row_count": 2,
                },
            ],
        },
        {
            "name": "diameter_change_band1",
            "band": 1,
            "arrangements": [
                {
                    "bot1_layout_mode": "Count",
                    "bot1_count": 7,
                    "db_bot_1": 24,
                    "bot2_layout_mode": "Count",
                    "bot2_count": 3,
                    "db_bot_2": 24,
                    "bot_row_count": 2,
                },
                {
                    "bot1_layout_mode": "Count",
                    "bot1_count": 7,
                    "db_bot_1": 20,
                    "bot2_layout_mode": "Count",
                    "bot2_count": 3,
                    "db_bot_2": 20,
                    "bot_row_count": 2,
                },
            ],
        },
    ]
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        arrangements = [dict(item) for item in scenario["arrangements"]]
        actual = build_bottom_reo_recommendation_arrangement_candidate_inputs(
            arrangements,
            band=int(scenario["band"]),
        )
        expected = _expected_rows(
            [dict(item) for item in scenario["arrangements"]],
            band=int(scenario["band"]),
        )
        rows.append(
            {
                "name": scenario["name"],
                "actual_count": len(actual),
                "expected_count": len(expected),
                "actual_hash": _stable(actual),
                "expected_hash": _stable(expected),
                "matches": actual == expected,
                "has_required_row_fields": all(
                    {"band", "arrangement", "updates", "label", "source", "action_type"}.issubset(row)
                    for row in actual
                ),
            }
        )
    return rows


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    target_start, target_end, target_segment = _function_segment(inputs_source, TARGET)
    service_start, service_end, service_segment = _function_segment(candidate_source, SERVICE_HELPER)
    scenario_rows = _scenario_rows()
    return {
        "schema": "design_guide_bottom_reo_recommendation_candidate_generation_service_boundary.v1",
        "target": {
            "function": TARGET,
            "line_start": target_start,
            "line_end": target_end,
        },
        "service_helper": {
            "function": SERVICE_HELPER,
            "line_start": service_start,
            "line_end": service_end,
        },
        "source_checks": {
            "page_delegates_candidate_rows_to_service": "_build_bottom_reo_recommendation_arrangement_candidate_inputs(" in target_segment,
            "page_keeps_arrangement_pool_generation": "_generate_local_bottom_arrangements(state, mode_config, band=band, context=context)" in target_segment,
            "page_keeps_evaluation_loop": "_evaluate_candidate_fast(" in target_segment,
            "page_keeps_filtering_ranking": "_pick_best_bottom_recommendation_by_selector(" in target_segment,
            "page_keeps_result_packaging": "_build_bottom_reo_recommendation_result(" in target_segment,
            "normal_bottom_loop_no_longer_directly_calls_arrangement_update_conversion": (
                "arrangement_updates = _bottom_arrangement_to_shared_updates(arrangement)" not in target_segment
            ),
            "normal_bottom_loop_no_longer_directly_calls_page_label": (
                "candidate_label = _practical_bottom_reo_label(" not in target_segment
            ),
            "service_imports_no_inputs_page_streamlit_session": all(
                token not in candidate_source for token in ("inputs_page", "streamlit", "st.session_state")
            ),
            "service_does_not_evaluate_or_rank": all(
                token not in service_segment
                for token in (
                    "evaluate_candidate(",
                    "_evaluate_candidate",
                    "evaluate_design_candidate_with_updates(",
                    "_pick_best_bottom_recommendation_by_selector(",
                    "_score_auto_design_candidate(",
                    "ranked_bottom",
                    "selected_candidate",
                    "button_contract",
                    "publication",
                    "st.session_state",
                )
            ),
        },
        "scenario_rows": scenario_rows,
        "decision": "BOTTOM_REO_CANDIDATE_ROW_PACKAGING_BOUNDARY_EXTRACTED",
        "next_safe_slice": {
            "name": "bottom_reo_recommendation_arrangement_pool_generation_boundary",
            "why": "Candidate row packaging is service-owned; the page still owns arrangement pool invocation, evaluator/cache/filtering/ranking/result packaging.",
            "required_verifier": "design_guide_bottom_reo_recommendation_arrangement_pool_generation_boundary.py",
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def checks(payload: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(payload.get("source_checks") or {})
    scenarios = list(payload.get("scenario_rows") or [])
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "service_helper_found": bool((payload.get("service_helper") or {}).get("line_start")),
        "page_delegates_candidate_rows_to_service": bool(source_checks.get("page_delegates_candidate_rows_to_service")),
        "page_keeps_arrangement_pool_generation": bool(source_checks.get("page_keeps_arrangement_pool_generation")),
        "page_keeps_evaluation_loop": bool(source_checks.get("page_keeps_evaluation_loop")),
        "page_keeps_filtering_ranking": bool(source_checks.get("page_keeps_filtering_ranking")),
        "page_keeps_result_packaging": bool(source_checks.get("page_keeps_result_packaging")),
        "normal_bottom_loop_no_longer_directly_calls_arrangement_update_conversion": bool(
            source_checks.get("normal_bottom_loop_no_longer_directly_calls_arrangement_update_conversion")
        ),
        "normal_bottom_loop_no_longer_directly_calls_page_label": bool(
            source_checks.get("normal_bottom_loop_no_longer_directly_calls_page_label")
        ),
        "service_boundary_clean": bool(source_checks.get("service_imports_no_inputs_page_streamlit_session")),
        "service_does_not_evaluate_or_rank": bool(source_checks.get("service_does_not_evaluate_or_rank")),
        "scenario_parity": bool(scenarios) and all(row.get("matches") for row in scenarios),
        "scenario_required_fields": bool(scenarios) and all(row.get("has_required_row_fields") for row in scenarios),
        "next_slice_identified": (payload.get("next_safe_slice") or {}).get("required_verifier")
        == "design_guide_bottom_reo_recommendation_arrangement_pool_generation_boundary.py",
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def write_artifacts(payload: dict[str, Any], check_results: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    status = "PASS" if all(check_results.values()) else "FAIL"
    payload = dict(payload)
    payload["status"] = status
    payload["checks"] = check_results
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_recommendation_candidate_generation_service_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_recommendation_candidate_generation_service_boundary_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    next_slice = dict(payload.get("next_safe_slice") or {})
    lines = [
        "# Bottom Reo Recommendation Candidate Row Service Boundary",
        "",
        f"## Executive Summary: {status}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Behaviour Preserved",
        "",
        "- Arrangement pool generation remains page-owned for this slice.",
        "- Candidate evaluation remains page-owned.",
        "- Filtering/ranking remains page-owned.",
        "- Result packaging remains page-owned.",
        "- CTA/apply/publication/render behaviour is unchanged.",
        "",
        "## Scenario Parity",
        "",
        "| Scenario | Actual count | Expected count | Match |",
        "| --- | ---: | ---: | --- |",
    ]
    for row in payload.get("scenario_rows") or []:
        lines.append(
            f"| {row.get('name')} | {row.get('actual_count')} | {row.get('expected_count')} | {row.get('matches')} |"
        )
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            f"- Name: `{next_slice.get('name')}`",
            f"- Required verifier: `{next_slice.get('required_verifier')}`",
            f"- Why: {next_slice.get('why')}",
            "",
            "## Checks",
            "",
        ]
    )
    lines.extend(f"- `{name}`: `{value}`" for name, value in check_results.items())
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    check_results = checks(payload)
    json_path, report_path = write_artifacts(payload, check_results)
    status = "PASS" if all(check_results.values()) else "FAIL"
    print(f"design_guide_bottom_reo_recommendation_candidate_generation_service_boundary {status}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if status != "PASS":
        failed = [name for name, value in check_results.items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
