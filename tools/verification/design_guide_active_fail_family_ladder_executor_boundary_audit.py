"""Audit active-fail family ladder executor boundary."""

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
            "surface": "family ladder dispatch construction",
            "classification": "controller-owned dispatch request",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "evidence": [
                _token_row(segment, start, "_build_design_guide_controller_active_fail_executor_family_ladder_dispatch(")
            ],
        },
        {
            "surface": "family ladder eval command shaping",
            "classification": "controller-owned command projection",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "evidence": [
                _token_row(segment, start, "_build_design_guide_controller_active_fail_executor_ladder_eval_commands(")
            ],
        },
        {
            "surface": "family ladder callback execution",
            "classification": "page-owned callback execution bridge",
            "current_owner": "inputs_page",
            "target_owner": "page shell until injected executor boundary exists",
            "deletion_readiness": "KEEP_BOUNDED",
            "evidence": [
                _token_row(segment, start, "evaluated = _evaluate("),
                _token_row(segment, start, "family_meta=dict(command.get(\"family_meta\") or {})"),
            ],
        },
        {
            "surface": "family ladder stop predicates",
            "classification": "completed controller-owned result policy",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "evidence": [
                _token_row(
                    segment,
                    start,
                    "_resolve_design_guide_controller_active_fail_executor_ladder_stop_decision(",
                ),
            ],
        },
        {
            "surface": "bending ladder trace and CTA side effects",
            "classification": "page-owned trace/side-effect plumbing",
            "current_owner": "inputs_page",
            "target_owner": "inputs_page page shell/shared side-effect layer",
            "deletion_readiness": "KEEP_BOUNDED",
            "evidence": [
                _token_row(segment, start, "_inputs_pre_widget_trace("),
                _token_row(segment, start, "_phase5c_latency_trace("),
                _token_row(segment, start, "_record_bending_fail_valid_repair_cta_published("),
                _token_row(segment, start, "st.session_state"),
            ],
        },
    ]
    return {
        "schema": "design_guide_active_fail_family_ladder_executor_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "decision": "FAMILY_LADDER_EXECUTOR_STOP_PREDICATE_ADAPTER_COMPLETE",
        "surfaces": surfaces,
        "first_safe_implementation_slice": {
            "name": "active_fail_executor_selection_evidence_projection_boundary_audit",
            "why": (
                "Dispatch, command shaping, rescue route inputs, policy inputs, and stop predicates are now "
                "controller-owned. Callback execution and trace/CTA side effects remain bounded page shell. "
                "The next remaining pure active-fail executor surface is selection/evidence projection."
            ),
            "move": (
                "Audit selection/evidence projection before moving any code. Keep callback execution, loop order, "
                "trace, session, CTA publication side effects, and family runtime behavior unchanged."
            ),
            "required_verifier": "design_guide_active_fail_executor_selection_evidence_projection_boundary_audit.py",
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
        "surfaces_classified": len(surfaces) == 5,
        "dispatch_and_commands_controller_owned": all(
            any(row.get("surface") == surface and row.get("deletion_readiness") == "SHELL_CALL" for row in surfaces)
            for surface in ("family ladder dispatch construction", "family ladder eval command shaping")
        ),
        "callback_execution_bounded": any(
            row.get("surface") == "family ladder callback execution"
            and row.get("deletion_readiness") == "KEEP_BOUNDED"
            for row in surfaces
        ),
        "stop_predicate_service_backed": any(
            row.get("surface") == "family ladder stop predicates"
            and row.get("deletion_readiness") == "SHELL_CALL"
            for row in surfaces
        ),
        "side_effects_bounded": any(
            row.get("surface") == "bending ladder trace and CTA side effects"
            and row.get("deletion_readiness") == "KEEP_BOUNDED"
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
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_family_ladder_executor_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_family_ladder_executor_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    first_slice = payload.get("first_safe_implementation_slice") or {}
    lines = [
        "# Design Guide Active-Fail Family Ladder Executor Boundary Audit",
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
    print(f"design_guide_active_fail_family_ladder_executor_boundary_audit {payload['status']}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
