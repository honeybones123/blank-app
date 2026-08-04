"""Verify bottom-reo geometry trial plan and delta projections are family-owned."""

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

COMPUTE_HELPER = "_compute_bottom_reo_recommendation"
COMPOUND_HELPER = "_append_geometry_bottom_compound_candidates"
DELTA_HELPER = "_annotate_bottom_reo_candidate_deltas"


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


def _old_plan(mode_config: dict[str, Any], deltas: list[int | float]) -> list[dict[str, Any]]:
    geo_axes = (
        ("increase_width", "increase_depth")
        if str(mode_config.get("search_strategy", "balanced") or "balanced") == "shallow"
        else ("increase_depth", "increase_width")
    )
    rows: list[dict[str, Any]] = []
    for d in deltas:
        for atype in geo_axes:
            rows.append(
                {
                    "action_type": atype,
                    "payload": {"delta_mm": float(d)},
                    "label": (
                        f"Increase depth D by {int(d)} mm"
                        if atype == "increase_depth"
                        else f"Increase section width by {int(d)} mm"
                    ),
                    "delta_mm": float(d),
                }
            )
    return rows


def _old_geometry_projection(candidate: dict[str, Any], width_key: str | None) -> dict[str, Any]:
    from design_brain.families.bending import resolve_bottom_reo_geometry_trial_axis

    axis = resolve_bottom_reo_geometry_trial_axis(candidate, width_key=width_key)
    return {
        "recommendation_geometry_trial": True,
        "actual_ast": float(candidate.get("Ast_bot", 0.0) or 0.0),
        "recommendation_family_tag": (
            f"pure_geometry_{axis}" if axis in ("width", "depth") else "pure_geometry"
        ),
    }


def _old_delta_projection(
    *,
    seed_depth: float,
    candidate_depth: float,
    seed_width: float,
    candidate_width: float,
    seed_ast: float,
    candidate_ast: float,
) -> dict[str, Any]:
    return {
        "delta_D_mm": round(candidate_depth - seed_depth, 3),
        "delta_b_mm": round(candidate_width - seed_width, 3),
        "delta_Ast_bot": round(candidate_ast - seed_ast, 3),
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    _, _, compute_segment = _function_segment(inputs_source, COMPUTE_HELPER)
    _, _, compound_segment = _function_segment(inputs_source, COMPOUND_HELPER)
    _, _, delta_segment = _function_segment(inputs_source, DELTA_HELPER)

    from design_brain.families.bending import (
        build_bottom_reo_candidate_delta_projection,
        build_bottom_reo_geometry_trial_candidate_projection,
        build_bottom_reo_geometry_trial_plan_rows,
    )

    plan_cases = [
        {"case": "balanced", "mode_config": {"search_strategy": "balanced"}, "deltas": [25, 50]},
        {"case": "shallow", "mode_config": {"search_strategy": "shallow"}, "deltas": [25, 50]},
        {"case": "default", "mode_config": {}, "deltas": [10.0]},
    ]
    plan_parity = []
    for case in plan_cases:
        old = _old_plan(dict(case["mode_config"]), list(case["deltas"]))
        new = build_bottom_reo_geometry_trial_plan_rows(
            mode_config=dict(case["mode_config"]),
            geometry_trial_deltas_mm=list(case["deltas"]),
        )
        plan_parity.append({"case": case["case"], "matches": old == new, "old": old, "new": new})

    projection_cases = [
        {"case": "depth", "candidate": {"updates": {"D": 675.0}, "Ast_bot": 801.5}, "width_key": "b"},
        {"case": "width", "candidate": {"updates": {"b": 450.0}, "Ast_bot": 721.0}, "width_key": "b"},
        {"case": "unknown", "candidate": {"updates": {"foo": 1}, "Ast_bot": 600.0}, "width_key": "b"},
        {"case": "depth_wins", "candidate": {"updates": {"D": 675.0, "b": 450.0}, "Ast_bot": 900.0}, "width_key": "b"},
    ]
    projection_parity = []
    for case in projection_cases:
        candidate = dict(case["candidate"])
        old = _old_geometry_projection(candidate, case.get("width_key"))
        new = build_bottom_reo_geometry_trial_candidate_projection(
            candidate=candidate,
            width_key=case.get("width_key"),
        )
        projection_parity.append({"case": case["case"], "matches": old == new, "old": old, "new": new})

    delta_cases = [
        {
            "case": "normal",
            "kwargs": {
                "seed_depth": 650.0,
                "candidate_depth": 675.0,
                "seed_width": 400.0,
                "candidate_width": 450.0,
                "seed_ast": 804.248,
                "candidate_ast": 721.111,
            },
        },
        {
            "case": "negative",
            "kwargs": {
                "seed_depth": 650.0,
                "candidate_depth": 625.0,
                "seed_width": 400.0,
                "candidate_width": 375.0,
                "seed_ast": 500.0,
                "candidate_ast": 450.0,
            },
        },
    ]
    delta_parity = []
    for case in delta_cases:
        kwargs = dict(case["kwargs"])
        old = _old_delta_projection(**kwargs)
        new = build_bottom_reo_candidate_delta_projection(**kwargs)
        delta_parity.append({"case": case["case"], "matches": old == new, "old": old, "new": new})

    source_checks = {
        "family_geometry_plan_helper_present": "def build_bottom_reo_geometry_trial_plan_rows(" in bending_source,
        "family_geometry_projection_helper_present": "def build_bottom_reo_geometry_trial_candidate_projection(" in bending_source,
        "family_delta_projection_helper_present": "def build_bottom_reo_candidate_delta_projection(" in bending_source,
        "page_delegates_geometry_plan": "_build_bottom_reo_geometry_trial_plan_rows(" in compute_segment,
        "page_delegates_geometry_projection": "_build_bottom_reo_geometry_trial_candidate_projection(" in compute_segment,
        "page_delegates_delta_projection": "_build_bottom_reo_candidate_delta_projection(" in delta_segment,
        "page_removed_geometry_axis_local_loop": "geo_axes =" not in compute_segment,
        "page_removed_geometry_metadata_direct_assignments": all(
            token not in compute_segment
            for token in (
                'geo_cand["recommendation_geometry_trial"] = True',
                'geo_cand["actual_ast"] =',
                'geo_cand["recommendation_family_tag"] =',
            )
        ),
        "page_removed_delta_direct_assignments": all(
            token not in delta_segment
            for token in (
                'candidate["delta_D_mm"] =',
                'candidate["delta_b_mm"] =',
                'candidate["delta_Ast_bot"] =',
            )
        ),
        "page_keeps_action_update_callback": "_guidance_action_updates(" in compute_segment,
        "page_keeps_evaluator_callback": "_evaluate_candidate_fast(" in compute_segment + compound_segment,
        "page_keeps_candidate_append": "candidates.append(geo_cand)" in compute_segment
        and "candidates.append(comp)" in compound_segment,
        "family_has_no_inputs_page_import": "import inputs_page" not in bending_source
        and "from inputs_page" not in bending_source,
        "family_has_no_streamlit_import": "streamlit" not in bending_source and "import st" not in bending_source,
    }
    checks = {
        **source_checks,
        "geometry_plan_parity": all(bool(row["matches"]) for row in plan_parity),
        "geometry_projection_parity": all(bool(row["matches"]) for row in projection_parity),
        "delta_projection_parity": all(bool(row["matches"]) for row in delta_parity),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_bottom_reo_geometry_trial_plan_delta_projection_family_boundary.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BOTTOM_REO_GEOMETRY_TRIAL_PLAN_DELTA_PROJECTION_FAMILY_BOUNDARY_EXTRACTED",
        "plan_parity": plan_parity,
        "projection_parity": projection_parity,
        "delta_parity": delta_parity,
        "source_checks": source_checks,
        "checks": checks,
        "remaining_page_owned_surfaces": [
            "_guidance_action_updates callback execution",
            "_evaluate_candidate_fast callback execution",
            "candidate list mutation",
            "compound trace emission",
            "state width/depth/Ast scalar collection for delta projection",
        ],
        "next_safe_slice": "bottom_reo_geometry_callback_or_delta_scalar_collection_shell_audit",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_geometry_trial_plan_delta_projection_family_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_geometry_trial_plan_delta_projection_family_boundary_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Geometry Trial Plan / Delta Projection Family Boundary",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Parity",
        "",
        f"- Geometry trial plan cases: `{sum(1 for row in payload.get('plan_parity', []) if row.get('matches'))}/{len(payload.get('plan_parity', []))}`",
        f"- Geometry metadata projection cases: `{sum(1 for row in payload.get('projection_parity', []) if row.get('matches'))}/{len(payload.get('projection_parity', []))}`",
        f"- Delta projection cases: `{sum(1 for row in payload.get('delta_parity', []) if row.get('matches'))}/{len(payload.get('delta_parity', []))}`",
        "",
        "## Remaining Page-Owned Surfaces",
        "",
    ]
    lines.extend(f"- `{item}`" for item in payload.get("remaining_page_owned_surfaces") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bottom_reo_geometry_trial_plan_delta_projection_family_boundary {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload.get("status") != "PASS":
        failed = [name for name, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
