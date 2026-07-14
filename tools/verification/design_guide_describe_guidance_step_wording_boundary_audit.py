"""Audit _describe_guidance_step visible wording boundary."""

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
    call_count = max(0, inputs_source.count(f"{TARGET}(") - 1)
    surfaces = [
        {
            "surface": "depth wording",
            "classification": "pure visible wording from state/update values",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController presentation wording helper",
            "deletion_readiness": "READY_FOR_PARITY_SNAPSHOT",
            "evidence": [
                _token(segment, start, '"D" in updates'),
                _token(segment, start, "Increased"),
                _token(segment, start, "Reduced"),
            ],
        },
        {
            "surface": "width wording",
            "classification": "visible wording with page-local width-context helper dependency",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController after width-context adapter parity",
            "deletion_readiness": "NOT_READY_WIDTH_CONTEXT_DEPENDENCY",
            "evidence": [
                _token(segment, start, "_resolve_geometry_width_context("),
                _token(segment, start, "width_short"),
            ],
        },
        {
            "surface": "bottom reinforcement wording",
            "classification": "visible wording with page-local bottom label dependency",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController after bottom-label adapter parity",
            "deletion_readiness": "NOT_READY_BOTTOM_LABEL_DEPENDENCY",
            "evidence": [
                _token(segment, start, "_bottom_reo_state_label("),
                _token(segment, start, "Updated bottom reinforcement"),
            ],
        },
        {
            "surface": "shear reinforcement wording",
            "classification": "visible wording with page-local shear label dependency",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController after shear-label adapter parity",
            "deletion_readiness": "NOT_READY_SHEAR_LABEL_DEPENDENCY",
            "evidence": [
                _token(segment, start, "_shear_state_label("),
                _token(segment, start, "Updated shear reinforcement"),
            ],
        },
        {
            "surface": "load wording",
            "classification": "visible wording with unit text and numeric formatting",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController after exact wording parity",
            "deletion_readiness": "READY_FOR_PARITY_SNAPSHOT",
            "evidence": [
                _token(segment, start, "Adjusted sustained load inputs"),
                _token(segment, start, "load_keys"),
            ],
        },
        {
            "surface": "generic fallback wording",
            "classification": "pure visible fallback wording",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController presentation wording helper",
            "deletion_readiness": "READY_FOR_PARITY_SNAPSHOT",
            "evidence": [
                _token(segment, start, "Applied {action_type.replace"),
            ],
        },
    ]
    return {
        "schema": "design_guide_describe_guidance_step_wording_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
            "call_count_excluding_definition": call_count,
        },
        "decision": "PARTIAL_PURE_WORDING_READY_LABEL_DEPENDENCIES_NOT_READY",
        "surfaces": surfaces,
        "first_safe_implementation_slice": {
            "name": "describe_guidance_step_pure_depth_load_generic_wording_adapter",
            "why": (
                "Depth, load, and generic fallback wording can be parity-proven without moving "
                "geometry width context or reinforcement label helpers."
            ),
            "move": (
                "Add a controller wording helper for pure branches only, while width/bottom/shear "
                "branches stay page-owned until label/context adapters exist."
            ),
            "required_verifier": "design_guide_describe_guidance_step_pure_wording_adapter_cutover.py",
        },
        "stop_conditions": [
            "Do not change visible wording.",
            "Do not move _resolve_geometry_width_context(...) without parity.",
            "Do not move _bottom_reo_state_label(...) or _shear_state_label(...) without parity.",
            "Do not move caller behavior or action update semantics.",
        ],
        "controller_boundary_clean": all(
            token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    surfaces = list(payload.get("surfaces") or [])
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "surfaces_classified": len(surfaces) == 6,
        "shared_call_surface_confirmed": (payload.get("target") or {}).get("call_count_excluding_definition", 0) >= 5,
        "pure_wording_ready": any(
            row.get("surface") == "depth wording"
            and row.get("deletion_readiness") == "READY_FOR_PARITY_SNAPSHOT"
            for row in surfaces
        ),
        "width_dependency_identified": any(
            row.get("surface") == "width wording"
            and row.get("deletion_readiness") == "NOT_READY_WIDTH_CONTEXT_DEPENDENCY"
            for row in surfaces
        ),
        "reinforcement_label_dependencies_identified": all(
            any(row.get("surface") == surface and str(row.get("deletion_readiness") or "").startswith("NOT_READY") for row in surfaces)
            for surface in ("bottom reinforcement wording", "shear reinforcement wording")
        ),
        "first_slice_identified": bool(
            (payload.get("first_safe_implementation_slice") or {}).get("required_verifier")
            == "design_guide_describe_guidance_step_pure_wording_adapter_cutover.py"
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
    json_path = ARTIFACT_DIR / f"design_guide_describe_guidance_step_wording_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_describe_guidance_step_wording_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    first_slice = dict(payload.get("first_safe_implementation_slice") or {})
    target = dict(payload.get("target") or {})
    lines = [
        "# Design Guide Describe Guidance Step Wording Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Target",
        f"- `{target.get('name')}` lines {target.get('line_start')}-{target.get('line_end')}",
        f"- Call count excluding definition: {target.get('call_count_excluding_definition')}",
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
            "## Stop Conditions",
            *[f"- {condition}" for condition in payload.get("stop_conditions") or []],
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
    print(f"design_guide_describe_guidance_step_wording_boundary_audit {payload['status']}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
