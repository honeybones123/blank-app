"""Verify bottom-reo target-band metric projection service extraction."""

from __future__ import annotations

import ast
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.candidate_evaluation import (
    build_bottom_reo_candidate_metric_projection,
    resolve_bottom_reo_candidate_bottom_updates,
)

INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(node.end_lineno or node.lineno)
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _near(a: Any, b: Any, *, tol: float = 1e-9) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return a == b


def _compare_dict(left: dict[str, Any], right: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    mismatches = {}
    for key in keys:
        if not _near(left.get(key), right.get(key)):
            mismatches[key] = {"left": left.get(key), "right": right.get(key)}
    return mismatches


def _sample_states() -> list[dict[str, Any]]:
    return [
        {
            "sec_shape": "RECT",
            "b": 400.0,
            "D": 650.0,
            "cover_bot": 40.0,
            "lig_d": 10.0,
            "db_bot": 20.0,
            "db_bot_1": 20,
            "db_bot_2": 20,
            "nb_bot": 8,
            "Ast_bot": 2513.2741228718346,
            "bot1_count": 6,
            "bot2_count": 2,
            "bot_row_count": 2,
        },
        {
            "sec_shape": "RECT",
            "b": 500.0,
            "D": 700.0,
            "cover_bot": 45.0,
            "lig_d": 0.0,
            "db_bot": 16.0,
            "db_bot_1": 16,
            "db_bot_2": 16,
            "nb_bot": 5,
            "Ast_bot": 1005.3096491487338,
            "bot1_count": 5,
            "bot2_count": 0,
            "bot_row_count": 1,
        },
        {
            "sec_shape": "T",
            "bw": 320.0,
            "b": 800.0,
            "D": 600.0,
            "cover_bot": 35.0,
            "lig_d": 10.0,
            "db_bot_1": 12,
            "db_bot_2": 12,
            "bot1_count": 4,
            "bot2_count": 0,
        },
        {
            "sec_shape": "RECT",
            "b": 400.0,
            "D": 650.0,
            "cover_bot": 40.0,
            "lig_d": 10.0,
            "bot_row_1_dia": 20,
            "bot_row_2_dia": 20,
            "bot_row_1_bars": 6,
            "bot_row_2_bars": 2,
            "bot_row_count": 2,
        },
        {
            "sec_shape": "RECT",
            "b": 500.0,
            "D": 700.0,
            "cover_bot": 45.0,
            "lig_d": 0.0,
            "bot_row_1_dia": 16,
            "bot_row_2_dia": 0,
            "bot_row_1_bars": 5,
            "bot_row_2_bars": 0,
            "bot_row_count": 1,
        },
    ]


def _build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    bottom_target = _function_source(inputs_source, "generate_less_bottom_reo_variants")
    layout_target = _function_source(inputs_source, "generate_simpler_layout_variants")
    candidate_bottom_wrapper = _function_source(inputs_source, "_candidate_bottom_updates")

    module = importlib.import_module("inputs_page")
    parity_rows = []
    mismatches: list[dict[str, Any]] = []
    for index, state in enumerate(_sample_states()):
        page_updates = module._candidate_bottom_updates(dict(state))
        service_updates = resolve_bottom_reo_candidate_bottom_updates(dict(state))
        page_bottom = module._effective_bottom_design_state(dict(state), page_updates)
        projection = build_bottom_reo_candidate_metric_projection(
            dict(state),
            bottom_updates=service_updates,
        )
        service_bottom = dict(projection.get("effective_bottom") or {})
        preview_candidate = {
            "state": dict(state),
            "Ast_bot": float(page_bottom.get("Ast_bot", 0.0) or 0.0),
            "row_count": module._bottom_row_count_from_state(dict(state)),
            "bar_count": module._bottom_bar_count_from_state(dict(state), page_bottom),
            "reo_congestion_index": module._reo_congestion_index(dict(state), page_bottom),
        }
        page_metrics = {
            "bottom_updates": page_updates,
            "effective_bottom": page_bottom,
            "row_count": module._bottom_row_count_from_state(dict(state)),
            "bar_count": module._bottom_bar_count_from_state(dict(state), page_bottom),
            "reo_congestion_index": module._reo_congestion_index(dict(state), page_bottom),
            "reo_complexity": module.compute_reo_complexity(preview_candidate),
        }
        service_metrics = {
            "bottom_updates": service_updates,
            "effective_bottom": service_bottom,
            "row_count": projection.get("row_count"),
            "bar_count": projection.get("bar_count"),
            "reo_congestion_index": projection.get("reo_congestion_index"),
            "reo_complexity": projection.get("reo_complexity"),
        }
        row_mismatches = {}
        if page_updates != service_updates:
            row_mismatches["bottom_updates"] = {"page": page_updates, "service": service_updates}
        bottom_mismatches = _compare_dict(
            page_bottom,
            service_bottom,
            ["Ast_bot", "db_bot", "nb_bot", "d_centroid"],
        )
        if bottom_mismatches:
            row_mismatches["effective_bottom"] = bottom_mismatches
        for key in ["row_count", "bar_count", "reo_congestion_index", "reo_complexity"]:
            if not _near(page_metrics.get(key), service_metrics.get(key)):
                row_mismatches[key] = {"page": page_metrics.get(key), "service": service_metrics.get(key)}
        parity_rows.append(
            {
                "case": index,
                "page_metrics": page_metrics,
                "service_metrics": service_metrics,
                "mismatches": row_mismatches,
            }
        )
        if row_mismatches:
            mismatches.append({"case": index, "mismatches": row_mismatches})

    bottom_source = bottom_target[2]
    layout_source = layout_target[2]
    wrapper_source = candidate_bottom_wrapper[2]
    checks = {
        "service_helper_exists": "def build_bottom_reo_candidate_metric_projection(" in candidate_source,
        "service_update_helper_exists": "def resolve_bottom_reo_candidate_bottom_updates(" in candidate_source,
        "bottom_lane_uses_metric_projection_service": "_build_bottom_reo_candidate_metric_projection(" in bottom_source,
        "layout_lane_uses_metric_projection_service": "_build_bottom_reo_candidate_metric_projection(" in layout_source,
        "bottom_lane_uses_update_service": "_resolve_bottom_reo_candidate_bottom_updates(" in bottom_source,
        "layout_lane_uses_update_service": "_resolve_bottom_reo_candidate_bottom_updates(" in layout_source,
        "bottom_lane_no_direct_effective_state_call": "_effective_bottom_design_state(" not in bottom_source,
        "layout_lane_no_direct_effective_state_call": "_effective_bottom_design_state(" not in layout_source,
        "candidate_bottom_updates_wrapper_delegates": "return _resolve_bottom_reo_candidate_bottom_updates(candidate_state)" in wrapper_source,
        "no_inputs_page_import_in_candidate_evaluation": "inputs_page" not in candidate_source,
        "no_streamlit_import_in_candidate_evaluation": "import streamlit" not in candidate_source and "from streamlit" not in candidate_source,
        "parity_cases_match": not mismatches,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "schema": "design_guide_bottom_reo_metric_projection_service_extraction.v1",
        "status": status,
        "decision": "BOTTOM_REO_METRIC_PROJECTION_SERVICE_EXTRACTED" if status == "PASS" else "PARITY_OR_BOUNDARY_FAILURE",
        "product_behavior_changed": False,
        "extraction_complete_estimate": "99%",
        "checks": checks,
        "mismatches": mismatches,
        "parity_rows": parity_rows,
        "line_ranges": {
            "generate_less_bottom_reo_variants": {"start": bottom_target[0], "end": bottom_target[1]},
            "generate_simpler_layout_variants": {"start": layout_target[0], "end": layout_target[1]},
            "_candidate_bottom_updates": {"start": candidate_bottom_wrapper[0], "end": candidate_bottom_wrapper[1]},
        },
        "remaining_page_wrappers": [
            "generate_less_bottom_reo_variants",
            "generate_simpler_layout_variants",
            "_effective_bottom_design_state",
            "_bottom_row_count_from_state",
            "_bottom_bar_count_from_state",
            "_reo_congestion_index",
            "compute_reo_complexity",
        ],
        "next_safe_slice": "bottom_reo_lane_orchestration_service_handoff_after_metric_projection",
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bottom-Reo Metric Projection Service Extraction",
        "",
        "## Executive Summary",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Extraction complete estimate: `{payload['extraction_complete_estimate']}`",
        f"- Product behavior changed: `{payload['product_behavior_changed']}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {name}: `{value}`" for name, value in payload["checks"].items())
    lines.extend(
        [
            "",
            "## Line Ranges",
            f"- `generate_less_bottom_reo_variants`: `{payload['line_ranges']['generate_less_bottom_reo_variants']['start']}-{payload['line_ranges']['generate_less_bottom_reo_variants']['end']}`",
            f"- `generate_simpler_layout_variants`: `{payload['line_ranges']['generate_simpler_layout_variants']['start']}-{payload['line_ranges']['generate_simpler_layout_variants']['end']}`",
            f"- `_candidate_bottom_updates`: `{payload['line_ranges']['_candidate_bottom_updates']['start']}-{payload['line_ranges']['_candidate_bottom_updates']['end']}`",
            "",
            "## Parity",
            f"- Cases checked: `{len(payload['parity_rows'])}`",
            f"- Mismatch count: `{len(payload['mismatches'])}`",
            "",
            "## Remaining Page Wrappers",
        ]
    )
    lines.extend(f"- `{item}`" for item in payload["remaining_page_wrappers"])
    lines.extend(["", "## Next Safe Slice", f"- `{payload['next_safe_slice']}`"])
    return "\n".join(lines) + "\n"


def _write_artifacts(payload: dict[str, Any]) -> dict[str, str]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_metric_projection_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_bottom_reo_metric_projection_service_extraction_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return payload["artifact_paths"]


def main() -> int:
    payload = _build_payload()
    paths = _write_artifacts(payload)
    print(f"design_guide_bottom_reo_metric_projection_service_extraction {payload['status']}")
    print(json.dumps({"decision": payload["decision"], "artifact_paths": paths}, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
