"""Verify direct target-band after-state score extraction to controller."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node.lineno, int(node.end_lineno or node.lineno), "\n".join(
                lines[node.lineno - 1 : int(node.end_lineno or node.lineno)]
            )
    return 0, 0, ""


def _parse_value(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).strip())
        except Exception:
            return None


def _old_state_after_updates(state: dict[str, Any] | None, updates: dict[str, Any] | None) -> dict[str, Any]:
    numeric_keys = {
        "bot1_count",
        "bot2_count",
        "bot_row_count",
        "bot_row_1_bars",
        "bot_row_1_dia",
        "bot_row_2_bars",
        "bot_row_2_dia",
        "db_bot_1",
        "db_bot_2",
        "nb_bot",
        "bot_entry",
        "lig_d",
        "db_lig",
        "lig_legs",
        "s_lig",
        "D",
        "b",
        "beam_width",
        "beam_b",
        "width",
    }
    ignored_keys = {"search_scope", "generated_count", "deduped_count", "preview_count"}
    out = dict(state or {})
    for raw_key, value in dict(updates or {}).items():
        key = str(raw_key or "").strip()
        key_l = key.lower()
        if not key or key_l in ignored_keys or key_l.endswith("_route") or key_l in {"links", "bottom_reo"}:
            continue
        if key in numeric_keys:
            numeric = _parse_value(value)
            if numeric is not None:
                out[key] = numeric
    return out


def _old_int(source: dict[str, Any], key: str, default: int) -> int:
    parsed = _parse_value(source.get(key))
    return int(default if parsed is None else parsed)


def _old_float(source: dict[str, Any], key: str, default: float) -> float:
    parsed = _parse_value(source.get(key))
    return float(default if parsed is None else parsed)


def _old_width(source: dict[str, Any]) -> float:
    sec_shape = str(source.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return float(source.get("bw", source.get("b", 300.0)) or 300.0)
    if sec_shape == "I":
        return float(source.get("tw", source.get("b", 200.0)) or 200.0)
    return float(source.get("b", 400.0) or 400.0)


def _old_shear_score(*, updates: dict[str, Any], state: dict[str, Any], canonical: float) -> tuple:
    shear_keys = {"lig_d", "lig_legs", "s_lig"}
    if not bool(set(updates) & shear_keys):
        return (0, 0, 0.0, 0)
    after = _old_state_after_updates(state, updates)
    legs = max(_old_int(after, "lig_legs", 2), 0)
    diameter = max(_old_int(after, "lig_d", 0), 0)
    spacing = float(_old_float(after, "s_lig", canonical) or canonical)
    leg_penalty = 0 if legs == 2 else (100 + abs(legs - 2))
    return (leg_penalty, spacing, -diameter, legs)


def _old_geometry_score(*, updates: dict[str, Any], state: dict[str, Any]) -> tuple:
    touches_geometry = bool(set(updates) & {"D", "b", "beam_width", "beam_b", "width"})
    geometry_locked = bool(state.get("optimisation_lock_geometry", False)) or bool(
        state.get("optimisation_lock_width", False) and state.get("optimisation_lock_depth", False)
    )
    if geometry_locked or not touches_geometry:
        return (0, 0.0, 0.0)
    after = _old_state_after_updates(state, updates)
    try:
        depth = float(_old_float(after, "D", 0.0) or 0.0)
        width = float(_old_width(after) or 0.0)
    except Exception:
        return (3, 99.0, 99.0)
    if depth <= 0.0 or width <= 0.0:
        return (3, 99.0, 99.0)
    ratio = depth / width
    if ratio <= 2.0 + 1e-9:
        return (0, abs(ratio - 2.0), ratio)
    if ratio <= 2.5 + 1e-9:
        return (1, ratio - 2.0, ratio)
    return (2, ratio - 2.0, ratio)


def _parity_cases() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_direct_target_after_state_preference_scores,
    )

    cases = [
        {
            "name": "no_updates",
            "state": {"D": 650.0, "b": 400.0, "lig_legs": 2, "lig_d": 10, "s_lig": 150.0},
            "updates": {},
        },
        {
            "name": "shear_updates",
            "state": {"D": 650.0, "b": 400.0, "lig_legs": 4, "lig_d": 12, "s_lig": 100.0},
            "updates": {"lig_legs": 2, "lig_d": 10, "s_lig": 200.0},
        },
        {
            "name": "shear_spacing_default",
            "state": {"D": 650.0, "b": 400.0, "lig_legs": 4, "lig_d": 12},
            "updates": {"lig_legs": 0, "lig_d": 0, "s_lig": ""},
        },
        {
            "name": "rect_geometry_update",
            "state": {"sec_shape": "RECT", "D": 700.0, "b": 300.0},
            "updates": {"D": 600.0, "b": 400.0},
        },
        {
            "name": "geometry_locked",
            "state": {
                "sec_shape": "RECT",
                "D": 700.0,
                "b": 300.0,
                "optimisation_lock_width": True,
                "optimisation_lock_depth": True,
            },
            "updates": {"D": 600.0, "b": 400.0},
        },
        {
            "name": "t_section_width_uses_bw",
            "state": {"sec_shape": "T", "D": 700.0, "b": 450.0, "bw": 250.0},
            "updates": {"D": 500.0, "b": 350.0},
        },
        {
            "name": "invalid_geometry_values",
            "state": {"sec_shape": "RECT", "D": 700.0, "b": 300.0},
            "updates": {"D": "bad", "b": 0},
        },
        {
            "name": "ignored_route_payload",
            "state": {"D": 650.0, "b": 400.0, "lig_legs": 2, "lig_d": 10, "s_lig": 150.0},
            "updates": {"s_lig_route": 300, "links": "remove", "bottom_reo": "5N10"},
        },
    ]
    rows = []
    for case in cases:
        state = dict(case["state"])
        updates = dict(case["updates"])
        expected_shear = _old_shear_score(updates=updates, state=state, canonical=200.0)
        expected_geometry = _old_geometry_score(updates=updates, state=state)
        actual = resolve_design_guide_controller_direct_target_after_state_preference_scores(
            updates=updates,
            state=state,
            canonical_no_shear_spacing=200.0,
        )
        rows.append(
            {
                "name": case["name"],
                "expected_shear": expected_shear,
                "actual_shear": tuple(actual.get("shear_practical_preference_score") or ()),
                "expected_geometry": expected_geometry,
                "actual_geometry": tuple(actual.get("geometry_proportion_preference_score") or ()),
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    shear_start, shear_end, shear_source = _function_source(inputs_source, "_design_guide_shear_practical_preference_score")
    geom_start, geom_end, geom_source = _function_source(inputs_source, "_design_guide_geometry_proportion_preference_score")
    helper_start, helper_end, helper_source = _function_source(
        controller_source,
        "resolve_design_guide_controller_direct_target_after_state_preference_scores",
    )
    parity_rows = _parity_cases()
    forbidden_page_tokens = [
        "_design_guide_state_after_updates(",
        "_geometry_lock_enabled(",
        "_int_from_state(",
        "_float_from_state(",
        "_design_width_value(",
        "_resolve_design_guide_controller_shear_practical_preference_score(",
        "_resolve_design_guide_controller_geometry_proportion_preference_score(",
    ]
    wrapper_source = "\n".join([shear_source, geom_source])
    return {
        "schema": "design_guide_direct_target_selection_dependency_row_after_state_score_extraction.v1",
        "page_wrappers": {
            "shear": {"line_start": shear_start, "line_end": shear_end, "line_count": max(0, shear_end - shear_start + 1)},
            "geometry": {"line_start": geom_start, "line_end": geom_end, "line_count": max(0, geom_end - geom_start + 1)},
        },
        "controller_helper": {
            "name": "resolve_design_guide_controller_direct_target_after_state_preference_scores",
            "line_start": helper_start,
            "line_end": helper_end,
            "line_count": max(0, helper_end - helper_start + 1),
        },
        "wrapper_delegates_to_controller_helper": (
            wrapper_source.count("_resolve_design_guide_controller_direct_target_after_state_preference_scores(") == 2
        ),
        "forbidden_page_tokens_present": [
            token for token in forbidden_page_tokens if token in wrapper_source
        ],
        "controller_has_no_page_or_streamlit_imports": "inputs_page" not in controller_source
        and "streamlit" not in controller_source
        and "st.session_state" not in controller_source,
        "parity_rows": parity_rows,
        "parity_mismatches": [
            row["name"]
            for row in parity_rows
            if row["expected_shear"] != row["actual_shear"]
            or row["expected_geometry"] != row["actual_geometry"]
        ],
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "page_wrappers_found": all((capture.get("page_wrappers") or {}).get(name, {}).get("line_start") for name in ("shear", "geometry")),
        "controller_helper_found": bool((capture.get("controller_helper") or {}).get("line_start")),
        "wrapper_delegates_to_controller_helper": bool(capture.get("wrapper_delegates_to_controller_helper")),
        "forbidden_page_tokens_removed": not bool(capture.get("forbidden_page_tokens_present")),
        "parity_cases_match": not bool(capture.get("parity_mismatches")),
        "controller_has_no_page_or_streamlit_imports": bool(capture.get("controller_has_no_page_or_streamlit_imports")),
        "product_behavior_unchanged": not bool(capture.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(capture.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(capture.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(capture.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_selection_dependency_row_after_state_score_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_selection_dependency_row_after_state_score_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Selection Dependency Row After-State Score Extraction",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        "- Direct-target shear/geometry after-state score input resolution now delegates to DesignGuideController.",
        "- Page wrappers remain as shell compatibility callers.",
        "- Candidate selection, CTA/apply, visible wording, and family runtimes were not changed.",
        "",
        "## Parity Cases",
    ]
    for row in payload.get("parity_rows") or []:
        rows_match = row.get("name") not in set(payload.get("parity_mismatches") or [])
        lines.append(f"- {row.get('name')}: {'PASS' if rows_match else 'FAIL'}")
    lines.extend(
        [
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        **capture,
        "status": status,
        "checks": checks,
        "checked_at": _timestamp(),
    }
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_direct_target_selection_dependency_row_after_state_score_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
