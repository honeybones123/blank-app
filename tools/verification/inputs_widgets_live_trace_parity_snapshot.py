"""Browser/live trace proof for Inputs widget metadata trace.

This starts a temporary Streamlit server with PERF_TRACE_INPUTS=1, opens the
Inputs page, and reads the emitted pre-widget JSONL trace. It does not change
widget rendering, widget keys, callbacks, session behavior, or visible wording.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _query,
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PERF_DIR = ROOT / "artifacts" / "performance"
TRACE_BLOCK = "inputs_widget_metadata_trace"
EXPECTED_WIDGET_KEYS = (
    "inputs_detailed_mode_toggle",
    "inputs_use_calculated_actions",
    "inputs_loads_edit_toggle",
    "inputs_load_Mstar_pos_proxy",
    "inputs_Tu_star",
    "inputs_load_Vstar_proxy",
    "inputs_load_Nstar_proxy",
    "inputs_sec_shape",
    "inputs_D",
    "inputs_L",
    "inputs_fsy",
    "inputs_fc",
    "inputs_lig_d",
    "inputs_lig_legs",
    "inputs_s_lig",
    "inputs_cover_bot",
    "inputs_cover_top",
)
DETAILED_WIDGET_KEYS = (
    "inputs_member_faces_exposed",
    "inputs_shrinkage_env",
    "inputs_env_option",
    "inputs_defl_support_type",
    "inputs_defl_limit_ratio",
    "inputs_d_g",
    "inputs_k_v_method",
    "inputs_t_shrink",
    "inputs_t_creep",
    "inputs_age_at_loading",
    "inputs_n_ducts",
    "inputs_duct_dia",
    "inputs_k_d_option",
    "inputs_exposure_class",
    "inputs_crack_member_type",
    "inputs_crack_k1",
    "inputs_crack_k2",
)
FLANGE_WIDGET_KEYS = (
    "inputs_top_flange_reo_enabled",
    "inputs_top_flange_mirror_lr",
    "inputs_top_flange_left_count",
    "inputs_top_flange_left_dia",
    "inputs_top_flange_left_rows",
    "inputs_top_flange_left_row_spacing",
    "inputs_top_flange_left_clear_spacing_mode",
    "inputs_bot_flange_reo_enabled",
    "inputs_bot_flange_mirror_lr",
    "inputs_bot_flange_left_count",
    "inputs_bot_flange_left_dia",
    "inputs_bot_flange_left_rows",
    "inputs_bot_flange_left_row_spacing",
    "inputs_bot_flange_left_clear_spacing_mode",
    "inputs_top_flange_transverse_enabled",
    "inputs_top_flange_transverse_dia",
    "inputs_top_flange_transverse_spacing",
    "inputs_top_flange_transverse_legs",
    "inputs_bot_flange_transverse_enabled",
    "inputs_bot_flange_transverse_dia",
    "inputs_bot_flange_transverse_spacing",
    "inputs_bot_flange_transverse_legs",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _trace_files() -> set[Path]:
    if not PERF_DIR.exists():
        return set()
    return set(PERF_DIR.glob("inputs_pre_widget_trace_*.jsonl"))


def _load_trace_rows(paths: set[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(paths, key=lambda item: item.stat().st_mtime):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            row["_trace_path"] = str(path)
            rows.append(row)
    return rows


def _wait_for_trace(
    paths_before: set[Path],
    *,
    timeout_s: float,
    started_at: float,
    require_detailed_groups: bool = False,
    require_flange_groups: bool = False,
) -> dict[str, Any] | None:
    deadline = time.time() + timeout_s
    best_row: dict[str, Any] | None = None
    required_groups = {
        "design_action_numbers",
        "geometry_basic",
        "materials_basic",
        "shear_reinforcement_basic",
        "bottom_longitudinal_reinforcement",
        "top_longitudinal_reinforcement",
    }
    if require_detailed_groups:
        required_groups.update(
            {
                "serviceability_environment_basic",
                "support_deflection_basic",
                "shear_section_parameters_basic",
                "time_dependent_basic",
                "ducts_prestress_voids_basic",
                "crack_control_inputs_basic",
            }
        )
    if require_flange_groups:
        required_groups.update(
            {
                "flange_reinforcement_basic",
                "flange_transverse_basic",
            }
        )
    while time.time() < deadline:
        paths_now = _trace_files()
        candidate_paths = {
            path for path in (paths_now - paths_before)
            if path.exists() and path.stat().st_mtime >= started_at - 1.0
        }
        rows = [
            row for row in _load_trace_rows(candidate_paths)
            if row.get("block") == TRACE_BLOCK
        ]
        if rows:
            rows_sorted = sorted(
                rows,
                key=lambda row: (
                    int(row.get("inputs_widget_metadata_count") or 0),
                    int(row.get("call_count") or 0),
                    str(row.get("timestamp") or ""),
                ),
            )
            best_row = rows_sorted[-1]
            group_ids = {str(value) for value in list(best_row.get("inputs_widget_group_ids") or [])}
            if required_groups.issubset(group_ids):
                return best_row
        time.sleep(0.5)
    return best_row


def _classify(
    trace: dict[str, Any] | None,
    *,
    require_detailed_groups: bool = False,
    require_flange_groups: bool = False,
    section_shape: str = "default",
) -> dict[str, Any]:
    if not isinstance(trace, dict):
        return {
            "status": "FAIL",
            "decision": "LIVE_WIDGET_METADATA_TRACE_MISSING",
            "failures": ["trace_missing"],
        }
    widget_keys = tuple(str(value) for value in list(trace.get("inputs_widget_keys") or []))
    group_ids = tuple(str(value) for value in list(trace.get("inputs_widget_group_ids") or []))
    design_action_numbers_keys = tuple(
        str(value) for value in list(trace.get("design_action_numbers_widget_keys") or [])
    )
    geometry_keys = tuple(str(value) for value in list(trace.get("geometry_widget_keys") or []))
    materials_keys = tuple(str(value) for value in list(trace.get("materials_widget_keys") or []))
    shear_keys = tuple(str(value) for value in list(trace.get("shear_widget_keys") or []))
    bottom_longitudinal_keys = tuple(
        str(value) for value in list(trace.get("bot_longitudinal_widget_keys") or [])
    )
    top_longitudinal_keys = tuple(
        str(value) for value in list(trace.get("top_longitudinal_widget_keys") or [])
    )
    serviceability_environment_keys = tuple(
        str(value) for value in list(trace.get("serviceability_environment_basic_widget_keys") or [])
    )
    support_deflection_keys = tuple(
        str(value) for value in list(trace.get("support_deflection_basic_widget_keys") or [])
    )
    shear_section_parameter_keys = tuple(
        str(value) for value in list(trace.get("shear_section_parameters_basic_widget_keys") or [])
    )
    time_dependent_keys = tuple(
        str(value) for value in list(trace.get("time_dependent_basic_widget_keys") or [])
    )
    ducts_prestress_voids_keys = tuple(
        str(value) for value in list(trace.get("ducts_prestress_voids_basic_widget_keys") or [])
    )
    crack_control_keys = tuple(
        str(value) for value in list(trace.get("crack_control_inputs_basic_widget_keys") or [])
    )
    flange_reinforcement_keys = tuple(
        str(value) for value in list(trace.get("flange_reinforcement_basic_widget_keys") or [])
    )
    flange_transverse_keys = tuple(
        str(value) for value in list(trace.get("flange_transverse_basic_widget_keys") or [])
    )
    detailed_groups_recorded = all(
        group in group_ids
        for group in (
            "serviceability_environment_basic",
            "support_deflection_basic",
            "shear_section_parameters_basic",
            "time_dependent_basic",
            "ducts_prestress_voids_basic",
            "crack_control_inputs_basic",
        )
    )
    effective_section_shape = str(section_shape or "default")
    if effective_section_shape == "default":
        if "inputs_tw" in geometry_keys:
            effective_section_shape = "I"
        elif {"inputs_bf", "inputs_tf", "inputs_bw"}.issubset(set(geometry_keys)):
            effective_section_shape = "T"
        else:
            effective_section_shape = "RECT"
    expected_geometry_keys = ("inputs_sec_shape", "inputs_D", "inputs_L")
    if effective_section_shape == "T":
        expected_geometry_keys = expected_geometry_keys + ("inputs_bf", "inputs_tf", "inputs_bw")
    elif effective_section_shape == "I":
        expected_geometry_keys = expected_geometry_keys + ("inputs_bf", "inputs_tf", "inputs_tw")
    else:
        expected_geometry_keys = expected_geometry_keys + ("inputs_b",)
    expected_widget_keys = EXPECTED_WIDGET_KEYS + tuple(
        key for key in expected_geometry_keys if key not in EXPECTED_WIDGET_KEYS
    )
    checks = {
        "trace_built": bool(trace.get("inputs_widget_metadata_trace_built")),
        "trace_only": bool(trace.get("inputs_widget_metadata_trace_only")),
        "renderer_not_cut_over": trace.get("live_widget_renderer_cutover") is False,
        "metadata_hash_present": bool(str(trace.get("inputs_widget_metadata_hash") or "").strip()),
        "metadata_count_at_least_top_level_actions_geometry_materials_shear_and_longitudinal": int(trace.get("inputs_widget_metadata_count") or 0) >= 18,
        "expected_widget_keys_present": all(key in widget_keys for key in expected_widget_keys),
        "design_action_numbers_group_recorded": "design_action_numbers" in group_ids,
        "design_action_numbers_widget_metadata_hash_present": bool(str(trace.get("design_action_numbers_widget_metadata_hash") or "").strip()),
        "design_action_numbers_widget_metadata_count_at_least_four": int(trace.get("design_action_numbers_widget_metadata_count") or 0) >= 4,
        "expected_design_action_number_keys_present": all(
            key in design_action_numbers_keys
            for key in (
                "inputs_load_Mstar_pos_proxy",
                "inputs_Tu_star",
                "inputs_load_Vstar_proxy",
                "inputs_load_Nstar_proxy",
            )
        ),
        "geometry_group_recorded": "geometry_basic" in group_ids,
        "geometry_widget_metadata_hash_present": bool(str(trace.get("geometry_widget_metadata_hash") or "").strip()),
        "geometry_widget_metadata_count_at_least_four": int(trace.get("geometry_widget_metadata_count") or 0) >= 4,
        "expected_geometry_keys_present": all(
            key in geometry_keys for key in expected_geometry_keys
        ),
        "materials_group_recorded": "materials_basic" in group_ids,
        "materials_widget_metadata_hash_present": bool(str(trace.get("materials_widget_metadata_hash") or "").strip()),
        "materials_widget_metadata_count_two": int(trace.get("materials_widget_metadata_count") or 0) == 2,
        "expected_materials_keys_present": all(
            key in materials_keys for key in ("inputs_fsy", "inputs_fc")
        ),
        "shear_group_recorded": "shear_reinforcement_basic" in group_ids,
        "shear_widget_metadata_hash_present": bool(str(trace.get("shear_widget_metadata_hash") or "").strip()),
        "shear_widget_metadata_count_three": int(trace.get("shear_widget_metadata_count") or 0) == 3,
        "expected_shear_keys_present": all(
            key in shear_keys for key in ("inputs_lig_d", "inputs_lig_legs", "inputs_s_lig")
        ),
        "bottom_longitudinal_group_recorded": "bottom_longitudinal_reinforcement" in group_ids,
        "bottom_longitudinal_widget_metadata_hash_present": bool(str(trace.get("bot_longitudinal_widget_metadata_hash") or "").strip()),
        "bottom_longitudinal_widget_metadata_count_at_least_one": int(trace.get("bot_longitudinal_widget_metadata_count") or 0) >= 1,
        "expected_bottom_longitudinal_keys_present": "inputs_cover_bot" in bottom_longitudinal_keys,
        "top_longitudinal_group_recorded": "top_longitudinal_reinforcement" in group_ids,
        "top_longitudinal_widget_metadata_hash_present": bool(str(trace.get("top_longitudinal_widget_metadata_hash") or "").strip()),
        "top_longitudinal_widget_metadata_count_at_least_one": int(trace.get("top_longitudinal_widget_metadata_count") or 0) >= 1,
        "expected_top_longitudinal_keys_present": "inputs_cover_top" in top_longitudinal_keys,
        "detailed_groups_optional": True,
        "detailed_groups_recorded_if_rendered": not detailed_groups_recorded or all(
            key in widget_keys for key in DETAILED_WIDGET_KEYS
        ),
        "serviceability_environment_widget_metadata_hash_present_if_rendered": "serviceability_environment_basic" not in group_ids or bool(str(trace.get("serviceability_environment_basic_widget_metadata_hash") or "").strip()),
        "serviceability_environment_widget_metadata_count_three_if_rendered": "serviceability_environment_basic" not in group_ids or int(trace.get("serviceability_environment_basic_widget_metadata_count") or 0) == 3,
        "expected_serviceability_environment_keys_present_if_rendered": "serviceability_environment_basic" not in group_ids or all(
            key in serviceability_environment_keys
            for key in ("inputs_member_faces_exposed", "inputs_shrinkage_env", "inputs_env_option")
        ),
        "support_deflection_widget_metadata_hash_present_if_rendered": "support_deflection_basic" not in group_ids or bool(str(trace.get("support_deflection_basic_widget_metadata_hash") or "").strip()),
        "support_deflection_widget_metadata_count_two_if_rendered": "support_deflection_basic" not in group_ids or int(trace.get("support_deflection_basic_widget_metadata_count") or 0) == 2,
        "expected_support_deflection_keys_present_if_rendered": "support_deflection_basic" not in group_ids or all(
            key in support_deflection_keys
            for key in ("inputs_defl_support_type", "inputs_defl_limit_ratio")
        ),
        "shear_section_parameters_widget_metadata_hash_present_if_rendered": "shear_section_parameters_basic" not in group_ids or bool(str(trace.get("shear_section_parameters_basic_widget_metadata_hash") or "").strip()),
        "shear_section_parameters_widget_metadata_count_two_if_rendered": "shear_section_parameters_basic" not in group_ids or int(trace.get("shear_section_parameters_basic_widget_metadata_count") or 0) == 2,
        "expected_shear_section_parameter_keys_present_if_rendered": "shear_section_parameters_basic" not in group_ids or all(
            key in shear_section_parameter_keys
            for key in ("inputs_d_g", "inputs_k_v_method")
        ),
        "time_dependent_widget_metadata_hash_present_if_rendered": "time_dependent_basic" not in group_ids or bool(str(trace.get("time_dependent_basic_widget_metadata_hash") or "").strip()),
        "time_dependent_widget_metadata_count_three_if_rendered": "time_dependent_basic" not in group_ids or int(trace.get("time_dependent_basic_widget_metadata_count") or 0) == 3,
        "expected_time_dependent_keys_present_if_rendered": "time_dependent_basic" not in group_ids or all(
            key in time_dependent_keys
            for key in ("inputs_t_shrink", "inputs_t_creep", "inputs_age_at_loading")
        ),
        "ducts_prestress_voids_widget_metadata_hash_present_if_rendered": "ducts_prestress_voids_basic" not in group_ids or bool(str(trace.get("ducts_prestress_voids_basic_widget_metadata_hash") or "").strip()),
        "ducts_prestress_voids_widget_metadata_count_three_if_rendered": "ducts_prestress_voids_basic" not in group_ids or int(trace.get("ducts_prestress_voids_basic_widget_metadata_count") or 0) == 3,
        "expected_ducts_prestress_voids_keys_present_if_rendered": "ducts_prestress_voids_basic" not in group_ids or all(
            key in ducts_prestress_voids_keys
            for key in ("inputs_n_ducts", "inputs_duct_dia", "inputs_k_d_option")
        ),
        "crack_control_widget_metadata_hash_present_if_rendered": "crack_control_inputs_basic" not in group_ids or bool(str(trace.get("crack_control_inputs_basic_widget_metadata_hash") or "").strip()),
        "crack_control_widget_metadata_count_four_if_rendered": "crack_control_inputs_basic" not in group_ids or int(trace.get("crack_control_inputs_basic_widget_metadata_count") or 0) == 4,
        "expected_crack_control_keys_present_if_rendered": "crack_control_inputs_basic" not in group_ids or all(
            key in crack_control_keys
            for key in (
                "inputs_exposure_class",
                "inputs_crack_member_type",
                "inputs_crack_k1",
                "inputs_crack_k2",
            )
        ),
        "detailed_groups_recorded_when_required": not require_detailed_groups or detailed_groups_recorded,
        "flange_reinforcement_widget_metadata_hash_present_if_rendered": "flange_reinforcement_basic" not in group_ids or bool(str(trace.get("flange_reinforcement_basic_widget_metadata_hash") or "").strip()),
        "flange_reinforcement_widget_metadata_count_at_least_mirrored_controls_if_rendered": "flange_reinforcement_basic" not in group_ids or int(trace.get("flange_reinforcement_basic_widget_metadata_count") or 0) >= 14,
        "expected_flange_reinforcement_keys_present_if_rendered": "flange_reinforcement_basic" not in group_ids or all(
            key in flange_reinforcement_keys
            for key in (
                "inputs_top_flange_reo_enabled",
                "inputs_top_flange_mirror_lr",
                "inputs_top_flange_left_count",
                "inputs_top_flange_left_dia",
                "inputs_bot_flange_reo_enabled",
                "inputs_bot_flange_mirror_lr",
                "inputs_bot_flange_left_count",
                "inputs_bot_flange_left_dia",
            )
        ),
        "flange_transverse_widget_metadata_hash_present_if_rendered": "flange_transverse_basic" not in group_ids or bool(str(trace.get("flange_transverse_basic_widget_metadata_hash") or "").strip()),
        "flange_transverse_widget_metadata_count_eight_if_rendered": "flange_transverse_basic" not in group_ids or int(trace.get("flange_transverse_basic_widget_metadata_count") or 0) == 8,
        "expected_flange_transverse_keys_present_if_rendered": "flange_transverse_basic" not in group_ids or all(
            key in flange_transverse_keys
            for key in (
                "inputs_top_flange_transverse_enabled",
                "inputs_top_flange_transverse_dia",
                "inputs_top_flange_transverse_spacing",
                "inputs_top_flange_transverse_legs",
                "inputs_bot_flange_transverse_enabled",
                "inputs_bot_flange_transverse_dia",
                "inputs_bot_flange_transverse_spacing",
                "inputs_bot_flange_transverse_legs",
            )
        ),
        "flange_groups_recorded_when_required": not require_flange_groups or (
            "flange_reinforcement_basic" in group_ids and "flange_transverse_basic" in group_ids
        ),
    }
    failures = [key for key, value in checks.items() if not value]
    return {
        "status": "PASS" if not failures else "FAIL",
        "decision": "READY_FOR_WIDGET_METADATA_EXTRACTION" if not failures else "LIVE_WIDGET_METADATA_TRACE_GAPS_REMAIN",
        "checks": checks,
        "failures": failures,
        "detailed_groups_required": bool(require_detailed_groups),
        "flange_groups_required": bool(require_flange_groups),
        "effective_section_shape": effective_section_shape,
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"inputs_widgets_live_trace_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"inputs_widgets_live_trace_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    lines = [
        "# Inputs Widgets Live Trace Parity Snapshot",
        "",
        f"## Executive Summary: {payload['classification']['decision']}",
        "",
        f"- Status: `{payload['classification']['status']}`",
        f"- Trace found: `{payload['trace_found']}`",
        f"- Product behavior changed: `{payload['product_behavior_changed']}`",
        f"- Widget keys changed: `{payload['widget_keys_changed']}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in dict(payload["classification"].get("checks") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    if payload["classification"].get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["classification"]["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8621)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--recipe", default="R1A_M300_V0")
    parser.add_argument("--timeout-s", type=float, default=75.0)
    parser.add_argument("--page-wait-ms", type=int, default=60000)
    parser.add_argument("--design-mode", choices=("fast", "detailed"), default="fast")
    parser.add_argument("--section-shape", choices=("default", "T", "I"), default="default")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    created_at = _stamp()
    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://127.0.0.1:{args.port}")
    paths_before = _trace_files()
    trace_started_at = time.time()
    env_before = dict(os.environ)
    try:
        if not args.base_url:
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            os.environ["PERF_TRACE_INPUTS"] = "1"
            process = _start_streamlit(int(args.port))
            _wait_for_http(base_url, timeout_s=60.0)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not bool(args.headed))
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 1100})
                url = _query(
                    base_url,
                    {
                        "page": "inputs",
                        "browser_recipe": str(args.recipe),
                        "batch_design_open": "0",
                    },
                )
                page.goto(url, wait_until="domcontentloaded", timeout=int(args.timeout_s * 1000))
                if args.design_mode == "detailed":
                    page.get_by_text("Detailed", exact=True).click(timeout=30000)
                if args.section_shape in {"T", "I"}:
                    try:
                        page.get_by_role("combobox", name=re.compile(r"Section shape")).click(timeout=30000)
                        page.get_by_text(args.section_shape, exact=True).click(timeout=30000)
                    except Exception:
                        page.get_by_role("combobox", name=re.compile(r"Section shape")).click(timeout=30000)
                        page.get_by_text(args.section_shape, exact=True).click(timeout=30000)
                page.wait_for_timeout(int(args.page_wait_ms))
            finally:
                browser.close()
        trace = _wait_for_trace(
            paths_before,
            timeout_s=float(args.timeout_s),
            started_at=trace_started_at,
            require_detailed_groups=args.design_mode == "detailed",
            require_flange_groups=args.section_shape in {"T", "I"},
        )
        classification = _classify(
            trace,
            require_detailed_groups=args.design_mode == "detailed",
            require_flange_groups=args.section_shape in {"T", "I"},
            section_shape=str(args.section_shape),
        )
        payload = {
            "created_at": created_at,
            "base_url": base_url,
            "recipe": args.recipe,
            "design_mode": args.design_mode,
            "section_shape": args.section_shape,
            "trace_found": isinstance(trace, dict),
            "trace": trace,
            "classification": classification,
            "product_behavior_changed": False,
            "visible_wording_changed": False,
            "cta_apply_semantics_changed": False,
            "widget_keys_changed": False,
            "session_behavior_changed": False,
            "live_renderer_switched": False,
        }
        json_path, report_path = _write(payload)
        print("inputs_widgets_live_trace_parity_snapshot", classification["status"])
        print(f"decision={classification['decision']}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 0 if classification["status"] == "PASS" else 1
    finally:
        os.environ.clear()
        os.environ.update(env_before)
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
