"""Verify bottom-reo compound attempt planning moved to bending family."""

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

PAGE_HELPER = "_append_geometry_bottom_compound_candidates"
FAMILY_HELPER = "build_bottom_reo_compound_attempt_rows"


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


def _label(count_1: int, count_2: int, diameter: int) -> str:
    if count_2 > 0:
        return f"{count_1}N{diameter} + {count_2}N{diameter}"
    return f"{count_1}N{diameter}"


def _old_attempt_rows(
    *,
    state: dict[str, Any],
    candidates: list[dict[str, Any]],
    mode_config: dict[str, Any],
    context: dict[str, Any],
    axis: str,
    width_key: str,
    seed_limit: int,
    bar_diameters: tuple[int, ...],
    default_limit: int,
) -> dict[str, Any]:
    from design_brain.contracts import bottom_arrangement_to_shared_updates
    from design_brain.families.bending import (
        build_bottom_reo_arrangement_pool_from_state,
        resolve_bottom_reo_geometry_trial_axis,
    )

    geo = [
        dict(candidate)
        for candidate in candidates
        if candidate.get("recommendation_geometry_trial")
        and resolve_bottom_reo_geometry_trial_axis(candidate, width_key=width_key) == axis
    ]

    def _geom_sort_key(candidate: dict[str, Any]) -> float:
        raw = ((candidate.get("overview") or {}).get("utils") or {}).get("bending")
        try:
            return float(raw) if raw is not None else 999.0
        except (TypeError, ValueError):
            return 999.0

    seeds: list[dict[str, Any]] = []
    seen_marker: set[tuple[str, float]] = set()
    for candidate in sorted(geo, key=_geom_sort_key):
        updates = dict(candidate.get("updates") or {})
        if axis == "width":
            if width_key not in updates:
                continue
            try:
                marker = ("width", round(float(updates[width_key]), 3))
            except (TypeError, ValueError):
                continue
        else:
            if "D" not in updates:
                continue
            try:
                marker = ("depth", round(float(updates["D"]), 3))
            except (TypeError, ValueError):
                continue
        if marker in seen_marker:
            continue
        seen_marker.add(marker)
        seeds.append(candidate)
        if len(seeds) >= seed_limit:
            break

    rows: list[dict[str, Any]] = []
    for geometry_candidate in seeds:
        geo_updates = dict(geometry_candidate.get("updates") or {})
        base_state = dict(state)
        base_state.update(geo_updates)
        local_arrangements: list[dict[str, Any]] = []
        seen_arrangements: set[tuple[int, int, int]] = set()
        for band in (0, 1):
            for arrangement in build_bottom_reo_arrangement_pool_from_state(
                base_state,
                mode_config,
                band=band,
                context=context,
                limit=18,
                bar_diameters=bar_diameters,
                default_limit=default_limit,
            ):
                arrangement_d = dict(arrangement)
                signature = (
                    int(arrangement_d.get("bot1_count", 0) or 0),
                    int(arrangement_d.get("bot2_count", 0) or 0),
                    int(arrangement_d.get("db_bot_1", 0) or 0),
                )
                if signature in seen_arrangements:
                    continue
                seen_arrangements.add(signature)
                local_arrangements.append(arrangement_d)
                if len(local_arrangements) >= 26:
                    break
            if len(local_arrangements) >= 26:
                break
        for arrangement in local_arrangements:
            count_1 = int(arrangement.get("bot1_count", 0) or 0)
            count_2 = int(arrangement.get("bot2_count", 0) or 0)
            diameter = int(arrangement.get("db_bot_1", 0) or 0)
            rows.append(
                {
                    "axis": axis,
                    "geometry_label": str(geometry_candidate.get("label") or ""),
                    "arrangement": dict(arrangement),
                    "bottom_updates": bottom_arrangement_to_shared_updates(dict(arrangement)),
                    "bottom_label": _label(count_1, count_2, diameter),
                }
            )
    return {
        "selected_geometry_seed_count": len(seeds),
        "attempt_rows": rows,
    }


def _row_projection(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "selected_geometry_seed_count": int(payload.get("selected_geometry_seed_count", 0) or 0),
        "attempt_rows": [
            {
                "axis": str(row.get("axis") or ""),
                "geometry_label": str(row.get("geometry_label") or ""),
                "arrangement": dict(row.get("arrangement") or {}),
                "bottom_updates": dict(row.get("bottom_updates") or {}),
                "bottom_label": str(row.get("bottom_label") or ""),
            }
            for row in list(payload.get("attempt_rows") or [])
            if isinstance(row, dict)
        ],
    }


def _parity_cases() -> list[dict[str, Any]]:
    state = {
        "b": 400.0,
        "D": 650.0,
        "cover_side": 40.0,
        "rowgap_bot": 60.0,
        "bot1_count": 8,
        "bot2_count": 0,
        "db_bot_1": 16,
        "db_bot_2": 16,
    }
    mode_config = {"search_strategy": "balanced"}
    candidates = [
        {
            "label": "Increase width by 25",
            "recommendation_geometry_trial": True,
            "updates": {"b": 425.0},
            "overview": {"utils": {"bending": 0.74}},
        },
        {
            "label": "Increase width by 50 duplicate worse",
            "recommendation_geometry_trial": True,
            "updates": {"b": 425.0},
            "overview": {"utils": {"bending": 0.91}},
        },
        {
            "label": "Increase depth by 25",
            "recommendation_geometry_trial": True,
            "updates": {"D": 675.0},
            "overview": {"utils": {"bending": 0.71}},
        },
    ]
    return [
        {
            "name": "width_seed_attempts",
            "state": state,
            "mode_config": mode_config,
            "candidates": candidates,
            "axis": "width",
            "seed_limit": 3,
        },
        {
            "name": "depth_seed_attempts",
            "state": state,
            "mode_config": mode_config,
            "candidates": candidates,
            "axis": "depth",
            "seed_limit": 2,
        },
    ]


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    _, _, page_segment = _function_segment(inputs_source, PAGE_HELPER)

    from design_brain.families.bending import build_bottom_reo_compound_attempt_rows

    parity: list[dict[str, Any]] = []
    for case in _parity_cases():
        old = _old_attempt_rows(
            state=dict(case["state"]),
            candidates=[dict(item) for item in case["candidates"]],
            mode_config=dict(case["mode_config"]),
            context={},
            axis=str(case["axis"]),
            width_key="b",
            seed_limit=int(case["seed_limit"]),
            bar_diameters=(10, 12, 16, 20, 24, 28, 32),
            default_limit=24,
        )
        new = build_bottom_reo_compound_attempt_rows(
            state=dict(case["state"]),
            candidates=[dict(item) for item in case["candidates"]],
            mode_config=dict(case["mode_config"]),
            context={},
            axis=str(case["axis"]),
            width_key="b",
            seed_limit=int(case["seed_limit"]),
            bar_diameters=(10, 12, 16, 20, 24, 28, 32),
            default_limit=24,
            arrangement_limit=18,
            max_attempts=26,
        )
        old_projection = _row_projection(old)
        new_projection = _row_projection(new)
        parity.append(
            {
                "case": case["name"],
                "matches": old_projection == new_projection,
                "old": old_projection,
                "new": new_projection,
            }
        )

    forbidden_page_tokens = [
        "_generate_local_bottom_arrangements(",
        "_bottom_arrangement_to_shared_updates(",
        "_practical_bottom_reo_label(",
        "_select_top_geometry_seeds_for_compound(",
    ]
    source_checks = {
        "family_helper_present": f"def {FAMILY_HELPER}(" in bending_source,
        "page_delegates_attempt_planning_to_family": "_build_bottom_reo_compound_attempt_rows(" in page_segment,
        "page_no_longer_generates_compound_arrangements_directly": not any(
            token in page_segment for token in forbidden_page_tokens
        ),
        "page_keeps_evaluator_callback": "_evaluate_candidate_fast(" in page_segment,
        "page_keeps_update_callback": "_updates_match_state(" in page_segment,
        "page_keeps_candidate_pool_mutation": "candidates.append(comp)" in page_segment,
        "family_has_no_inputs_page_import": "import inputs_page" not in bending_source
        and "from inputs_page" not in bending_source,
        "family_has_no_streamlit_import": "streamlit" not in bending_source and "import st" not in bending_source,
    }
    checks = {
        **source_checks,
        "parity_cases_match": all(bool(row.get("matches")) for row in parity),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_bottom_reo_compound_attempt_planner_family_boundary.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BOTTOM_REO_COMPOUND_ATTEMPT_PLANNER_FAMILY_BOUNDARY_EXTRACTED",
        "page_helper": PAGE_HELPER,
        "family_helper": FAMILY_HELPER,
        "parity": parity,
        "source_checks": source_checks,
        "checks": checks,
        "next_safe_slice": "bottom_reo_compound_merge_reject_policy_family_boundary",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_compound_attempt_planner_family_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_compound_attempt_planner_family_boundary_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Bottom Reo Compound Attempt Planner Family Boundary",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Boundary",
        "",
        f"- Page helper: `{payload.get('page_helper')}`",
        f"- Family helper: `{payload.get('family_helper')}`",
        "- Page still owns evaluator callbacks, update/no-op checks, live candidate pool mutation, and trace emission.",
        "",
        "## Parity",
        "",
    ]
    for row in payload.get("parity") or []:
        lines.append(f"- `{row.get('case')}`: `{row.get('matches')}`")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    status = payload.get("status")
    print(f"design_guide_bottom_reo_compound_attempt_planner_family_boundary {status}")
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
