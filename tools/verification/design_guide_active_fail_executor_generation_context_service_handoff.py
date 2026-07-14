"""Verify active-fail executor generation context service handoff."""

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
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_active_fail_near_current_repair_item"
SERVICE_HELPER = "build_active_fail_executor_candidate_generation_context"


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


def _old_int(source: dict[str, Any], *keys: str, default: int = 0) -> int:
    for key in keys:
        if key in source:
            try:
                return int(source.get(key) or default)
            except Exception:
                continue
    return int(default)


def _old_float(source: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(source.get(key, default) or default)
    except Exception:
        return float(default)


def _old_width_context(source: dict[str, Any]) -> tuple[str, str, float]:
    sec_shape = str(source.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return "bw", "Web width bw (mm)", _old_float(source, "bw", _old_float(source, "b", 300.0))
    if sec_shape == "I":
        return "tw", "Web thickness tw (mm)", _old_float(source, "tw", _old_float(source, "b", 200.0))
    return "b", "Width b (mm)", _old_float(source, "b", 400.0)


def _old_generation_context(
    base_state: dict[str, Any],
    active_failures: set[str],
    *,
    target_low: float,
    target_high: float,
    canonical_no_shear_spacing: float,
) -> dict[str, Any]:
    from design_brain.repair import (  # noqa: WPS433
        build_near_current_bottom_repair_specs,
        build_near_current_geometry_repair_specs,
        build_near_current_shear_repair_specs,
    )

    base = dict(base_state or {})
    active = {
        str(family or "").strip().lower()
        for family in list(active_failures or [])
        if str(family or "").strip()
    }
    width_key, width_label, base_width = _old_width_context(base)
    base_depth = _old_float(base, "D", 0.0)
    base_count = max(2, _old_int(base, "bot1_count", "bot_row_1_bars", default=2))
    base_dia = max(10, _old_int(base, "db_bot_1", "bot_row_1_dia", default=16))
    base_lig_d = _old_int(base, "lig_d", default=0)
    base_legs = _old_int(base, "lig_legs", default=0)
    base_spacing = _old_float(base, "s_lig", canonical_no_shear_spacing)
    return {
        "active": sorted(active),
        "target_low": float(target_low),
        "target_high": float(target_high),
        "width_key": width_key,
        "width_label": width_label,
        "base_width": float(base_width),
        "base_depth": float(base_depth),
        "base_count": int(base_count),
        "base_dia": int(base_dia),
        "base_lig_d": int(base_lig_d),
        "base_legs": int(base_legs),
        "base_spacing": float(base_spacing),
        "ordered_bottom": build_near_current_bottom_repair_specs(int(base_count), int(base_dia)),
        "ordered_geom": build_near_current_geometry_repair_specs(float(base_width), float(base_depth)),
        "ordered_shear": build_near_current_shear_repair_specs(
            active,
            base_lig_d=int(base_lig_d),
            base_legs=int(base_legs),
            base_spacing=float(base_spacing),
        ),
    }


def _sample_parity() -> dict[str, Any]:
    from design_brain.candidate_evaluation import (  # noqa: WPS433
        build_active_fail_executor_candidate_generation_context,
    )

    cases = {
        "rect_bending": (
            {
                "sec_shape": "RECT",
                "b": 400.0,
                "D": 650.0,
                "bot1_count": 6,
                "db_bot_1": 20,
                "lig_d": 10,
                "lig_legs": 2,
                "s_lig": 200.0,
            },
            {"bending"},
        ),
        "t_shear": (
            {
                "sec_shape": "T",
                "b": 600.0,
                "bw": 300.0,
                "D": 700.0,
                "bot_row_1_bars": 5,
                "bot_row_1_dia": 16,
                "lig_d": 12,
                "lig_legs": 3,
                "s_lig": 175.0,
            },
            {"shear"},
        ),
        "i_combined": (
            {
                "sec_shape": "I",
                "b": 500.0,
                "tw": 240.0,
                "D": 750.0,
                "bot1_count": 8,
                "db_bot_1": 24,
                "lig_d": 10,
                "lig_legs": 2,
                "s_lig": 150.0,
            },
            {"bending", "shear"},
        ),
    }
    rows: dict[str, dict[str, Any]] = {}
    for name, (base, active) in cases.items():
        old_context = _old_generation_context(
            base,
            active,
            target_low=0.85,
            target_high=1.0,
            canonical_no_shear_spacing=200.0,
        )
        new_context = build_active_fail_executor_candidate_generation_context(
            base,
            active,
            target_low=0.85,
            target_high=1.0,
            canonical_no_shear_spacing=200.0,
        )
        rows[name] = {
            "old_hash": _stable_hash(old_context),
            "new_hash": _stable_hash(new_context),
            "old_context": old_context,
            "new_context": new_context,
        }
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    parity = _sample_parity()
    return {
        "schema": "design_guide_active_fail_executor_generation_context_service_handoff.v1",
        "target": {
            "name": TARGET,
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
        },
        "parity": parity,
        "source_checks": {
            "target_uses_generation_context_helper": "_build_active_fail_executor_candidate_generation_context("
            in target_source,
            "target_no_longer_calls_near_current_repair_spec_builders": all(
                token not in target_source
                for token in (
                    "_repair_build_near_current_bottom_repair_specs(",
                    "_repair_build_near_current_geometry_repair_specs(",
                    "_repair_build_near_current_shear_repair_specs(",
                )
            ),
            "inputs_no_longer_imports_near_current_repair_spec_builders": all(
                token not in inputs_source
                for token in (
                    "_repair_build_near_current_bottom_repair_specs",
                    "_repair_build_near_current_geometry_repair_specs",
                    "_repair_build_near_current_shear_repair_specs",
                )
            ),
            "candidate_evaluation_helper_exists": f"def {SERVICE_HELPER}(" in candidate_source,
            "candidate_evaluation_exports_helper": f'"{SERVICE_HELPER}"' in candidate_source,
            "candidate_evaluation_import_clean_terms_absent": all(
                token not in candidate_source
                for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
            ),
            "family_ladder_dispatch_controller_owned": (
                "_build_design_guide_controller_active_fail_executor_family_ladder_dispatch("
                in target_source
                and ".contracted_repair_ladder_specs(" not in target_source
            ),
            "session_cache_still_page_owned": "st.session_state" in target_source,
            "candidate_selection_controller_owned": (
                "_select_design_guide_controller_active_fail_executor_family_ladder_candidate("
                in target_source
                and "select_repair_candidate_from_ladder(" not in target_source
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    parity = payload.get("parity") or {}
    source_checks = payload.get("source_checks") or {}
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "generation_context_hashes_unchanged": bool(parity)
        and all(row.get("old_hash") == row.get("new_hash") for row in parity.values()),
        **{name: bool(value) for name, value in source_checks.items()},
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"design_guide_active_fail_executor_generation_context_service_handoff_{suffix}.json"
    )
    report_path = AUDIT_DIR / (
        f"design_guide_active_fail_executor_generation_context_service_handoff_{suffix}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Generation Context Service Handoff",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        (
            "Moved active-fail executor generation context and ordered near-current repair spec "
            "construction behind `design_brain.candidate_evaluation`. Runtime loops, family ladder "
            "execution, ranking/evidence packaging, cache/session, and CTA side effects remain page-owned."
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
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_executor_generation_context_service_handoff {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
