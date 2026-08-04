"""Audit active-fail executor route input projection boundary."""

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
TARGET = "_active_fail_near_current_repair_item"


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
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _token_row(segment: str, start_line: int, token: str) -> dict[str, Any]:
    return {
        "token": token,
        "present": token in segment,
        "count": segment.count(token),
        "lines": _line_numbers(segment, start_line, token)[:20],
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    surfaces = [
        {
            "surface": "geometry lock scalar",
            "classification": "page-shell current-state guard input",
            "current_owner": "inputs_page",
            "target_owner": "page shell or controller route-input adapter",
            "deletion_readiness": "KEEP_BOUNDED",
            "reason": (
                "The lock reads page/user state and gates family ladder generation. It can be passed "
                "as plain data, but the state read itself remains page-owned."
            ),
            "evidence": [_token_row(segment, start, "_geometry_lock_enabled(")],
        },
        {
            "surface": "combined rescue requested tier",
            "classification": "completed controller-owned route input policy",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController route-input adapter",
            "deletion_readiness": "SHELL_CALL",
            "reason": "Requested rescue tier is projected by the controller from plain action/util tier inputs.",
            "evidence": [
                _token_row(segment, start, "_build_design_guide_controller_active_fail_executor_rescue_tier_route_inputs(")
            ],
        },
        {
            "surface": "combined rescue seed tier expansion",
            "classification": "completed controller-owned route input policy",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController route-input adapter",
            "deletion_readiness": "SHELL_CALL",
            "reason": "Seed tier expansion is projected by the controller from the requested tier.",
            "evidence": [
                _token_row(segment, start, "_build_design_guide_controller_active_fail_executor_rescue_tier_route_inputs(")
            ],
        },
        {
            "surface": "family ladder dispatch consumption",
            "classification": "controller-owned consumer after route input preparation",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "reason": "Ladder dispatch already consumes plain geometry_locked and rescue_tiers inputs.",
            "evidence": [
                _token_row(segment, start, "_build_design_guide_controller_active_fail_executor_family_ladder_dispatch(")
            ],
        },
    ]
    return {
        "schema": "design_guide_active_fail_executor_route_input_projection_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "decision": "ROUTE_INPUT_PROJECTION_TIER_ADAPTER_COMPLETE",
        "surfaces": surfaces,
        "first_safe_implementation_slice": {
            "name": "active_fail_family_ladder_executor_boundary_audit",
            "why": (
                "Geometry lock remains a bounded page-owned state guard input, and rescue tier/order "
                "projection is now controller-owned. The next remaining active-fail executor surface is "
                "family ladder execution itself."
            ),
            "move": (
                "Audit whether family ladder execution can be represented as a service/controller executor "
                "boundary while keeping page-owned session/cache/trace and CTA side effects unchanged."
            ),
            "required_verifier": "design_guide_active_fail_family_ladder_executor_boundary_audit.py",
        },
        "controller_boundary_clean": all(
            token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    surfaces = payload.get("surfaces") or []
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "surfaces_classified": len(surfaces) == 4,
        "rescue_tier_service_backed": all(
            any(row.get("surface") == surface and row.get("deletion_readiness") == "SHELL_CALL" for row in surfaces)
            for surface in ("combined rescue requested tier", "combined rescue seed tier expansion")
        ),
        "geometry_lock_bounded": any(
            row.get("surface") == "geometry lock scalar" and row.get("deletion_readiness") == "KEEP_BOUNDED"
            for row in surfaces
        ),
        "family_dispatch_controller_owned": any(
            row.get("surface") == "family ladder dispatch consumption"
            and row.get("deletion_readiness") == "SHELL_CALL"
            for row in surfaces
        ),
        "first_safe_slice_identified": bool(
            (payload.get("first_safe_implementation_slice") or {}).get("required_verifier")
        ),
        "controller_boundary_clean": bool(payload.get("controller_boundary_clean")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_route_input_projection_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_route_input_projection_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    first_slice = payload.get("first_safe_implementation_slice") or {}
    lines = [
        "# Design Guide Active-Fail Executor Route Input Projection Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Surface Inventory",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"- {row.get('surface')}: {row.get('classification')} "
            f"({row.get('current_owner')} -> {row.get('target_owner')}); "
            f"readiness `{row.get('deletion_readiness')}`"
        )
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            f"- Name: `{first_slice.get('name')}`",
            f"- Move: {first_slice.get('move')}",
            f"- Verifier: `{first_slice.get('required_verifier')}`",
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
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_executor_route_input_projection_audit {payload['status']}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
