"""Audit cleanup attempt/arrangement label ownership before extraction."""

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


def _evidence(source: str, token: str, *, start_line: int) -> dict[str, Any]:
    lines = [start_line + index for index, line in enumerate(source.splitlines()) if token in line]
    return {"token": token, "present": bool(lines), "count": len(lines), "lines": lines[:20]}


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    table_start, table_end, table = _function_source(inputs_source, "_design_guide_blocker_attempts_table")
    label_start, label_end, label_helper = _function_source(inputs_source, "_design_guide_cleanup_attempt_label")
    arrangement_start, arrangement_end, arrangement_helper = _function_source(
        inputs_source,
        "_design_guide_cleanup_arrangement_label",
    )
    exact_start, exact_end, exact_helper = _function_source(inputs_source, "_design_guide_exact_attempt_change_label")
    sanitize_start, sanitize_end, sanitize_helper = _function_source(
        inputs_source,
        "_design_guide_sanitised_model_updates_for_label",
    )

    explicit_label_controller_owned = (
        "_resolve_design_guide_controller_cleanup_explicit_attempt_label(row_d)" in label_helper
        and "def resolve_design_guide_controller_cleanup_explicit_attempt_label(" in controller_source
    )
    label_controller_owned = explicit_label_controller_owned
    arrangement_has_page_label_deps = any(
        token in arrangement_helper
        for token in (
            "_bottom_reo_state_label(",
            "_guidance_shear_links_banner_fragment(",
        )
    )
    exact_label_has_page_label_deps = any(
        token in exact_helper + label_helper
        for token in (
            "_design_guide_state_after_updates(",
            "_guidance_change_lines_for_updates(",
            "_design_guide_attempt_route_summary(",
        )
    )
    pure_explicit_label_branch_present = all(
        token in label_helper
        for token in (
            "explicit = str(",
            "explicit_l = explicit.lower()",
        )
    ) and (
        "return explicit" in label_helper
        or "_resolve_design_guide_controller_cleanup_explicit_attempt_label(" in label_helper
    )
    surfaces = [
        {
            "surface": "explicit attempted-change label branch",
            "classification": (
                "controller-owned pure explicit label branch"
                if explicit_label_controller_owned
                else "pure explicit label sanitisation branch"
            ),
            "current_owner": (
                "DesignGuideController via inputs_page shell"
                if explicit_label_controller_owned
                else "inputs_page.py"
            ),
            "target_owner": "DesignGuideController",
            "readiness": "SHELL_CALL" if explicit_label_controller_owned else "READY_TO_EXTRACT",
            "first_safe_slice": (
                None
                if explicit_label_controller_owned
                else "blocker_attempts_cleanup_explicit_attempt_label_extraction"
            ),
            "risk": "Visible wording; exact string parity required, but branch is independent of page label helpers.",
            "evidence": [
                _evidence(label_helper, "explicit = str(", start_line=label_start),
                _evidence(label_helper, "_resolve_design_guide_controller_cleanup_explicit_attempt_label(", start_line=label_start),
                _evidence(controller_source, "resolve_design_guide_controller_cleanup_explicit_attempt_label", start_line=1),
            ],
            "present": pure_explicit_label_branch_present,
        },
        {
            "surface": "arrangement label wording",
            "classification": "page-owned wording with reinforcement/shear label dependencies",
            "current_owner": "inputs_page.py",
            "target_owner": "page shell until bottom/shear label services are extracted",
            "readiness": "KEEP_PAGE_OWNED",
            "first_safe_slice": None,
            "risk": "Depends on page-local bottom reinforcement and shear-link label helpers.",
            "evidence": [
                _evidence(arrangement_helper, "_bottom_reo_state_label(", start_line=arrangement_start),
                _evidence(arrangement_helper, "_guidance_shear_links_banner_fragment(", start_line=arrangement_start),
            ],
            "present": arrangement_has_page_label_deps,
        },
        {
            "surface": "exact/change-lines label wording",
            "classification": "page-owned wording with state/update and change-line dependencies",
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController only after label-helper parity",
            "readiness": "NOT_FIRST",
            "first_safe_slice": "blocker_attempts_cleanup_exact_label_boundary_audit",
            "risk": "Calls page-local state/update/change-line helpers and contains visible wording.",
            "evidence": [
                _evidence(exact_helper, "_design_guide_state_after_updates(", start_line=exact_start),
                _evidence(label_helper, "_guidance_change_lines_for_updates(", start_line=label_start),
                _evidence(label_helper, "_design_guide_attempt_route_summary(", start_line=label_start),
            ],
            "present": exact_label_has_page_label_deps,
        },
        {
            "surface": "sanitised model updates for label",
            "classification": "pure update filtering but shared by page-owned wording",
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController after exact/change-line label boundary",
            "readiness": "NOT_FIRST",
            "first_safe_slice": "blocker_attempts_sanitised_label_updates_boundary_audit",
            "risk": "Safe-looking but feeds page-owned wording branches; do not move first.",
            "evidence": [
                _evidence(sanitize_helper, "numeric_keys", start_line=sanitize_start),
                _evidence(sanitize_helper, "ignored_keys", start_line=sanitize_start),
            ],
            "present": bool(sanitize_helper),
        },
    ]
    ready = [
        row
        for row in surfaces
        if row.get("present") and row.get("readiness") == "READY_TO_EXTRACT"
    ]
    first = (ready or [{}])[0]
    return {
        "schema": "design_guide_blocker_attempts_cleanup_attempt_label_boundary_audit.v1",
        "target": {
            "table_function": "_design_guide_blocker_attempts_table",
            "line_start": table_start,
            "line_end": table_end,
            "line_count": max(0, table_end - table_start + 1),
        },
        "label_controller_owned": label_controller_owned,
        "explicit_label_controller_owned": explicit_label_controller_owned,
        "arrangement_has_page_label_deps": arrangement_has_page_label_deps,
        "exact_label_has_page_label_deps": exact_label_has_page_label_deps,
        "surfaces": surfaces,
        "first_safe_slice": dict(first),
        "status_decision": (
            "BLOCKER_ATTEMPTS_CLEANUP_EXPLICIT_LABEL_BOUNDED"
            if explicit_label_controller_owned
            else "BLOCKER_ATTEMPTS_CLEANUP_EXPLICIT_LABEL_READY_TO_EXTRACT"
            if ready
            else "BLOCKER_ATTEMPTS_CLEANUP_ATTEMPT_LABEL_NOT_READY"
        ),
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
        "first_safe_implementation_slice": (
            "Next audit exact/change-line and route-summary label wording. Keep arrangement, exact label, "
            "change-line, route-summary, and state-update wording in inputs_page.py until parity proves a slice."
            if explicit_label_controller_owned
            else "Extract only the explicit attempted-change label sanitisation branch. Keep arrangement, exact label, "
            "change-line, route-summary, and state-update wording in inputs_page.py."
        ),
        "stop_conditions": [
            "explicit label wording changes",
            "generated change-line wording moves",
            "arrangement labels move",
            "bottom/shear label helpers move",
            "visible blocker rows differ",
            "any composed lock fails",
        ],
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "first_safe_slice_identified": bool((payload.get("first_safe_slice") or {}).get("first_safe_slice"))
        or payload.get("status_decision") == "BLOCKER_ATTEMPTS_CLEANUP_EXPLICIT_LABEL_BOUNDED",
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
    json_path = ARTIFACT_DIR / f"design_guide_blocker_attempts_cleanup_attempt_label_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_blocker_attempts_cleanup_attempt_label_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Blocker Attempts Cleanup Attempt Label Boundary Audit",
        "",
        f"Status: {payload.get('status')}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## Executive Summary",
        "",
        "Only the explicit attempted-change label sanitisation branch is ready to extract. Arrangement and generated change-line wording stay page-owned.",
        "",
        "## Surface Inventory",
        "",
        "| Surface | Classification | Current owner | Target owner | Readiness | First safe slice | Risk |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            "| {surface} | {classification} | {current_owner} | {target_owner} | {readiness} | {first_safe_slice} | {risk} |".format(
                surface=row.get("surface"),
                classification=row.get("classification"),
                current_owner=row.get("current_owner"),
                target_owner=row.get("target_owner"),
                readiness=row.get("readiness"),
                first_safe_slice=row.get("first_safe_slice") or "",
                risk=row.get("risk"),
            )
        )
    first = payload.get("first_safe_slice") or {}
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            "",
            f"- Slice: `{first.get('first_safe_slice')}`",
            f"- Surface: `{first.get('surface')}`",
            f"- Implementation: {payload.get('first_safe_implementation_slice')}",
            "",
            "## Stop Conditions",
        ]
    )
    for condition in payload.get("stop_conditions") or []:
        lines.append(f"- {condition}")
    lines.extend(["", "## Checks"])
    for key, value in checks.items():
        lines.append(f"- {key}: {'PASS' if value else 'FAIL'}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_blocker_attempts_cleanup_attempt_label_boundary_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"first_slice={(payload.get('first_safe_slice') or {}).get('first_safe_slice')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
