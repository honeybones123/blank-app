"""Verify bottom-reo target-band lane orchestration service handoff."""

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

from design_brain.candidate_evaluation import generate_bottom_reo_target_band_candidate_states


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


def _candidate_identity_rows(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in candidates:
        state = dict(item or {})
        rows.append(
            {
                "b": state.get("b"),
                "D": state.get("D"),
                "bot1_count": state.get("bot1_count"),
                "bot2_count": state.get("bot2_count"),
                "db_bot_1": state.get("db_bot_1"),
                "db_bot_2": state.get("db_bot_2"),
                "bot_row_count": state.get("bot_row_count"),
            }
        )
    return rows


def _sample_current_candidate() -> dict[str, Any]:
    state = {
        "sec_shape": "RECT",
        "b": 400.0,
        "D": 650.0,
        "cover_bot": 40.0,
        "cover_side": 40.0,
        "rowgap_bot": 60.0,
        "lig_d": 10.0,
        "db_bot": 20.0,
        "db_bot_1": 20,
        "db_bot_2": 20,
        "nb_bot": 8,
        "Ast_bot": 2513.2741228718346,
        "bot1_count": 6,
        "bot2_count": 2,
        "bot_row_count": 2,
    }
    return {
        "state": state,
        "Ast_bot": 2513.2741228718346,
        "row_count": 2,
        "bar_count": 8,
        "reo_congestion_index": 10.9,
        "reo_complexity": 154.8,
    }


def _build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    bottom_range = _function_source(inputs_source, "generate_less_bottom_reo_variants")
    layout_range = _function_source(inputs_source, "generate_simpler_layout_variants")
    bottom_source = bottom_range[2]
    layout_source = layout_range[2]

    module = importlib.import_module("inputs_page")
    current_candidate = _sample_current_candidate()
    mode_config = {
        "search_strategy": "balanced",
        "practicality_congestion_limit": 20.0,
    }
    context = {"layout_fit_cache": {}}
    wrapper_bottom = module.generate_less_bottom_reo_variants(
        dict(current_candidate),
        dict(mode_config),
        dict(context),
    )
    service_bottom = generate_bottom_reo_target_band_candidate_states(
        current_candidate=dict(current_candidate),
        mode_config=dict(mode_config),
        context=dict(context),
        lane="less_bottom_reo",
        candidate_key_fn=module._make_auto_design_candidate_key,
        bar_diameters=module.REO_BAR_DIAS,
        default_stage_candidate_limit=module.AUTO_DESIGN_MAX_STAGE_CANDIDATES,
    )
    wrapper_layout = module.generate_simpler_layout_variants(
        dict(current_candidate),
        dict(mode_config),
        dict(context),
    )
    service_layout = generate_bottom_reo_target_band_candidate_states(
        current_candidate=dict(current_candidate),
        mode_config=dict(mode_config),
        context=dict(context),
        lane="simpler_layout",
        candidate_key_fn=module._make_auto_design_candidate_key,
        bar_diameters=module.REO_BAR_DIAS,
        default_stage_candidate_limit=module.AUTO_DESIGN_MAX_STAGE_CANDIDATES,
    )
    bottom_wrapper_rows = _candidate_identity_rows(wrapper_bottom)
    bottom_service_rows = _candidate_identity_rows(service_bottom)
    layout_wrapper_rows = _candidate_identity_rows(wrapper_layout)
    layout_service_rows = _candidate_identity_rows(service_layout)
    checks = {
        "service_helper_exists": "def generate_bottom_reo_target_band_candidate_states(" in candidate_source,
        "bottom_wrapper_delegates_to_service": "_generate_bottom_reo_target_band_candidate_states(" in bottom_source,
        "layout_wrapper_delegates_to_service": "_generate_bottom_reo_target_band_candidate_states(" in layout_source,
        "bottom_wrapper_no_arrangement_pool_call": "_generate_local_bottom_arrangements(" not in bottom_source,
        "layout_wrapper_no_arrangement_pool_call": "_generate_local_bottom_arrangements(" not in layout_source,
        "bottom_wrapper_no_metric_projection_body": "_build_bottom_reo_candidate_metric_projection(" not in bottom_source,
        "layout_wrapper_no_metric_projection_body": "_build_bottom_reo_candidate_metric_projection(" not in layout_source,
        "bottom_wrapper_rows_match_service": bottom_wrapper_rows == bottom_service_rows,
        "layout_wrapper_rows_match_service": layout_wrapper_rows == layout_service_rows,
        "no_inputs_page_import_in_candidate_evaluation": "inputs_page" not in candidate_source,
        "no_streamlit_import_in_candidate_evaluation": "import streamlit" not in candidate_source and "from streamlit" not in candidate_source,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "schema": "design_guide_bottom_reo_lane_service_handoff.v1",
        "status": status,
        "decision": "BOTTOM_REO_TARGET_BAND_LANE_SERVICE_OWNED_WRAPPERS" if status == "PASS" else "HANDOFF_FAILURE",
        "product_behavior_changed": False,
        "extraction_complete_estimate": "99%",
        "checks": checks,
        "line_ranges": {
            "generate_less_bottom_reo_variants": {"start": bottom_range[0], "end": bottom_range[1]},
            "generate_simpler_layout_variants": {"start": layout_range[0], "end": layout_range[1]},
        },
        "parity": {
            "bottom_wrapper_count": len(wrapper_bottom),
            "bottom_service_count": len(service_bottom),
            "layout_wrapper_count": len(wrapper_layout),
            "layout_service_count": len(service_layout),
            "bottom_wrapper_rows": bottom_wrapper_rows,
            "bottom_service_rows": bottom_service_rows,
            "layout_wrapper_rows": layout_wrapper_rows,
            "layout_service_rows": layout_service_rows,
        },
        "remaining_page_shell_inputs": [
            "candidate_key_fn",
            "REO_BAR_DIAS constant pass-through",
            "AUTO_DESIGN_MAX_STAGE_CANDIDATES constant pass-through",
        ],
        "next_safe_slice": "audit shared shear-reo cleanup generator before moving generate_less_shear_reo_variants",
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bottom-Reo Lane Service Handoff",
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
            "## Parity",
            f"- Bottom wrapper/service count: `{payload['parity']['bottom_wrapper_count']}` / `{payload['parity']['bottom_service_count']}`",
            f"- Layout wrapper/service count: `{payload['parity']['layout_wrapper_count']}` / `{payload['parity']['layout_service_count']}`",
            "",
            "## Remaining Page Shell Inputs",
        ]
    )
    lines.extend(f"- {item}" for item in payload["remaining_page_shell_inputs"])
    lines.extend(["", "## Next Safe Slice", f"- `{payload['next_safe_slice']}`"])
    return "\n".join(lines) + "\n"


def _write_artifacts(payload: dict[str, Any]) -> dict[str, str]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_lane_service_handoff_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_bottom_reo_lane_service_handoff_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return payload["artifact_paths"]


def main() -> int:
    payload = _build_payload()
    paths = _write_artifacts(payload)
    print(f"design_guide_bottom_reo_lane_service_handoff {payload['status']}")
    print(json.dumps({"decision": payload["decision"], "artifact_paths": paths}, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
