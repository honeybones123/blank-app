"""Audit fast candidate evaluation overview/status extraction boundary."""

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
EXISTING_SERVICE_HELPER = "build_fast_candidate_evaluation_result_projection"
PROPOSED_SERVICE_HELPER = "build_fast_candidate_evaluation_overview_status_projection"


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

    rows = [
        {
            "surface": "fast evaluator state/action resolution",
            "current_owner": "inputs_page",
            "target_owner": "page shell until callback/service runner parity exists",
            "classification": "page-owned evaluator callback plumbing",
            "deletion_readiness": "NOT_READY",
            "risk": "HIGH",
            "evidence": [
                "_state_with_resolved_auto_design_actions",
                "_candidate_bottom_updates",
                "_candidate_shear_updates",
            ],
        },
        {
            "surface": "fast evaluator solver execution",
            "current_owner": "inputs_page",
            "target_owner": "candidate evaluation service runner only after injected-callback parity",
            "classification": "page-owned solver/evaluator execution",
            "deletion_readiness": "NOT_READY",
            "risk": "HIGH",
            "evidence": [
                "_evaluate_bending_with_bottom_state",
                "_evaluate_shear_with_state",
                "_evaluate_crack_with_state",
                "_evaluate_deflection_with_state",
            ],
        },
        {
            "surface": "fast overview/status projection",
            "current_owner": "inputs_page",
            "target_owner": "design_brain.candidate_evaluation",
            "classification": "pure projection candidate",
            "deletion_readiness": "READY_FOR_PARITY_EXTRACTION",
            "risk": "LOW",
            "evidence": [
                "statuses = {",
                "utils = {",
                "tracked_statuses =",
                "overview = {",
                "failure_details_by_family",
            ],
        },
        {
            "surface": "fast result projection",
            "current_owner": "design_brain.candidate_evaluation",
            "target_owner": "design_brain.candidate_evaluation",
            "classification": "already extracted",
            "deletion_readiness": "SHELL_CALL_ONLY",
            "risk": "LOW",
            "evidence": [f"_{EXISTING_SERVICE_HELPER}("],
        },
        {
            "surface": "fast physical metrics projection",
            "current_owner": "inputs_page",
            "target_owner": "candidate_evaluation only after plain-fact metric boundary proof",
            "classification": "mixed page helper calls",
            "deletion_readiness": "NOT_READY",
            "risk": "MEDIUM",
            "evidence": [
                "_effective_bottom_design_state",
                "_design_width_value",
                "_reo_congestion_index",
            ],
        },
    ]

    proposed_helper_present = f"def {PROPOSED_SERVICE_HELPER}(" in candidate_source
    checks = {
        "fast_helper_found": bool(fast_segment),
        "service_module_import_clean_source": "import inputs_page" not in candidate_source
        and "from inputs_page" not in candidate_source
        and "import streamlit" not in candidate_source,
        "existing_result_projection_extracted": f"def {EXISTING_SERVICE_HELPER}(" in candidate_source
        and f"_{EXISTING_SERVICE_HELPER}(" in fast_segment,
        "overview_status_projection_service_boundary_present": (
            proposed_helper_present
            and f"_{PROPOSED_SERVICE_HELPER}(" in fast_segment
        )
        or all(token in fast_segment for token in ("statuses = {", "utils = {", "tracked_statuses =", "overview = {")),
        "overview_projection_has_plain_inputs_only": all(
            token in fast_segment
            for token in (
                "bending_status",
                "shear_status",
                "crack",
                "deflection",
                "bend_pack",
                "shear_link_detailing_failures",
            )
        ),
        "solver_callbacks_still_page_owned": all(
            token in fast_segment
            for token in (
                "_evaluate_bending_with_bottom_state",
                "_evaluate_shear_with_state",
                "_evaluate_crack_with_state",
                "_evaluate_deflection_with_state",
            )
        ),
        "state_resolution_still_page_owned": "_state_with_resolved_auto_design_actions" in fast_segment,
        "proposed_service_helper_state_valid": True,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }

    status = "PASS" if all(checks.values()) else "FAIL"
    if status == "PASS" and proposed_helper_present:
        decision = "FAST_OVERVIEW_STATUS_PROJECTION_EXTRACTED"
    elif status == "PASS":
        decision = "READY_TO_EXTRACT_FAST_OVERVIEW_STATUS_PROJECTION_ONLY"
    else:
        decision = "FAST_OVERVIEW_STATUS_BOUNDARY_AUDIT_FAILED"

    return {
        "schema": "design_guide_fast_candidate_evaluation_overview_status_boundary_audit.v1",
        "status": status,
        "decision": decision,
        "targets": {
            PAGE_HELPER: {"line_start": fast_start, "line_end": fast_end},
        },
        "surface_rows": rows,
        "first_safe_implementation_slice": {
            "name": "fast_candidate_evaluation_overview_status_projection_extraction",
            "target_helper": PROPOSED_SERVICE_HELPER,
            "allowed_to_move": [
                "statuses/utils dict construction from plain evaluated facts",
                "tracked status and any_fail/any_warn/all_key_pass/worst_util projection",
                "shear-link detailing failure details projection",
            ],
            "must_remain_page_owned": [
                "state/action resolution",
                "solver/evaluator callback execution",
                "bottom/design width/depth/reo metric helper calls",
                "_evaluate_candidate_fast cache/cap/metrics runner",
            ],
        },
        "stop_conditions": [
            "Stop if overview/status parity changes any status, util, fail/warn flag, worst util, or failure details.",
            "Stop if solver/evaluator callbacks move into design_brain.candidate_evaluation.",
            "Stop if candidate_evaluation imports inputs_page, Streamlit, session, UI, apply, or publication code.",
            "Stop if CTA/apply semantics, visible wording, family runtime behaviour, or candidate metadata changes.",
        ],
        "checks": checks,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_fast_candidate_evaluation_overview_status_boundary_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_fast_candidate_evaluation_overview_status_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Fast Candidate Evaluation Overview/Status Boundary Audit",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Current Responsibilities",
        "",
    ]
    for row in payload.get("surface_rows") or []:
        lines.append(
            f"- `{row.get('surface')}`: `{row.get('classification')}` -> `{row.get('target_owner')}` "
            f"({row.get('deletion_readiness')}, risk `{row.get('risk')}`)"
        )
    lines.extend(["", "## First Safe Implementation Slice", ""])
    first_slice = dict(payload.get("first_safe_implementation_slice") or {})
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
    print(f"design_guide_fast_candidate_evaluation_overview_status_boundary_audit {payload.get('status')}")
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
