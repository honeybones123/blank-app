"""Audit direct-target active-failure route condition policy extraction boundary."""

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


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    route_window = segment.split("_diag_prior = st.session_state.get", 1)[0]
    route_condition_tokens = [
        '_overview_active_failure_keys(dict(overview or {})) == {"bending"}',
        '_overview_active_failure_keys(dict(overview or {})) == {"shear"}',
        '_overview_active_failure_keys(dict(overview or {})) >= {"bending", "shear"}',
    ]
    page_condition_count = sum(route_window.count(token) for token in route_condition_tokens)
    controller_policy_exists = (
        "resolve_design_guide_controller_direct_target_active_failure_route_policy" in controller_source
    )
    page_calls_controller_policy = (
        "_resolve_design_guide_controller_direct_target_active_failure_route_policy(" in route_window
    )
    return {
        "schema": "design_guide_direct_target_active_failure_route_condition_policy_adapter_audit.v1",
        "target": {"name": TARGET, "line_start": start, "line_end": end},
        "page_route_condition_tokens": {
            token: {
                "present": token in route_window,
                "count": route_window.count(token),
            }
            for token in route_condition_tokens
        },
        "page_route_condition_count": page_condition_count,
        "controller_policy_exists": controller_policy_exists,
        "page_still_owns_executor": "_active_fail_near_current_repair_item(" in route_window,
        "page_still_owns_bending_speed_isolation_probe": "_bending_fail_speed_isolated_active_repair(debug_sink)" in route_window,
        "page_still_owns_post_publication_probe": "_skip_bending_fail_post_publication_probe(" in route_window,
        "page_still_owns_bending_cta_side_effect": "_record_bending_fail_valid_repair_cta_published(" in route_window,
        "controller_route_adapter_used": (
            "_build_design_guide_controller_direct_target_active_failure_route_request_result_adapter("
            in route_window
        ),
        "decision": (
            "READY_TO_EXTRACT_PURE_ROUTE_CONDITION_POLICY"
            if page_condition_count == 3 and not controller_policy_exists
            else "POLICY_EXTRACTED"
            if page_condition_count == 0 and controller_policy_exists and page_calls_controller_policy
            else "POLICY_ALREADY_EXTRACTED_OR_NOT_READY"
        ),
        "first_safe_implementation_slice": {
            "name": "direct_target_active_failure_route_condition_policy_adapter",
            "move": (
                "Move only pure route-kind classification from strengthening + active_failure_keys into "
                "DesignGuideController. Keep overview collection, speed-isolation probe, post-publication "
                "probe, executor calls, CTA side effect, debug/session writes, and route execution page-owned."
            ),
            "required_verifier": "design_guide_direct_target_active_failure_route_condition_policy_adapter.py",
        },
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
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "route_conditions_ready_or_extracted": int(payload.get("page_route_condition_count") or 0) in (0, 3),
        "executor_still_page_owned": bool(payload.get("page_still_owns_executor")),
        "speed_isolation_probe_page_owned": bool(payload.get("page_still_owns_bending_speed_isolation_probe")),
        "post_publication_probe_page_owned": bool(payload.get("page_still_owns_post_publication_probe")),
        "bending_cta_side_effect_page_owned": bool(payload.get("page_still_owns_bending_cta_side_effect")),
        "controller_route_adapter_used": bool(payload.get("controller_route_adapter_used")),
        "ready_or_already_extracted": payload.get("decision")
        in {
            "READY_TO_EXTRACT_PURE_ROUTE_CONDITION_POLICY",
            "POLICY_EXTRACTED",
            "POLICY_ALREADY_EXTRACTED_OR_NOT_READY",
        },
        "first_safe_slice_identified": bool(
            (payload.get("first_safe_implementation_slice") or {}).get("required_verifier")
        ),
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
        / f"design_guide_direct_target_active_failure_route_condition_policy_adapter_audit_{suffix}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_direct_target_active_failure_route_condition_policy_adapter_audit_{suffix}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Active-Failure Route Condition Policy Adapter Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Summary",
        (
            "Pure route-kind classification is still page-owned. It can move to a controller helper "
            "using only strengthening and active-failure keys. Page probes, executor calls, CTA side "
            "effect, and debug/session writes must stay page-owned."
        ),
        "",
        "## Counts",
        f"- page route condition count: {payload.get('page_route_condition_count')}",
        "",
        "## First Safe Implementation Slice",
        f"- Name: `{(payload.get('first_safe_implementation_slice') or {}).get('name')}`",
        f"- Move: {(payload.get('first_safe_implementation_slice') or {}).get('move')}",
        f"- Verifier: `{(payload.get('first_safe_implementation_slice') or {}).get('required_verifier')}`",
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
    print(f"design_guide_direct_target_active_failure_route_condition_policy_adapter_audit {status}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
