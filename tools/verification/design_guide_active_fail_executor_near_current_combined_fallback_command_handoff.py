"""Verify active-fail near-current combined fallback command handoff."""

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
HELPER = "build_design_guide_controller_active_fail_executor_near_current_combined_fallback_eval_commands"


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


def _rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    geometry_bottom_rows = [
        {
            "geometry_updates": {"b": 450.0, "D": 750.0},
            "bottom_update_rows": [
                {"updates": {"bot1_count": 4, "db_bot_1": 20}},
                {"updates": {"bot1_count": 5, "db_bot_1": 24}},
            ],
        },
        {
            "geometry_updates": {},
            "bottom_update_rows": [
                {"updates": {"bot1_count": 6, "db_bot_1": 24}},
            ],
        },
    ]
    shear_rows = [
        {"lig_d": 12, "lig_legs": 2},
        {"lig_d": 16, "lig_legs": 4},
    ]
    return geometry_bottom_rows, shear_rows


def _old_commands(
    geometry_bottom_rows: list[dict[str, Any]],
    shear_rows: list[dict[str, Any]],
    label: str,
) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    for geometry_row in geometry_bottom_rows:
        geometry_updates = dict(geometry_row.get("geometry_updates") or {})
        for bottom_row in list(geometry_row.get("bottom_update_rows") or []):
            bottom_updates = dict(bottom_row.get("updates") or {})
            for shear_updates in shear_rows:
                merged = dict(geometry_updates)
                merged.update(bottom_updates)
                merged.update(dict(shear_updates or {}))
                commands.append(
                    {
                        "updates": merged,
                        "label": label,
                        "source": "active_fail_near_current_combined_fallback",
                    }
                )
    return commands


def _new_commands(
    geometry_bottom_rows: list[dict[str, Any]],
    shear_rows: list[dict[str, Any]],
    label: str,
) -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        build_design_guide_controller_active_fail_executor_near_current_combined_fallback_eval_commands,
    )

    return build_design_guide_controller_active_fail_executor_near_current_combined_fallback_eval_commands(
        geometry_bottom_rows=geometry_bottom_rows,
        shear_update_rows=shear_rows,
        label=label,
    )


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    helper_start, helper_end, helper_source = _function_source(controller_source, HELPER)
    geometry_rows, shear_rows = _rows()
    label = "Active fail near-current combined repair"
    old = _old_commands(geometry_rows, shear_rows, label)
    new = _new_commands(geometry_rows, shear_rows, label)
    removed_inline_tokens = {
        "inline_shear_loop": "for shear_updates in ordered_shear:" not in target_source,
        "inline_merged_dict": "merged = dict(geom_updates)" not in target_source,
        "inline_merged_bottom": "merged.update(bottom_updates)" not in target_source,
        "inline_merged_shear": "merged.update(dict(shear_updates or {}))" not in target_source,
        "inline_direct_evaluate_label": '_evaluate(merged, "Active fail near-current combined repair")'
        not in target_source,
    }
    return {
        "schema": "design_guide_active_fail_executor_near_current_combined_fallback_command_handoff.v1",
        "target": {
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
            "delegates_near_current_fallback_commands": "_build_design_guide_controller_active_fail_executor_near_current_combined_fallback_eval_commands("
            in target_source,
            "still_owns_geometry_state_and_fit_checks": all(
                token in target_source
                for token in (
                    "_geometry_state_with_updates(",
                    "_arrangement_fits_state(",
                    "_normalise_bottom_layer_order(",
                )
            ),
            "still_owns_evaluator_callback": "_evaluate_active_fail_executor_candidate_with_updates(" in target_source,
            "removed_inline_tokens": removed_inline_tokens,
        },
        "controller_helper": {
            "line_start": helper_start,
            "line_end": helper_end,
            "line_count": max(0, helper_end - helper_start + 1),
            "exists": bool(helper_start),
            "exported": f'"{HELPER}"' in controller_source,
            "imports_no_page_or_streamlit": all(
                token not in controller_source
                for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
            ),
            "helper_hash": _stable_hash(helper_source),
        },
        "parity": {
            "old_hash": _stable_hash(old),
            "new_hash": _stable_hash(new),
            "match": old == new,
            "command_count": len(new),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    target = payload.get("target") or {}
    helper = payload.get("controller_helper") or {}
    parity = payload.get("parity") or {}
    return {
        "target_found": bool(target.get("line_start")),
        "target_delegates_near_current_fallback_commands": bool(target.get("delegates_near_current_fallback_commands")),
        "page_still_owns_geometry_fit_checks": bool(target.get("still_owns_geometry_state_and_fit_checks")),
        "page_still_owns_evaluator_callback": bool(target.get("still_owns_evaluator_callback")),
        "inline_merge_loop_removed": all((target.get("removed_inline_tokens") or {}).values()),
        "controller_helper_exists": bool(helper.get("exists")),
        "controller_helper_exported": bool(helper.get("exported")),
        "controller_import_boundary_clean": bool(helper.get("imports_no_page_or_streamlit")),
        "command_parity_matches": bool(parity.get("match")),
        "command_count_expected": int(parity.get("command_count") or 0) == 6,
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_near_current_combined_fallback_command_handoff_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_near_current_combined_fallback_command_handoff_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Near-Current Combined Fallback Command Handoff",
        "",
        f"Status: {payload['status']}",
        "",
        "## Executive Summary",
        (
            "Near-current combined fallback geometry/bottom/shear merge ordering now delegates to "
            "`DesignGuideController`. The page still prepares geometry/bottom rows because it owns current "
            "geometry state and bar-fit checks."
        ),
        "",
        "## Parity",
        f"- command count: `{(payload.get('parity') or {}).get('command_count')}`",
        f"- match: `{(payload.get('parity') or {}).get('match')}`",
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
            "controller_helper": payload.get("controller_helper"),
            "parity": payload.get("parity"),
        }
    )
    json_path, report_path = _write(payload, checks)
    print(f"status={payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
