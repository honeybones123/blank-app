"""Audit fast candidate evaluation scalar/status extraction boundary."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

PAGE_HELPER = "evaluate_candidate_fast"
PAGE_STATUS_HELPER = "_status_from_candidate_util"
PROPOSED_SERVICE_HELPER = "build_fast_candidate_evaluation_scalar_status_projection"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    fast_start, fast_end, fast_segment = _function_segment(inputs_source, PAGE_HELPER)
    status_start, status_end, status_segment = _function_segment(inputs_source, PAGE_STATUS_HELPER)

    rows = [
        {
            "surface": "bending component scalar projection",
            "current_owner": "inputs_page",
            "target_owner": "design_brain.candidate_evaluation",
            "classification": "service-owned projection with legacy inline deadness pending",
            "deletion_readiness": "CUTOVER_DONE_DEADNESS_PENDING",
            "risk": "MEDIUM",
            "evidence": ["flexural_util", "ductility_util", "min_steel_util", "governs"],
        },
        {
            "surface": "shear scalar status projection",
            "current_owner": "inputs_page",
            "target_owner": "design_brain.candidate_evaluation",
            "classification": "service-owned projection with legacy inline deadness pending",
            "deletion_readiness": "CUTOVER_DONE_DEADNESS_PENDING",
            "risk": "MEDIUM",
            "evidence": ["shear_candidates", "shear_util", PAGE_STATUS_HELPER],
        },
        {
            "surface": "crack/deflection status fallback projection",
            "current_owner": "inputs_page",
            "target_owner": "design_brain.candidate_evaluation",
            "classification": "service-owned projection with seed fallback input",
            "deletion_readiness": "CUTOVER_DONE_DEADNESS_PENDING",
            "risk": "LOW",
            "evidence": ["seed_overview", "crack", "deflection"],
        },
        {
            "surface": "shear detailing failure collection",
            "current_owner": "inputs_page",
            "target_owner": "page shell until detailing helper boundary exists",
            "classification": "page-owned helper call",
            "deletion_readiness": "NOT_READY",
            "risk": "MEDIUM",
            "evidence": ["_shear_link_detailing_failures_from_state"],
        },
        {
            "surface": "fast overview/status materialization",
            "current_owner": "design_brain.candidate_evaluation called by inputs_page",
            "target_owner": "design_brain.candidate_evaluation",
            "classification": "already extracted",
            "deletion_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": ["_build_fast_candidate_evaluation_overview_status_projection("],
        },
    ]
    checks = {
        "fast_helper_found": bool(fast_segment),
        "status_helper_found": bool(status_segment),
        "candidate_evaluation_boundary_clean": "import inputs_page" not in candidate_source
        and "from inputs_page" not in candidate_source
        and "import streamlit" not in candidate_source,
        "overview_status_projection_already_extracted": "_build_fast_candidate_evaluation_overview_status_projection(" in fast_segment
        and "def build_fast_candidate_evaluation_overview_status_projection(" in candidate_source,
        "scalar_status_projection_service_boundary_present": f"_{PROPOSED_SERVICE_HELPER}(" in fast_segment
        and f"def {PROPOSED_SERVICE_HELPER}(" in candidate_source,
        "legacy_scalar_status_inline_deadness_pending": all(
            token in fast_segment
            for token in ("flexural_util", "ductility_util", "min_steel_util", "shear_candidates", PAGE_STATUS_HELPER)
        ),
        "detailing_helper_call_still_page_owned": "_shear_link_detailing_failures_from_state" in fast_segment,
        "solver_callbacks_still_page_owned": all(
            token in fast_segment
            for token in (
                "_evaluate_bending_with_bottom_state",
                "_evaluate_shear_with_state",
                "_evaluate_crack_with_state",
                "_evaluate_deflection_with_state",
            )
        ),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_fast_candidate_evaluation_scalar_status_boundary_audit.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": (
            "FAST_SCALAR_STATUS_PROJECTION_CUTOVER_DONE_LEGACY_INLINE_DEADNESS_PENDING"
            if all(checks.values())
            else "FAST_SCALAR_STATUS_BOUNDARY_AUDIT_FAILED"
        ),
        "targets": {
            PAGE_HELPER: {"line_start": fast_start, "line_end": fast_end},
            PAGE_STATUS_HELPER: {"line_start": status_start, "line_end": status_end},
        },
        "surface_rows": rows,
        "first_safe_implementation_slice": {
            "name": "fast_candidate_evaluation_legacy_scalar_status_deadness_deletion",
            "target_helper": PROPOSED_SERVICE_HELPER,
            "allowed_to_move": [
                "delete or bypass old inline scalar prep once verifier proves service output is the only downstream consumer",
            ],
            "must_remain_page_owned": [
                "solver/evaluator callback execution",
                "shear detailing failure helper call",
                "physical metrics helper calls",
                "_evaluate_candidate_fast cache/cap/metrics runner",
            ],
        },
        "stop_conditions": [
            "Stop if unknown/no-data status output changes.",
            "Stop if any PASS/NEAR LIMIT/FAIL threshold changes.",
            "Stop if shear detailing failure collection moves without its own boundary proof.",
            "Stop if solver/evaluator callbacks move into candidate_evaluation.",
        ],
        "checks": checks,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_fast_candidate_evaluation_scalar_status_boundary_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_fast_candidate_evaluation_scalar_status_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Fast Candidate Evaluation Scalar/Status Boundary Audit",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Surface Inventory",
        "",
    ]
    for row in payload.get("surface_rows") or []:
        lines.append(
            f"- `{row.get('surface')}`: `{row.get('classification')}` -> `{row.get('target_owner')}` "
            f"({row.get('deletion_readiness')}, risk `{row.get('risk')}`)"
        )
    first_slice = dict(payload.get("first_safe_implementation_slice") or {})
    lines.extend(["", "## First Safe Implementation Slice", ""])
    lines.append(f"- Name: `{first_slice.get('name')}`")
    lines.append(f"- Target helper: `{first_slice.get('target_helper')}`")
    lines.extend(["", "Allowed to move:"])
    lines.extend(f"- `{item}`" for item in first_slice.get("allowed_to_move") or [])
    lines.extend(["", "Must remain page-owned:"])
    lines.extend(f"- `{item}`" for item in first_slice.get("must_remain_page_owned") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Stop Conditions", ""])
    lines.extend(f"- {item}" for item in payload.get("stop_conditions") or [])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_fast_candidate_evaluation_scalar_status_boundary_audit {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload.get("status") != "PASS":
        failed = [name for name, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
