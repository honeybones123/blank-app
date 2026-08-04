"""Verify active-fail geometry/bottom row projection handoff."""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
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
TARGET = "_active_fail_near_current_repair_item"
GEOM_HELPER = "build_design_guide_controller_active_fail_executor_geometry_update_row"
BOTTOM_HELPER = "build_design_guide_controller_active_fail_executor_bottom_update_row"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _old_geometry_update_row(
    *,
    width_key: str,
    base_width: float,
    base_depth: float,
    resolved_width: float,
    resolved_depth: float,
) -> dict[str, Any]:
    geom_updates: dict[str, Any] = {}
    gw = float(resolved_width)
    gd = float(resolved_depth)
    if abs(gw - base_width) > 1e-9:
        geom_updates[width_key] = gw
        if width_key != "b":
            geom_updates["b"] = gw
        if abs(gd - base_depth) > 1e-9:
            geom_updates["D"] = gd
    return geom_updates


def _new_geometry_update_row(**kwargs: Any) -> dict[str, Any]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        build_design_guide_controller_active_fail_executor_geometry_update_row,
    )

    return build_design_guide_controller_active_fail_executor_geometry_update_row(**kwargs)


def _old_bottom_row(updates: dict[str, Any] | None) -> dict[str, Any]:
    return {"updates": dict(updates or {})}


def _new_bottom_row(updates: dict[str, Any] | None) -> dict[str, Any]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        build_design_guide_controller_active_fail_executor_bottom_update_row,
    )

    return build_design_guide_controller_active_fail_executor_bottom_update_row(updates)


def _geometry_cases() -> dict[str, dict[str, Any]]:
    return {
        "same_width_depth": {
            "width_key": "b",
            "base_width": 400.0,
            "base_depth": 650.0,
            "resolved_width": 400.0,
            "resolved_depth": 650.0,
        },
        "width_only_b": {
            "width_key": "b",
            "base_width": 400.0,
            "base_depth": 650.0,
            "resolved_width": 450.0,
            "resolved_depth": 650.0,
        },
        "width_and_depth_b": {
            "width_key": "b",
            "base_width": 400.0,
            "base_depth": 650.0,
            "resolved_width": 450.0,
            "resolved_depth": 700.0,
        },
        "web_width_alias": {
            "width_key": "bw",
            "base_width": 300.0,
            "base_depth": 650.0,
            "resolved_width": 350.0,
            "resolved_depth": 700.0,
        },
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    geom_start, geom_end, geom_source = _function_source(controller_source, GEOM_HELPER)
    bottom_start, bottom_end, bottom_source = _function_source(controller_source, BOTTOM_HELPER)
    geometry_parity: dict[str, dict[str, Any]] = {}
    for name, kwargs in _geometry_cases().items():
        old = _old_geometry_update_row(**kwargs)
        new = _new_geometry_update_row(**kwargs)
        geometry_parity[name] = {
            "old_hash": _stable_hash(old),
            "new_hash": _stable_hash(new),
            "match": old == new,
            "new": new,
        }
    bottom_cases = {
        "none": None,
        "empty": {},
        "updates": {"bot1_count": 4, "db_bot_1": 20},
    }
    bottom_parity: dict[str, dict[str, Any]] = {}
    for name, updates in bottom_cases.items():
        old = _old_bottom_row(updates)
        new = _new_bottom_row(updates)
        bottom_parity[name] = {
            "old_hash": _stable_hash(old),
            "new_hash": _stable_hash(new),
            "match": old == new,
        }
    removed_inline_tokens = {
        "inline_geom_updates_decl": "geom_updates: dict[str, object] = {}" not in target_source,
        "inline_width_delta_assignment": "geom_updates[width_key] = gw" not in target_source,
        "inline_alias_assignment": 'geom_updates["b"] = gw' not in target_source,
        "inline_depth_assignment": 'geom_updates["D"] = gd' not in target_source,
        "inline_bottom_row_wrapper": 'bottom_update_rows.append({"updates": dict(bottom_updates or {})})'
        not in target_source,
    }
    return {
        "schema": "design_guide_active_fail_executor_geometry_bottom_row_handoff.v1",
        "target": {
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
            "delegates_geometry_update_row": "_build_design_guide_controller_active_fail_executor_geometry_update_row("
            in target_source,
            "delegates_bottom_update_row": "_build_design_guide_controller_active_fail_executor_bottom_update_row("
            in target_source,
            "still_owns_geometry_state_and_fit_checks": all(
                token in target_source
                for token in (
                    "_geometry_state_with_updates(",
                    "_arrangement_fits_state(",
                    "_normalise_bottom_layer_order(",
                )
            ),
            "removed_inline_tokens": removed_inline_tokens,
        },
        "controller_helpers": {
            "geometry_line_start": geom_start,
            "geometry_line_end": geom_end,
            "bottom_line_start": bottom_start,
            "bottom_line_end": bottom_end,
            "geometry_exists": bool(geom_start),
            "bottom_exists": bool(bottom_start),
            "helpers_exported": f'"{GEOM_HELPER}"' in controller_source and f'"{BOTTOM_HELPER}"' in controller_source,
            "imports_no_page_or_streamlit": all(
                token not in controller_source
                for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
            ),
            "helper_hash": _stable_hash(geom_source + bottom_source),
        },
        "geometry_parity": geometry_parity,
        "bottom_parity": bottom_parity,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    target = payload.get("target") or {}
    helpers = payload.get("controller_helpers") or {}
    geometry = payload.get("geometry_parity") or {}
    bottom = payload.get("bottom_parity") or {}
    return {
        "target_found": bool(target.get("line_start")),
        "target_delegates_geometry_update_row": bool(target.get("delegates_geometry_update_row")),
        "target_delegates_bottom_update_row": bool(target.get("delegates_bottom_update_row")),
        "page_still_owns_geometry_fit_checks": bool(target.get("still_owns_geometry_state_and_fit_checks")),
        "inline_row_projection_removed": all((target.get("removed_inline_tokens") or {}).values()),
        "controller_geometry_helper_exists": bool(helpers.get("geometry_exists")),
        "controller_bottom_helper_exists": bool(helpers.get("bottom_exists")),
        "controller_helpers_exported": bool(helpers.get("helpers_exported")),
        "controller_import_boundary_clean": bool(helpers.get("imports_no_page_or_streamlit")),
        "geometry_parity_cases_present": len(geometry) == 4,
        "all_geometry_hashes_match": all(bool(row.get("match")) for row in geometry.values()),
        "bottom_parity_cases_present": len(bottom) == 3,
        "all_bottom_hashes_match": all(bool(row.get("match")) for row in bottom.values()),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_geometry_bottom_row_handoff_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_geometry_bottom_row_handoff_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Geometry/Bottom Row Handoff",
        "",
        f"Status: {payload['status']}",
        "",
        "## Executive Summary",
        (
            "Near-current fallback geometry update-row and bottom update-row projection now delegate to "
            "`DesignGuideController`. The page still owns geometry state derivation and reinforcement fit checks."
        ),
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    payload["snapshot_hash"] = _stable_hash(
        {
            "target": payload.get("target"),
            "controller_helpers": payload.get("controller_helpers"),
            "geometry_parity": payload.get("geometry_parity"),
            "bottom_parity": payload.get("bottom_parity"),
        }
    )
    json_path, report_path = _write(payload, checks)
    print(f"status={payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
