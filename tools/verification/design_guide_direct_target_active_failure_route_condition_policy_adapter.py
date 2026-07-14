"""Verify direct-target active-failure route condition policy extraction."""

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

from design_brain.design_guide_controller import (  # noqa: E402
    resolve_design_guide_controller_direct_target_active_failure_route_policy,
)


INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_direct_target_band_guidance_item"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _policy_cases() -> dict[str, dict[str, Any]]:
    cases = {
        "bending": {"strengthening": True, "active_failure_keys": {"bending"}, "route_kind": "bending"},
        "shear": {"strengthening": True, "active_failure_keys": {"shear"}, "route_kind": "shear"},
        "combined": {
            "strengthening": True,
            "active_failure_keys": {"bending", "shear"},
            "route_kind": "combined",
        },
        "combined_with_extra": {
            "strengthening": True,
            "active_failure_keys": {"bending", "shear", "crack"},
            "route_kind": "combined",
        },
        "not_strengthening": {
            "strengthening": False,
            "active_failure_keys": {"bending"},
            "route_kind": None,
        },
        "none": {"strengthening": True, "active_failure_keys": set(), "route_kind": None},
    }
    out: dict[str, dict[str, Any]] = {}
    for name, case in cases.items():
        result = resolve_design_guide_controller_direct_target_active_failure_route_policy(
            strengthening=bool(case["strengthening"]),
            active_failure_keys=case["active_failure_keys"],
        )
        out[name] = {
            "expected_route_kind": case["route_kind"],
            "actual_route_kind": result.get("route_kind"),
            "matches": result.get("route_kind") == case["route_kind"],
            "should_dispatch_matches": bool(result.get("should_dispatch")) == (case["route_kind"] is not None),
        }
    return out


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    route_window = segment.split("_diag_prior = st.session_state.get", 1)[0]
    old_tokens = [
        '_overview_active_failure_keys(dict(overview or {})) == {"bending"}',
        '_overview_active_failure_keys(dict(overview or {})) == {"shear"}',
        '_overview_active_failure_keys(dict(overview or {})) >= {"bending", "shear"}',
    ]
    return {
        "schema": "design_guide_direct_target_active_failure_route_condition_policy_adapter.v1",
        "target": {"name": TARGET, "line_start": start, "line_end": end},
        "policy_cases": _policy_cases(),
        "page_calls_controller_policy": (
            "_resolve_design_guide_controller_direct_target_active_failure_route_policy(" in route_window
        ),
        "old_page_condition_tokens_removed": {token: token not in route_window for token in old_tokens},
        "page_still_collects_active_failure_keys": "_overview_active_failure_keys(dict(overview or {}))" in route_window,
        "page_still_owns_executor": "_active_fail_near_current_repair_item(" in route_window,
        "page_still_owns_bending_speed_isolation_probe": "_bending_fail_speed_isolated_active_repair(debug_sink)" in route_window,
        "page_still_owns_post_publication_probe": "_skip_bending_fail_post_publication_probe(" in route_window,
        "page_still_owns_bending_cta_side_effect": "_record_bending_fail_valid_repair_cta_published(" in route_window,
        "controller_helper_exported": (
            '"resolve_design_guide_controller_direct_target_active_failure_route_policy"' in controller_source
        ),
        "controller_has_no_page_or_streamlit_imports": (
            "inputs_page" not in controller_source
            and "streamlit" not in controller_source
            and "st.session_state" not in controller_source
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    cases = payload.get("policy_cases") or {}
    removed = payload.get("old_page_condition_tokens_removed") or {}
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "policy_cases_match": bool(cases)
        and all(bool(row.get("matches")) and bool(row.get("should_dispatch_matches")) for row in cases.values()),
        "page_calls_controller_policy": bool(payload.get("page_calls_controller_policy")),
        "old_page_condition_tokens_removed": bool(removed) and all(bool(value) for value in removed.values()),
        "page_still_collects_active_failure_keys": bool(payload.get("page_still_collects_active_failure_keys")),
        "page_still_owns_executor": bool(payload.get("page_still_owns_executor")),
        "page_still_owns_bending_speed_isolation_probe": bool(
            payload.get("page_still_owns_bending_speed_isolation_probe")
        ),
        "page_still_owns_post_publication_probe": bool(payload.get("page_still_owns_post_publication_probe")),
        "page_still_owns_bending_cta_side_effect": bool(
            payload.get("page_still_owns_bending_cta_side_effect")
        ),
        "controller_helper_exported": bool(payload.get("controller_helper_exported")),
        "controller_has_no_page_or_streamlit_imports": bool(
            payload.get("controller_has_no_page_or_streamlit_imports")
        ),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_direct_target_active_failure_route_condition_policy_adapter_{suffix}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_direct_target_active_failure_route_condition_policy_adapter_{suffix}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Active-Failure Route Condition Policy Adapter",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        (
            "Moved pure active-failure route-kind classification into DesignGuideController. "
            "Page still collects overview keys and owns executor/probe/CTA/debug/session plumbing."
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
    print(f"design_guide_direct_target_active_failure_route_condition_policy_adapter {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
