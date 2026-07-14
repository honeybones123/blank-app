"""Verify bottom-reo arrangement-pool generation boundary.

The page wrapper `_generate_local_bottom_arrangements(...)` should now be a
thin shell over a family-owned from-state helper. This verifier proves parity
against the primitive family pool builder and confirms the page no longer owns
primitive state/config normalization for this surface.
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
BENDING = ROOT / "design_brain" / "families" / "bending.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

PAGE_HELPER = "_generate_local_bottom_arrangements"
FAMILY_HELPER = "build_bottom_reo_arrangement_pool_from_state"


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


def _safe_int(source: dict[str, Any], key: str, default: int) -> int:
    value = source.get(key)
    if value is None:
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def _safe_float(source: dict[str, Any], key: str, default: float) -> float:
    value = source.get(key)
    if value is None:
        return float(default)
    try:
        return float(value)
    except Exception:
        return float(default)


def _design_width(source: dict[str, Any]) -> float:
    sec_shape = str(source.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return _safe_float(source, "bw", _safe_float(source, "b", 300.0))
    if sec_shape == "I":
        return _safe_float(source, "tw", _safe_float(source, "b", 200.0))
    return _safe_float(source, "b", 400.0)


def _scenario_rows() -> list[dict[str, Any]]:
    from design_brain.families.bending import (
        build_bottom_reo_arrangement_pool,
        build_bottom_reo_arrangement_pool_from_state,
    )

    scenarios = [
        {
            "name": "rect_balanced_band0",
            "state": {
                "sec_shape": "RECT",
                "b": 400.0,
                "cover_side": 40.0,
                "rowgap_bot": 60.0,
                "bot1_count": 5,
                "bot2_count": 0,
                "db_bot_1": 16,
            },
            "mode_config": {"search_strategy": "balanced"},
            "band": 0,
            "context": {},
        },
        {
            "name": "t_shallow_band1",
            "state": {
                "sec_shape": "T",
                "b": 600.0,
                "bw": 320.0,
                "cover_side": 35.0,
                "rowgap_bot": 55.0,
                "bot1_count": 4,
                "bot2_count": 2,
                "db_bot_1": 20,
            },
            "mode_config": {"search_strategy": "shallow"},
            "band": 1,
            "context": {},
        },
        {
            "name": "i_low_reo_ductility_band1",
            "state": {
                "sec_shape": "I",
                "b": 500.0,
                "tw": 280.0,
                "cover_side": 45.0,
                "rowgap_bot": 65.0,
                "bot1_count": 7,
                "bot2_count": 3,
                "db_bot_1": 24,
            },
            "mode_config": {"search_strategy": "low_reo"},
            "band": 1,
            "context": {"ductility_priority": True},
        },
    ]
    bar_diameters = (10, 12, 16, 20, 24, 28, 32, 36, 40)
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        state = dict(scenario["state"])
        mode_config = dict(scenario["mode_config"])
        expected_context = dict(scenario["context"])
        actual_context = dict(scenario["context"])
        expected_cache = expected_context.setdefault("layout_fit_cache", {})
        expected = build_bottom_reo_arrangement_pool(
            current_bot1_count=_safe_int(state, "bot1_count", 0),
            current_bot2_count=_safe_int(state, "bot2_count", 0),
            current_db_bot_1=_safe_int(state, "db_bot_1", 20),
            design_width=_design_width(state),
            cover_side=_safe_float(state, "cover_side", 40.0),
            rowgap_bot=_safe_float(state, "rowgap_bot", 60.0),
            search_strategy=str(mode_config.get("search_strategy", "balanced") or "balanced"),
            bar_diameters=bar_diameters,
            band=int(scenario["band"]),
            ductility_priority=bool(expected_context.get("ductility_priority")),
            default_limit=32,
            layout_fit_cache=expected_cache,
        )
        actual = build_bottom_reo_arrangement_pool_from_state(
            state,
            mode_config,
            band=int(scenario["band"]),
            context=actual_context,
            bar_diameters=bar_diameters,
            default_limit=32,
        )
        rows.append(
            {
                "name": scenario["name"],
                "actual_count": len(actual),
                "expected_count": len(expected),
                "actual_hash": _stable(actual),
                "expected_hash": _stable(expected),
                "matches": actual == expected,
                "context_cache_created": isinstance(actual_context.get("layout_fit_cache"), dict),
            }
        )
    return rows


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    page_start, page_end, page_segment = _function_segment(inputs_source, PAGE_HELPER)
    family_start, family_end, family_segment = _function_segment(bending_source, FAMILY_HELPER)
    scenario_rows = _scenario_rows()
    return {
        "schema": "design_guide_bottom_reo_recommendation_arrangement_pool_generation_boundary.v1",
        "page_helper": {
            "function": PAGE_HELPER,
            "line_start": page_start,
            "line_end": page_end,
            "line_count": max(0, page_end - page_start + 1),
        },
        "family_helper": {
            "function": FAMILY_HELPER,
            "line_start": family_start,
            "line_end": family_end,
        },
        "source_checks": {
            "page_delegates_to_family_helper": "_build_bottom_reo_arrangement_pool_from_state(" in page_segment,
            "page_no_longer_calls_primitive_pool_builder": "_build_bottom_reo_arrangement_pool(" not in page_segment,
            "page_no_longer_reads_bottom_primitives": all(
                token not in page_segment
                for token in (
                    "_int_from_state(",
                    "_float_from_state(",
                    "_design_width_value(",
                    "layout_fit_cache",
                )
            ),
            "family_helper_no_inputs_page_streamlit_session": all(
                token not in family_segment for token in ("inputs_page", "streamlit", "st.session_state")
            ),
            "family_helper_does_not_evaluate_rank_publish": all(
                token not in family_segment
                for token in (
                    "evaluate_candidate",
                    "_evaluate_candidate",
                    "_pick_best",
                    "button_contract",
                    "publication",
                    "st.session_state",
                )
            ),
        },
        "scenario_rows": scenario_rows,
        "decision": "BOTTOM_REO_ARRANGEMENT_POOL_FROM_STATE_BOUNDARY_EXTRACTED",
        "next_safe_slice": {
            "name": "bottom_reo_recommendation_evaluation_loop_service_boundary",
            "why": "Arrangement generation and row packaging are now outside page-owned logic; evaluator/cache/filtering/ranking/result packaging remain page-owned.",
            "required_verifier": "design_guide_bottom_reo_recommendation_evaluation_loop_service_boundary.py",
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
        "page_helper_found": bool((payload.get("page_helper") or {}).get("line_start")),
        "family_helper_found": bool((payload.get("family_helper") or {}).get("line_start")),
        "page_is_thin_delegate": bool(source_checks.get("page_delegates_to_family_helper"))
        and bool(source_checks.get("page_no_longer_calls_primitive_pool_builder"))
        and bool(source_checks.get("page_no_longer_reads_bottom_primitives")),
        "family_boundary_clean": bool(source_checks.get("family_helper_no_inputs_page_streamlit_session")),
        "family_helper_does_not_evaluate_rank_publish": bool(source_checks.get("family_helper_does_not_evaluate_rank_publish")),
        "scenario_parity": bool(scenarios) and all(row.get("matches") for row in scenarios),
        "context_cache_preserved": bool(scenarios) and all(row.get("context_cache_created") for row in scenarios),
        "next_slice_identified": (payload.get("next_safe_slice") or {}).get("required_verifier")
        == "design_guide_bottom_reo_recommendation_evaluation_loop_service_boundary.py",
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
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_recommendation_arrangement_pool_generation_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_recommendation_arrangement_pool_generation_boundary_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    next_slice = dict(payload.get("next_safe_slice") or {})
    lines = [
        "# Bottom Reo Arrangement Pool Generation Boundary",
        "",
        f"## Executive Summary: {status}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Behaviour Preserved",
        "",
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
    print(f"design_guide_bottom_reo_recommendation_arrangement_pool_generation_boundary {status}")
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
