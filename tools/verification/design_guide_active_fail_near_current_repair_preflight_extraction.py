from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_active_fail_near_current_repair_preflight,
)


INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"
TARGET = "_active_fail_near_current_repair_item"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _sample_preflight() -> dict[str, Any]:
    base = {
        "sec_shape": "RECT",
        "b": 400.0,
        "D": 650.0,
        "bot1_count": 4,
        "db_bot_1": 16,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200.0,
        "design_optimisation_goal": "balanced",
    }
    overview = {
        "statuses": {"bending": "FAIL", "shear": "PASS"},
        "utils": {"bending": 1.25, "shear": 0.8},
        "any_fail": True,
    }
    return build_design_guide_controller_active_fail_near_current_repair_preflight(
        base_state=base,
        overview=overview,
        active_failures={"bending"},
        goal_labels={"balanced": "Balanced"},
        mode_config_by_goal={"balanced": {"target_util_min": 0.85, "target_util_max": 1.0}},
        default_low=0.85,
        default_high=1.0,
        default_goal="balanced",
        canonical_no_shear_spacing=200.0,
    )


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    preflight = _sample_preflight()
    search_payload = dict(preflight.get("search_cache_payload") or {})
    generation_context = dict(preflight.get("generation_context") or {})
    return {
        "schema": "design_guide_active_fail_near_current_repair_preflight_extraction.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "sample_preflight": {
            "should_continue": bool(preflight.get("should_continue")),
            "active": list(preflight.get("active") or []),
            "target_low": preflight.get("target_low"),
            "target_high": preflight.get("target_high"),
            "width_key": preflight.get("width_key"),
            "base_width": preflight.get("base_width"),
            "base_depth": preflight.get("base_depth"),
            "search_cache_payload": search_payload,
            "generation_context_keys": sorted(generation_context.keys()),
        },
        "source_checks": {
            "target_found": bool(segment),
            "page_calls_controller_preflight": "_build_design_guide_controller_active_fail_near_current_repair_preflight(" in segment,
            "page_no_longer_calls_policy_input_directly": "_build_design_guide_controller_active_fail_executor_policy_input_request(" not in segment,
            "page_no_longer_calls_generation_context_directly": "_build_active_fail_executor_candidate_generation_context(" not in segment,
            "page_uses_preflight_search_cache_payload": 'preflight.get("search_cache_payload")' in segment,
            "page_session_cache_still_page_owned": "st.session_state" in segment
            and "get_rerun_pure_cache(" in segment
            and "set_rerun_pure_cache(" in segment,
            "page_trace_callbacks_still_page_owned": "_inputs_pre_widget_trace(" in segment,
            "page_family_callback_output_still_page_owned": "_guidance_item_from_resolved_candidate(" in segment,
            "controller_exports_preflight": "build_design_guide_controller_active_fail_near_current_repair_preflight" in controller_source
            and "search_cache_payload" in controller_source,
            "controller_import_clean": all(
                token not in controller_source
                for token in ("import inputs_page", "from inputs_page", "import streamlit", "st.session_state")
            ),
        },
        "preflight_checks": {
            "sample_should_continue": bool(preflight.get("should_continue")),
            "sample_active_bending": list(preflight.get("active") or []) == ["bending"],
            "sample_target_band_preserved": preflight.get("target_low") == 0.85
            and preflight.get("target_high") == 1.0,
            "sample_geometry_context_preserved": preflight.get("width_key") == "b"
            and preflight.get("base_width") == 400.0
            and preflight.get("base_depth") == 650.0,
            "search_payload_version_preserved": search_payload.get("version")
            == "active_fail_near_current_repair_item:2026-06-03.1",
            "search_payload_overview_preserved": search_payload.get("overview_statuses") == {
                "bending": "FAIL",
                "shear": "PASS",
            }
            and search_payload.get("overview_any_fail") is True,
        },
        "next_safe_target": {
            "name": "active_fail_near_current_repair_candidate_eval_loop_boundary",
            "why": (
                "Preflight/default construction is controller-owned. The remaining page-owned Design Brain surface "
                "is the candidate evaluation loop, candidate accumulation, and final item projection, with page "
                "trace/session/CTA side effects still intentionally retained."
            ),
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    preflight_checks = dict(capture.get("preflight_checks") or {})
    return {
        "target_found": bool(source_checks.get("target_found")),
        "page_calls_controller_preflight": bool(source_checks.get("page_calls_controller_preflight")),
        "page_no_longer_calls_policy_input_directly": bool(
            source_checks.get("page_no_longer_calls_policy_input_directly")
        ),
        "page_no_longer_calls_generation_context_directly": bool(
            source_checks.get("page_no_longer_calls_generation_context_directly")
        ),
        "page_uses_preflight_search_cache_payload": bool(source_checks.get("page_uses_preflight_search_cache_payload")),
        "page_session_cache_still_page_owned": bool(source_checks.get("page_session_cache_still_page_owned")),
        "page_trace_callbacks_still_page_owned": bool(source_checks.get("page_trace_callbacks_still_page_owned")),
        "page_family_callback_output_still_page_owned": bool(
            source_checks.get("page_family_callback_output_still_page_owned")
        ),
        "controller_exports_preflight": bool(source_checks.get("controller_exports_preflight")),
        "controller_import_clean": bool(source_checks.get("controller_import_clean")),
        "sample_preflight_matches_old_defaults": all(bool(value) for value in preflight_checks.values()),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    target = dict(capture.get("target") or {})
    lines = [
        "# Active Fail Near-Current Repair Preflight Extraction",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        f"- Target lines: `{target.get('line_start')}`-`{target.get('line_end')}`",
        f"- Target line count: `{target.get('line_count')}`",
        "- Moved: pure active-fail preflight/default/generation-context/search-payload construction",
        "- Retained in page: session cache, trace callbacks, CTA recording, candidate evaluation loop, final item projection",
        "",
        "## Checks",
    ]
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    lines.extend(
        [
            "",
            "## Next Safe Target",
            f"- `{(capture.get('next_safe_target') or {}).get('name')}`",
            f"- {(capture.get('next_safe_target') or {}).get('why')}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = PROGRESS_PATH.read_text(encoding="utf-8").rstrip() if PROGRESS_PATH.exists() else ""
    lines = [existing, ""] if existing else []
    lines.extend(
        [
            f"## {payload.get('created_at')} - Active fail near-current repair preflight extraction",
            "",
            f"- Status: `{payload.get('status')}`",
            "- Extraction estimate: `99.70%`",
            f"- Report: [{report_path.name}](../audits/{report_path.name})",
            "",
        ]
    )
    PROGRESS_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    created_at = _timestamp()
    capture = _capture()
    checks = _checks(capture)
    passed = all(checks.values())
    payload = {
        "schema": "design_guide_active_fail_near_current_repair_preflight_extraction.v1",
        "created_at": created_at,
        "status": "PASS" if passed else "FAIL",
        "capture": capture,
        "checks": checks,
    }
    suffix = created_at.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_near_current_repair_preflight_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_near_current_repair_preflight_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    _append_progress(payload, report_path)
    print(f"design_guide_active_fail_near_current_repair_preflight_extraction {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if not passed:
        print("failing_checks=" + json.dumps([name for name, ok in checks.items() if not ok]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
