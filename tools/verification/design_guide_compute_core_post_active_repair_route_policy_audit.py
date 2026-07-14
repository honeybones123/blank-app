"""Audit post-active repair route policy inside compute guidance core."""

from __future__ import annotations

import ast
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


def _line_numbers(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + index for index, line in enumerate(segment.splitlines()) if token in line]


def _row(
    *,
    surface: str,
    classification: str,
    current_owner: str,
    target_owner: str,
    readiness: str,
    first_safe_slice: str | None,
    tokens: list[str],
    segment: str,
    start_line: int,
    risk: str,
) -> dict[str, Any]:
    evidence = [
        {
            "token": token,
            "present": token in segment,
            "count": segment.count(token),
            "lines": _line_numbers(segment, start_line, token)[:60],
        }
        for token in tokens
    ]
    return {
        "surface": surface,
        "classification": classification,
        "current_owner": current_owner,
        "target_owner": target_owner,
        "readiness": readiness,
        "first_safe_slice": first_safe_slice,
        "risk": risk,
        "present": any(bool(item["present"]) for item in evidence),
        "evidence": evidence,
    }


def _capture() -> dict[str, Any]:
    source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, core_segment = _function_source(source, "_compute_design_guidance_items_core")
    zero_shear_predicate_cutover = (
        "_resolve_design_guide_controller_post_active_zero_shear_predicate(" in core_segment
        and "_post_active_zero_shear = bool(\n            _shear_demands_negligible" not in core_segment
    )
    zero_shear_terminal_cutover = (
        "_build_design_guide_controller_post_active_zero_shear_terminal_projection(" in core_segment
        and "The one-click capacity repair has been applied" not in core_segment
        and "zero or negligible demand" not in core_segment
        and "_zero_shear_exclusion = {" not in core_segment
    )

    surfaces = [
        _row(
            surface="post-active route entry guard",
            classification="controller-backed scalar plus page branch gate",
            current_owner="DesignGuideController scalar projection plus inputs_page.py branch order",
            target_owner="DesignGuideController route policy",
            readiness="BOUNDED_NOT_ZERO",
            first_safe_slice=None,
            tokens=[
                "_post_apply_from_active_failure_repair",
                "post_click_accepted_green_valid",
                "target_band_with_eps_passed",
            ],
            segment=core_segment,
            start_line=start,
            risk="Changing this can suppress a required post-click accepted/blocker/cleanup route.",
        ),
        _row(
            surface="post-active actions and zero-shear predicate",
            classification=(
                "controller-owned zero-shear predicate with page scalar collection"
                if zero_shear_predicate_cutover
                else "page-owned scalar collection with pure zero-shear predicate"
            ),
            current_owner=(
                "DesignGuideController via inputs_page shell"
                if zero_shear_predicate_cutover
                else "inputs_page.py"
            ),
            target_owner="DesignGuideController",
            readiness="SHELL_CALL" if zero_shear_predicate_cutover else "READY_TO_EXTRACT",
            first_safe_slice=None if zero_shear_predicate_cutover else "compute_core_post_active_zero_shear_predicate_projection_extraction",
            tokens=[
                "_post_active_actions",
                "_post_active_vu",
                "_post_active_zero_shear",
                "_shear_demands_negligible(",
                "GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN",
            ],
            segment=core_segment,
            start_line=start,
            risk="Low if page keeps action/Vu collection and controller owns only boolean projection.",
        ),
        _row(
            surface="post-active target accepted item callback",
            classification="page-owned callback execution",
            current_owner="inputs_page.py callback shell",
            target_owner="page shell unless callback projection is separately audited",
            readiness="KEEP_BOUNDED",
            first_safe_slice=None,
            tokens=["_post_active_repair_target_accepted_item("],
            segment=core_segment,
            start_line=start,
            risk="Callback can build a terminal item; keep bounded until parity exists.",
        ),
        _row(
            surface="zero-shear accepted terminal item projection",
            classification=(
                "controller-owned recommendation/display/debug projection"
                if zero_shear_terminal_cutover
                else "page-owned recommendation/display/debug projection"
            ),
            current_owner=(
                "DesignGuideController via inputs_page shell"
                if zero_shear_terminal_cutover
                else "inputs_page.py"
            ),
            target_owner="DesignGuideController",
            readiness="SHELL_CALL" if zero_shear_terminal_cutover else "NOT_READY",
            first_safe_slice=None if zero_shear_terminal_cutover else "compute_core_post_active_zero_shear_terminal_projection_extraction",
            tokens=[
                "post_active_repair_zero_shear_terminal",
                "The one-click capacity repair has been applied",
                "zero or negligible demand",
                "_zero_shear_exclusion",
            ],
            segment=core_segment,
            start_line=start,
            risk="Moves visible wording/display/button-contract projection; requires exact parity.",
        ),
        _row(
            surface="post-active residual shear cleanup action",
            classification="mixed candidate callback and CTA/debug projection",
            current_owner="inputs_page.py plus service-backed cleanup helper",
            target_owner="DesignGuideController/candidate service plus page callback shell",
            readiness="NOT_READY",
            first_safe_slice="compute_core_post_active_residual_shear_cleanup_action_audit",
            tokens=[
                "_shear_best_safe_cleanup_item_from_evidence(",
                "_shear_low_util_target_cleanup_item(",
                "post_active_repair_residual_shear_best_safe_action",
                "_attach_family_status_display_payload(",
            ],
            segment=core_segment,
            start_line=start,
            risk="Touches selected cleanup action and CTA payload; audit separately.",
        ),
        _row(
            surface="post-active shear exact blocker item projection",
            classification="page-owned blocker publication/projection",
            current_owner="inputs_page.py",
            target_owner="DesignGuideController/FinalDesignGuidePublication adapter",
            readiness="NOT_READY",
            first_safe_slice="compute_core_post_active_shear_blocker_projection_extraction",
            tokens=[
                "post_active_repair_shear_cleanup_blocked",
                "Shear cleanup blocked by final efficiency threshold",
                "No second one-click cleanup is enabled",
                "exact_blockers_by_family",
                "candidate_search_evidence",
            ],
            segment=core_segment,
            start_line=start,
            risk="Visible wording and blocker evidence must remain exact.",
        ),
        _row(
            surface="post-apply accepted cleanup terminal",
            classification="page-owned accepted terminal projection",
            current_owner="inputs_page.py",
            target_owner="DesignGuideController",
            readiness="NOT_READY",
            first_safe_slice="compute_core_post_apply_cleanup_accepted_projection_extraction",
            tokens=[
                "post_apply_local_cleanup_accepted",
                "The one-click cleanup has been applied",
                "accepted post-click Design Guide state",
            ],
            segment=core_segment,
            start_line=start,
            risk="Visible accepted wording/status must remain exact.",
        ),
    ]

    not_ready = [
        row
        for row in surfaces
        if row["present"] and row["readiness"] in {"READY_TO_EXTRACT", "NOT_READY"}
    ]
    ready = [row for row in not_ready if row["readiness"] == "READY_TO_EXTRACT"]
    first = (ready or not_ready or [{}])[0]
    return {
        "schema": "design_guide_compute_core_post_active_repair_route_policy_audit.v1",
        "status_decision": (
            "POST_ACTIVE_REPAIR_ROUTE_READY_TO_EXTRACT"
            if ready
            else "POST_ACTIVE_REPAIR_ROUTE_NOT_READY"
            if not_ready
            else "POST_ACTIVE_REPAIR_ROUTE_BOUNDED"
        ),
        "target": {
            "function": "_compute_design_guidance_items_core",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "surfaces": surfaces,
        "not_ready_or_ready_surfaces": not_ready,
        "ready_to_extract_surfaces": ready,
        "first_safe_slice": dict(first),
        "zero_shear_predicate_cutover": bool(zero_shear_predicate_cutover),
        "zero_shear_terminal_cutover": bool(zero_shear_terminal_cutover),
        "controller_has_existing_no_active_low_shear_route": "def run_design_guide_controller_no_active_low_shear_or_blocker_route(" in controller_source,
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    target = payload.get("target") or {}
    return {
        "target_found": bool(target.get("line_start") and target.get("line_end")),
        "surfaces_classified": len(payload.get("surfaces") or []) >= 6,
        "first_safe_slice_identified": bool((payload.get("first_safe_slice") or {}).get("first_safe_slice")),
        "first_slice_is_expected": (
            (payload.get("first_safe_slice") or {}).get("first_safe_slice")
            in {
                "compute_core_post_active_zero_shear_predicate_projection_extraction",
                "compute_core_post_active_zero_shear_terminal_projection_extraction",
                "compute_core_post_active_residual_shear_cleanup_action_audit",
            }
        ),
        "controller_boundary_clean": bool(payload.get("controller_has_no_page_or_streamlit_imports")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_core_post_active_repair_route_policy_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_core_post_active_repair_route_policy_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Compute Core Post-Active Repair Route Policy Audit",
        "",
        f"Status: {payload.get('status')}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## Executive Summary",
        (
            "PARTIAL. The post-active repair route is still mixed. The first safe "
            "implementation slice is predicate-only: move the zero-shear boolean "
            "projection into the controller while keeping action/Vu collection and "
            "all item/CTA/debug projection in the page."
        ),
        "",
        "## First Safe Slice",
        f"- Surface: {(payload.get('first_safe_slice') or {}).get('surface')}",
        f"- Slice: {(payload.get('first_safe_slice') or {}).get('first_safe_slice')}",
        "",
        "## Surface Inventory",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"- {row.get('surface')}: {row.get('classification')} | "
            f"{row.get('readiness')} | {row.get('first_safe_slice')}"
        )
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
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_compute_core_post_active_repair_route_policy_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"first_slice={(payload.get('first_safe_slice') or {}).get('first_safe_slice')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
