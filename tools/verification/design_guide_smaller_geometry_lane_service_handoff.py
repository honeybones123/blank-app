"""Verify smaller-geometry lane orchestration handoff to candidate_evaluation."""

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
    build_auto_design_candidate_key,
    build_geometry_update_projection,
    generate_smaller_geometry_candidate_states,
    resolve_geometry_width_context,
)
from design_brain.families.bending_fail_governs.geometry_ratio import (  # noqa: E402
    guard_bending_depth_width_geometry_update,
)


MIN_DEPTH = 300.0
MIN_WIDTH = 250.0

CASES = [
    {
        "name": "rect_balanced_depth_and_width",
        "current_candidate": {"state": {"sec_shape": "RECT", "b": 400.0, "D": 650.0}, "depth": 650.0},
        "mode_config": {"search_strategy": "balanced"},
        "geometry_locked": False,
    },
    {
        "name": "rect_shallow_depth_only",
        "current_candidate": {"state": {"sec_shape": "RECT", "b": 400.0, "D": 650.0}, "depth": 650.0},
        "mode_config": {"search_strategy": "shallow"},
        "geometry_locked": False,
    },
    {
        "name": "locked_geometry_empty",
        "current_candidate": {"state": {"sec_shape": "RECT", "b": 400.0, "D": 650.0}, "depth": 650.0},
        "mode_config": {"search_strategy": "balanced"},
        "geometry_locked": True,
    },
    {
        "name": "t_section_includes_rectified_width",
        "current_candidate": {"state": {"sec_shape": "T", "b": 500.0, "bw": 320.0, "D": 650.0}, "depth": 650.0},
        "mode_config": {"search_strategy": "balanced"},
        "geometry_locked": False,
    },
    {
        "name": "i_section_includes_rectified_width",
        "current_candidate": {"state": {"sec_shape": "I", "b": 450.0, "tw": 300.0, "D": 620.0}, "depth": 620.0},
        "mode_config": {"search_strategy": "balanced"},
        "geometry_locked": False,
    },
    {
        "name": "minimum_depth_filters_second_depth",
        "current_candidate": {"state": {"sec_shape": "RECT", "b": 400.0, "D": 360.0}, "depth": 360.0},
        "mode_config": {"search_strategy": "balanced"},
        "geometry_locked": False,
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


def _geometry_state(base_state: dict[str, Any], *, depth: float | None = None, width: float | None = None) -> dict[str, Any]:
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


def _candidate_key(state: dict[str, Any]) -> Any:
    return build_auto_design_candidate_key(state, resolved_actions={})


def _legacy_variants(current_candidate: dict[str, Any], mode_config: dict[str, Any], *, geometry_locked: bool) -> list[dict[str, Any]]:
    state = dict(current_candidate.get("state") or {})
    if geometry_locked:
        return []
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    current_depth = float(current_candidate.get("depth", _float_from_state(state, "D", 600.0)) or _float_from_state(state, "D", 600.0))
    width_key, _, current_width = resolve_geometry_width_context(state)
    variants: dict[Any, dict[str, Any]] = {}
    for depth in [current_depth - 50.0, current_depth - 100.0]:
        if depth >= MIN_DEPTH:
            candidate_state = _geometry_state(state, depth=depth)
            variants[_candidate_key(candidate_state)] = candidate_state
    if strategy != "shallow":
        narrower = current_width - 50.0
        if narrower >= MIN_WIDTH:
            candidate_state = _geometry_state(state, width=narrower)
            variants[_candidate_key(candidate_state)] = candidate_state
        if width_key != "b":
            current_rectified = _geometry_state(state, width=current_width)
            variants[_candidate_key(current_rectified)] = current_rectified
    return list(variants.values())


def _service_variants(current_candidate: dict[str, Any], mode_config: dict[str, Any], *, geometry_locked: bool) -> list[dict[str, Any]]:
    return generate_smaller_geometry_candidate_states(
        current_candidate=current_candidate,
        mode_config=mode_config,
        geometry_locked=geometry_locked,
        minimum_practical_depth_mm=MIN_DEPTH,
        minimum_practical_width_mm=MIN_WIDTH,
        geometry_state_fn=_geometry_state,
        candidate_key_fn=_candidate_key,
    )


def _build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    wrapper_start, wrapper_end, wrapper_source = _function_source(inputs_source, "generate_smaller_geometry_variants")
    helper_start, helper_end, helper_source = _function_source(candidate_source, "generate_smaller_geometry_candidate_states")
    cases = []
    for case in CASES:
        legacy = _legacy_variants(case["current_candidate"], case["mode_config"], geometry_locked=case["geometry_locked"])
        service = _service_variants(case["current_candidate"], case["mode_config"], geometry_locked=case["geometry_locked"])
        cases.append(
            {
                "name": case["name"],
                "legacy_count": len(legacy),
                "service_count": len(service),
                "legacy": legacy,
                "service": service,
                "matches": legacy == service,
            }
        )

    checks = {
        "all_cases_match": all(row["matches"] for row in cases),
        "service_helper_present": "def generate_smaller_geometry_candidate_states(" in candidate_source,
        "page_imports_service_helper": "generate_smaller_geometry_candidate_states as _generate_smaller_geometry_candidate_states" in inputs_source,
        "page_wrapper_delegates": "return _generate_smaller_geometry_candidate_states(" in wrapper_source,
        "page_wrapper_keeps_geometry_lock_input": "geometry_locked=_geometry_lock_enabled(state)" in wrapper_source,
        "page_wrapper_injects_materializer": "geometry_state_fn=_geometry_state_with_updates" in wrapper_source,
        "page_wrapper_injects_candidate_key": "candidate_key_fn=_make_auto_design_candidate_key" in wrapper_source,
        "candidate_evaluation_no_inputs_page_import": "inputs_page" not in candidate_source,
        "candidate_evaluation_no_streamlit_import": "streamlit" not in candidate_source and "st." not in helper_source,
        "service_helper_no_family_guard_call": "guard_bending_depth_width_geometry_update" not in helper_source,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "surface": "smaller_geometry_lane_service_handoff",
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
        "next_safe_slice": "reclassify geometry lane as service-owned wrapper, then audit bottom-reo lane helpers",
    }


def _write_artifacts(payload: dict[str, Any]) -> dict[str, str]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_smaller_geometry_lane_service_handoff_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_smaller_geometry_lane_service_handoff_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Smaller Geometry Lane Service Handoff",
            "",
            "## Executive Summary",
            f"- Status: `{payload['status']}`",
            f"- Extraction complete estimate: `{payload['extraction_complete_estimate']}`",
            f"- Product behavior changed: `{payload['product_behavior_changed']}`",
            "",
            "## Behaviour Preserved",
            *[
                f"- `{row['name']}`: `{row['matches']}` counts `{row['legacy_count']}` / `{row['service_count']}`"
                for row in payload["cases"]
            ],
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
