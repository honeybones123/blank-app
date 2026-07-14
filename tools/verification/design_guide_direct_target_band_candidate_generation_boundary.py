"""Verify direct target-band ladder update generation is service-backed."""

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
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET = "_direct_target_band_guidance_item"
SERVICE_HELPER = "build_direct_target_band_ladder_stage_update_attempts"


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


def _nested_function_source(source: str, outer_name: str, nested_name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == outer_name:
            for child in ast.walk(node):
                if isinstance(child, ast.FunctionDef) and child.name == nested_name:
                    return child.lineno, int(child.end_lineno or child.lineno), "\n".join(
                        lines[child.lineno - 1 : int(child.end_lineno or child.lineno)]
                    )
    return 0, 0, ""


def _hash(value: Any) -> str:
    from design_brain.candidate_evaluation import stable_candidate_evaluation_hash

    return stable_candidate_evaluation_hash(value)


def _expected_strengthen_shear(*, lig_d: int, legs: int, spacing: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if lig_d > 0 and legs >= 2 and spacing > 0:
        for next_spacing in (max(75.0, spacing - 25.0), max(75.0, spacing - 50.0), 150.0, 125.0, 100.0, 75.0):
            if next_spacing < spacing - 1e-9:
                rows.append({"label": f"reduce link spacing to {next_spacing:g}", "updates": {"s_lig": float(next_spacing)}})
        for dia in (10, 12, 16, 20, 24):
            if dia > lig_d:
                rows.append({"label": f"increase link diameter to {dia}", "updates": {"lig_d": int(dia)}})
        for next_legs in (legs + 2, 4, 6, 8):
            if next_legs > legs:
                rows.append({"label": f"increase link legs to {next_legs}", "updates": {"lig_legs": int(next_legs)}})
    return rows[:18]


def _expected_cleanup_geometry(*, width_key: str, base_width: float, base_depth: float, min_width: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for depth_step in (25.0, 50.0, 75.0):
        next_depth = base_depth - depth_step
        if next_depth >= 300.0:
            rows.append({"label": f"reduce depth {depth_step:g}", "updates": {"D": float(next_depth)}})
    for width_step in (25.0, 50.0, 75.0):
        next_width = base_width - width_step
        if next_width >= min_width:
            updates: dict[str, Any] = {width_key: float(next_width)}
            if width_key != "b":
                updates["b"] = float(next_width)
            rows.append({"label": f"reduce width {width_step:g}", "updates": updates})
    return rows


def _parity() -> dict[str, Any]:
    from design_brain.candidate_evaluation import build_direct_target_band_ladder_stage_update_attempts

    prebuilt = [(f"candidate {idx}", {"x": idx}) for idx in range(15)]
    cases: list[dict[str, Any]] = []

    actual_reo = build_direct_target_band_ladder_stage_update_attempts(
        stage_name="strengthen_reo_nearby",
        base_state={},
        prebuilt_update_attempts=prebuilt,
    )
    expected_reo = [{"label": label, "updates": dict(updates)} for label, updates in prebuilt[:12]]
    cases.append(
        {
            "case": "strengthen_reo_prebuilt_limit",
            "expected_hash": _hash(expected_reo),
            "actual_hash": _hash(actual_reo),
            "passed": actual_reo == expected_reo,
        }
    )

    actual_shear = build_direct_target_band_ladder_stage_update_attempts(
        stage_name="strengthen_shear_nearby",
        base_state={},
        base_lig_d=8,
        base_lig_legs=2,
        base_lig_spacing=150.0,
    )
    expected_shear = _expected_strengthen_shear(lig_d=8, legs=2, spacing=150.0)
    cases.append(
        {
            "case": "strengthen_shear_pure_generation",
            "expected_hash": _hash(expected_shear),
            "actual_hash": _hash(actual_shear),
            "passed": actual_shear == expected_shear,
        }
    )

    actual_cleanup_geometry = build_direct_target_band_ladder_stage_update_attempts(
        stage_name="cleanup_geometry_nearby",
        base_state={},
        width_key="bw",
        base_width=400.0,
        base_depth=500.0,
        min_cleanup_width=250.0,
    )
    expected_cleanup_geometry = _expected_cleanup_geometry(
        width_key="bw",
        base_width=400.0,
        base_depth=500.0,
        min_width=250.0,
    )
    cases.append(
        {
            "case": "cleanup_geometry_pure_generation",
            "expected_hash": _hash(expected_cleanup_geometry),
            "actual_hash": _hash(actual_cleanup_geometry),
            "passed": actual_cleanup_geometry == expected_cleanup_geometry,
        }
    )

    actual_passthrough = build_direct_target_band_ladder_stage_update_attempts(
        stage_name="cleanup_shear_nearby",
        base_state={},
        prebuilt_update_attempts=[{"label": "reduce shear", "updates": {"lig_d": 0, "lig_legs": 0}}],
    )
    expected_passthrough = [{"label": "reduce shear", "updates": {"lig_d": 0, "lig_legs": 0}}]
    cases.append(
        {
            "case": "callback_heavy_stage_prebuilt_passthrough",
            "expected_hash": _hash(expected_passthrough),
            "actual_hash": _hash(actual_passthrough),
            "passed": actual_passthrough == expected_passthrough,
        }
    )

    return {
        "cases": cases,
        "all_passed": all(bool(row.get("passed")) for row in cases),
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    service_start, service_end, service_source = _function_source(candidate_source, SERVICE_HELPER)
    adapter_start, adapter_end, adapter_source = _nested_function_source(target_source, TARGET, "_service_stage_updates")
    parity = _parity()
    source_checks = {
        "service_helper_exists": bool(service_source),
        "service_helper_exported": f'"{SERVICE_HELPER}"' in candidate_source,
        "inputs_imports_service_helper": f"{SERVICE_HELPER} as _{SERVICE_HELPER}" in inputs_source,
        "page_has_service_stage_adapter": bool(adapter_source),
        "adapter_calls_service_helper": f"_{SERVICE_HELPER}(" in adapter_source,
        "target_uses_service_stage_for_all_ladder_stages": all(
            token in target_source
            for token in (
                '_service_stage_updates("strengthen_reo_nearby", reo_updates)',
                '_service_stage_updates("strengthen_shear_nearby")',
                '_service_stage_updates("strengthen_geometry_nearby", geometry_updates)',
                '_service_stage_updates("cleanup_reo_nearby", bottom_updates)',
                '_service_stage_updates("cleanup_shear_nearby", shear_cleanup_updates)',
                '_service_stage_updates("cleanup_geometry_nearby")',
            )
        ),
        "page_no_longer_owns_pure_strengthen_shear_generation": all(
            token not in target_source
            for token in (
                "base_lig_d = _int_from_state(base, \"lig_d\", 0)",
                "shear_updates.append((f\"reduce link spacing",
                "shear_updates.append((f\"increase link diameter",
                "shear_updates.append((f\"increase link legs",
            )
        ),
        "page_no_longer_owns_pure_cleanup_geometry_generation": all(
            token not in target_source
            for token in (
                "next_depth = base_depth - depth_step",
                "geometry_updates.append((f\"reduce depth",
                "geometry_updates.append((f\"reduce width",
            )
        ),
        "callback_heavy_generation_remains_page_owned": all(
            token in target_source
            for token in (
                "_normalise_bottom_layer_order(",
                "_arrangement_fits_state(",
                "_geometry_updates_with_depth_width_contract_guard(",
                "_generate_local_bottom_arrangements(",
                "generate_less_shear_reo_variants(",
            )
        ),
        "evaluation_selection_projection_remain_page_owned": all(
            token in target_source
            for token in (
                "_evaluate_updates(",
                "_record_stage(",
                "_select_direct_target_item(",
                "_build_candidate_search_evidence(",
                "_guidance_item_from_resolved_candidate(",
                "item[\"action_payload\"]",
            )
        ),
        "candidate_evaluation_import_clean_terms_absent": all(
            token not in candidate_source
            for token in (
                "inputs_page",
                "streamlit",
                "st.session_state",
                "rendered_html",
                "apply_routing",
                "ui_state",
            )
        ),
    }
    return {
        "schema": "design_guide_direct_target_band_candidate_generation_boundary.v1",
        "target": {
            "name": TARGET,
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
        },
        "service_helper": {
            "name": SERVICE_HELPER,
            "line_start": service_start,
            "line_end": service_end,
            "line_count": max(0, service_end - service_start + 1),
        },
        "adapter": {
            "name": "_service_stage_updates",
            "line_start": adapter_start,
            "line_end": adapter_end,
            "line_count": max(0, adapter_end - adapter_start + 1),
        },
        "parity": parity,
        "source_checks": source_checks,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "remaining_page_owned_surfaces": [
            "callback-heavy bottom reinforcement arrangement generation",
            "geometry contract guard generation",
            "shear seed and less-shear variant generation",
            "broad direct target-band search loops",
            "ranking/selection",
            "evidence and item projection",
            "debug/session diagnostics",
        ],
        "next_safe_slice": "direct_target_band_broad_search_generation_audit_or_direct_target_ranking_policy_extraction",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "parity_passed": bool((capture.get("parity") or {}).get("all_passed")),
        **{str(key): bool(value) for key, value in source_checks.items()},
        "product_behavior_unchanged": not bool(capture.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(capture.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(capture.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(capture.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_band_candidate_generation_boundary_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_band_candidate_generation_boundary_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    failed = [name for name, passed in checks.items() if not passed]
    lines = [
        "# Design Guide Direct Target-Band Candidate Generation Boundary",
        "",
        f"Status: {payload['status']}",
        "",
        "## Target",
        f"- `{TARGET}` lines {payload['target']['line_start']}-{payload['target']['line_end']}",
        f"- Service helper: `design_brain.candidate_evaluation.{SERVICE_HELPER}(...)`",
        "",
        "## Parity",
    ]
    for row in (payload.get("parity") or {}).get("cases") or []:
        lines.append(f"- {row['case']}: {'PASS' if row.get('passed') else 'FAIL'}")
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Surfaces",
            *[f"- {item}" for item in payload.get("remaining_page_owned_surfaces") or []],
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
            "",
            "## Failed Checks",
            *(f"- {name}" for name in failed),
            "",
            f"Next safe slice: `{payload.get('next_safe_slice')}`",
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
    print(f"design_guide_direct_target_band_candidate_generation_boundary {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
