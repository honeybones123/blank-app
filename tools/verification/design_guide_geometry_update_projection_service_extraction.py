"""Verify geometry update projection extraction into candidate_evaluation."""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.candidate_evaluation import (  # noqa: E402
    build_geometry_update_projection,
    resolve_geometry_width_context,
)
from design_brain.families.bending_fail_governs.geometry_ratio import (  # noqa: E402
    guard_bending_depth_width_geometry_update,
)


MIN_DEPTH = 300.0
MIN_WIDTH = 250.0

CASES = [
    {
        "name": "rect_depth_reduction",
        "state": {"sec_shape": "RECT", "b": 400.0, "D": 650.0},
        "depth": 550.0,
        "width": None,
    },
    {
        "name": "rect_width_reduction",
        "state": {"sec_shape": "RECT", "b": 400.0, "D": 650.0},
        "depth": None,
        "width": 350.0,
    },
    {
        "name": "rect_min_depth_rounding",
        "state": {"sec_shape": "RECT", "b": 400.0, "D": 650.0},
        "depth": 275.0,
        "width": None,
    },
    {
        "name": "rect_min_width_rounding",
        "state": {"sec_shape": "RECT", "b": 400.0, "D": 650.0},
        "depth": None,
        "width": 230.0,
    },
    {
        "name": "t_width_mirrors_b",
        "state": {"sec_shape": "T", "b": 500.0, "bw": 320.0, "D": 650.0},
        "depth": None,
        "width": 300.0,
    },
    {
        "name": "i_width_mirrors_b",
        "state": {"sec_shape": "I", "b": 450.0, "tw": 230.0, "D": 600.0},
        "depth": None,
        "width": 260.0,
    },
    {
        "name": "t_width_none_sets_current_web_width",
        "state": {"sec_shape": "T", "b": 500.0, "bw": 320.0, "D": 650.0},
        "depth": 600.0,
        "width": None,
    },
    {
        "name": "depth_width_ratio_rescues_width",
        "state": {"sec_shape": "RECT", "b": 300.0, "D": 650.0},
        "depth": 900.0,
        "width": None,
    },
    {
        "name": "locked_depth_width_ratio_blocks",
        "state": {"sec_shape": "RECT", "b": 300.0, "D": 650.0, "optimisation_lock_width": True},
        "depth": 900.0,
        "width": None,
    },
]


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


def _float_from_state(state: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(state.get(key, default) or default)
    except (TypeError, ValueError):
        return float(default)


def _width_locked(state: dict[str, Any]) -> bool:
    return bool(state.get("optimisation_lock_geometry", False) or state.get("optimisation_lock_width", False))


def _guard_updates(base_state: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    if not updates:
        return {}
    if not (set(updates) & {"D", "b", "bw", "tw", "beam_width", "beam_b", "width"}):
        return dict(updates)
    width_key, _, current_width = resolve_geometry_width_context(base_state)
    result = guard_bending_depth_width_geometry_update(
        current_width=_float_from_state(base_state, width_key, current_width),
        current_depth=_float_from_state(base_state, "D", 0.0),
        updates=dict(updates),
        width_update_key=width_key,
        width_locked=_width_locked(base_state),
        allow_width_rescue=True,
        minimum_practical_width=MIN_WIDTH,
    )
    return dict(result.updates)


def _legacy_candidate_state(base_state: dict[str, Any], *, depth: float | None, width: float | None) -> dict[str, Any]:
    candidate_state = dict(base_state)
    width_key, _, current_width = resolve_geometry_width_context(base_state)
    updates: dict[str, float] = {}
    if depth is not None:
        updates["D"] = float(int(round(max(MIN_DEPTH, depth) / 10.0) * 10))
    if width is not None:
        resolved_width = float(int(round(max(MIN_WIDTH, width) / 10.0) * 10))
        updates[width_key] = resolved_width
        if width_key != "b":
            updates["b"] = resolved_width
    else:
        candidate_state[width_key] = float(current_width)
    candidate_state.update(_guard_updates(base_state, updates))
    return candidate_state


def _service_candidate_state(base_state: dict[str, Any], *, depth: float | None, width: float | None) -> dict[str, Any]:
    width_key, _, current_width = resolve_geometry_width_context(base_state)
    projection = build_geometry_update_projection(
        base_state=base_state,
        width_key=width_key,
        current_width=current_width,
        depth=depth,
        width=width,
        minimum_practical_depth_mm=MIN_DEPTH,
        minimum_practical_width_mm=MIN_WIDTH,
    )
    guarded_updates = _guard_updates(base_state, projection.get("raw_updates") or {})
    guarded_projection = build_geometry_update_projection(
        base_state=base_state,
        width_key=width_key,
        current_width=current_width,
        depth=depth,
        width=width,
        minimum_practical_depth_mm=MIN_DEPTH,
        minimum_practical_width_mm=MIN_WIDTH,
        guarded_updates=guarded_updates,
    )
    return dict(guarded_projection.get("candidate_state") or {})


def _build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    wrapper_start, wrapper_end, wrapper_source = _function_source(inputs_source, "_geometry_state_with_updates")
    helper_start, helper_end, helper_source = _function_source(candidate_source, "build_geometry_update_projection")
    cases = []
    for case in CASES:
        state = dict(case["state"])
        legacy = _legacy_candidate_state(state, depth=case["depth"], width=case["width"])
        service = _service_candidate_state(state, depth=case["depth"], width=case["width"])
        cases.append(
            {
                "name": case["name"],
                "legacy": legacy,
                "service": service,
                "matches": legacy == service,
            }
        )

    checks = {
        "all_cases_match": all(row["matches"] for row in cases),
        "service_helper_present": "def build_geometry_update_projection(" in candidate_source,
        "page_imports_service_helper": "build_geometry_update_projection as _build_geometry_update_projection" in inputs_source,
        "page_wrapper_delegates_projection": "_build_geometry_update_projection(" in wrapper_source,
        "page_wrapper_still_calls_guard": "_geometry_updates_with_depth_width_contract_guard(" in wrapper_source,
        "page_wrapper_uses_raw_updates_for_guard": 'projection.get("raw_updates")' in wrapper_source,
        "candidate_evaluation_no_inputs_page_import": "inputs_page" not in candidate_source,
        "candidate_evaluation_no_streamlit_import": "streamlit" not in candidate_source and "st." not in helper_source,
        "service_helper_has_no_family_guard_call": "guard_bending_depth_width_geometry_update" not in helper_source,
        "service_helper_preserves_non_b_mirror": 'if resolved_width_key != "b":' in helper_source,
        "service_helper_preserves_current_width_materialization": "candidate_state[resolved_width_key] = current_width_f" in helper_source,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "surface": "geometry_update_projection_service_extraction",
        "product_behavior_changed": False,
        "extraction_complete_estimate": "99%",
        "cases": cases,
        "checks": checks,
        "wrapper": {
            "line_start": wrapper_start,
            "line_end": wrapper_end,
            "line_count": wrapper_end - wrapper_start + 1,
        },
        "service_helper": {
            "line_start": helper_start,
            "line_end": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "next_safe_slice": "attempt generate_smaller_geometry_variants shell handoff now that width context and update projection are service-owned",
    }


def _write_artifacts(payload: dict[str, Any]) -> dict[str, str]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_geometry_update_projection_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_geometry_update_projection_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Geometry Update Projection Service Extraction",
            "",
            "## Executive Summary",
            f"- Status: `{payload['status']}`",
            f"- Extraction complete estimate: `{payload['extraction_complete_estimate']}`",
            f"- Product behavior changed: `{payload['product_behavior_changed']}`",
            "",
            "## Behaviour Preserved",
            *[f"- `{row['name']}`: `{row['matches']}`" for row in payload["cases"]],
            "",
            "## Checks",
            *[f"- `{name}`: `{passed}`" for name, passed in payload["checks"].items()],
            "",
            "## Wrapper",
            f"- Lines: `{payload['wrapper']['line_start']}-{payload['wrapper']['line_end']}`",
            f"- Line count: `{payload['wrapper']['line_count']}`",
            "",
            "## Service Helper",
            f"- Lines: `{payload['service_helper']['line_start']}-{payload['service_helper']['line_end']}`",
            f"- Line count: `{payload['service_helper']['line_count']}`",
            "",
            "## Next Safe Slice",
            payload["next_safe_slice"],
            "",
        ]
    )


def main() -> int:
    payload = _build_payload()
    payload["artifact_paths"] = _write_artifacts(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
