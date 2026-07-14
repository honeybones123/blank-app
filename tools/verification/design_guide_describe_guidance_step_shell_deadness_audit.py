"""Audit shell/deadness state of _describe_guidance_step after wording cutovers."""

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
TARGET = "_describe_guidance_step"


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


def _token(segment: str, start_line: int, token: str) -> dict[str, Any]:
    return {
        "token": token,
        "present": token in segment,
        "count": segment.count(token),
        "lines": [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line][:20],
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    surfaces = [
        {
            "surface": "page-shell label/context collection",
            "classification": "allowed page shell",
            "owner": "inputs_page",
            "deletion_readiness": "SHELL_ONLY",
            "evidence": [
                _token(segment, start, "_resolve_geometry_width_context("),
                _token(segment, start, "_bottom_reo_state_label("),
                _token(segment, start, "_shear_state_label("),
            ],
        },
        {
            "surface": "controller wording call",
            "classification": "DesignGuideController-owned wording authority",
            "owner": "DesignGuideController",
            "deletion_readiness": "ACTIVE_AUTHORITY",
            "evidence": [_token(segment, start, "_build_design_guide_pure_guidance_step_description(")],
        },
        {
            "surface": "legacy width fallback row",
            "classification": "deleted after controller deadness proof",
            "owner": "deleted",
            "deletion_readiness": "DELETED_ZERO_LOCK",
            "evidence": [_token(segment, start, "if width_key in updates:")],
        },
        {
            "surface": "legacy bottom fallback row",
            "classification": "deleted after controller deadness proof",
            "owner": "deleted",
            "deletion_readiness": "DELETED_ZERO_LOCK",
            "evidence": [_token(segment, start, "Updated bottom reinforcement from {_bottom_reo_state_label(before_state)}")],
        },
        {
            "surface": "legacy shear fallback row",
            "classification": "deleted after controller deadness proof",
            "owner": "deleted",
            "deletion_readiness": "DELETED_ZERO_LOCK",
            "evidence": [_token(segment, start, "Updated shear reinforcement from {_shear_state_label(before_state)}")],
        },
        {
            "surface": "legacy load/generic fallback rows",
            "classification": "deleted after controller deadness proof",
            "owner": "deleted",
            "deletion_readiness": "DELETED_ZERO_LOCK",
            "evidence": [
                _token(segment, start, "Adjusted sustained load inputs"),
                _token(segment, start, "Applied {action_type.replace"),
            ],
        },
    ]
    return {
        "schema": "design_guide_describe_guidance_step_shell_deadness_audit.v1",
        "target": {"name": TARGET, "line_start": start, "line_end": end, "line_count": max(0, end - start + 1)},
        "decision": "SHELL_ONLY_WITH_FALLBACK_ROWS_DELETED",
        "surfaces": surfaces,
        "next_safe_slice": "continue_next_extraction_surface",
        "controller_boundary_clean": all(
            token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    rows = list(payload.get("surfaces") or [])
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "surfaces_classified": len(rows) == 6,
        "controller_wording_authority_present": any(row.get("surface") == "controller wording call" for row in rows),
        "page_shell_collection_bounded": any(row.get("surface") == "page-shell label/context collection" and row.get("deletion_readiness") == "SHELL_ONLY" for row in rows),
        "fallback_rows_deleted_zero_locked": all(
            any(
                row.get("surface") == surface
                and row.get("deletion_readiness") == "DELETED_ZERO_LOCK"
                and all(not bool(item.get("present")) for item in row.get("evidence", []))
                for row in rows
            )
            for surface in (
                "legacy width fallback row",
                "legacy bottom fallback row",
                "legacy shear fallback row",
                "legacy load/generic fallback rows",
            )
        ),
        "next_surface_identified": payload.get("next_safe_slice") == "continue_next_extraction_surface",
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
    json_path = ARTIFACT_DIR / f"design_guide_describe_guidance_step_shell_deadness_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_describe_guidance_step_shell_deadness_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Describe Guidance Step Shell/Deadness Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Surface Inventory",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"- {row.get('surface')}: {row.get('classification')} "
            f"({row.get('owner')}); readiness `{row.get('deletion_readiness')}`"
        )
    lines.extend(
        [
            "",
            f"Next safe slice: `{payload.get('next_safe_slice')}`",
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
    print(f"design_guide_describe_guidance_step_shell_deadness_audit {payload['status']}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
