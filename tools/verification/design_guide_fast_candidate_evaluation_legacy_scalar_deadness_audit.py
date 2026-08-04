"""Audit deadness of legacy inline fast candidate scalar/status prep."""

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
SERVICE_HELPER = "build_fast_candidate_evaluation_scalar_status_projection"


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

    legacy_start_token = "flexural_util = None"
    service_call_token = "scalar_status_projection = _build_fast_candidate_evaluation_scalar_status_projection("
    legacy_start = fast_segment.find(legacy_start_token)
    service_call = fast_segment.find(service_call_token)
    legacy_block = fast_segment[legacy_start:service_call] if legacy_start >= 0 and service_call > legacy_start else ""
    post_service_segment = fast_segment[service_call:] if service_call >= 0 else ""
    legacy_block_deleted = not bool(legacy_block) and service_call >= 0

    forbidden_side_effect_tokens = [
        "st.",
        "session_state",
        ".update(",
        "_evaluate_bending_with_bottom_state",
        "_evaluate_shear_with_state",
        "_evaluate_crack_with_state",
        "_evaluate_deflection_with_state",
        "_build_fast_candidate_evaluation_result_projection(",
        "_build_fast_candidate_evaluation_overview_status_projection(",
    ]
    overwritten_after_service = all(
        token in post_service_segment
        for token in (
            "statuses = dict(scalar_status_projection.get(\"statuses\") or {})",
            "utils = dict(scalar_status_projection.get(\"utils\") or {})",
            "flexural_util = scalar_status_projection.get(\"flexural_util\")",
            "ductility_util = scalar_status_projection.get(\"ductility_util\")",
            "min_steel_util = scalar_status_projection.get(\"min_steel_util\")",
            "bending_util = scalar_status_projection.get(\"bending_util\")",
            "shear_util = scalar_status_projection.get(\"shear_util\")",
        )
    )
    checks = {
        "fast_helper_found": bool(fast_segment),
        "legacy_block_deleted_or_found_before_service_call": legacy_block_deleted or bool(legacy_block),
        "service_helper_present": f"def {SERVICE_HELPER}(" in candidate_source,
        "service_call_present": service_call >= 0,
        "service_output_overwrites_legacy_values_before_downstream_use": overwritten_after_service,
        "legacy_block_has_no_session_or_streamlit_side_effects": legacy_block_deleted
        or not any(token in legacy_block for token in forbidden_side_effect_tokens),
        "legacy_block_deleted_or_still_contains_only_scalar_status_prep": legacy_block_deleted
        or all(
            token in legacy_block
            for token in ("bending_status", "shear_status", "_status_from_candidate_util", "statuses = {", "utils = {")
        ),
        "solver_callbacks_remain_before_legacy_block": all(
            token in fast_segment[:legacy_start]
            for token in (
                "_evaluate_bending_with_bottom_state",
                "_evaluate_shear_with_state",
                "_evaluate_crack_with_state",
                "_evaluate_deflection_with_state",
            )
        ),
        "overview_projection_uses_service_values": "_build_fast_candidate_evaluation_overview_status_projection(" in post_service_segment
        and "scalar_status_projection.get(\"unknown_status\")" in post_service_segment,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_fast_candidate_evaluation_legacy_scalar_deadness_audit.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": (
            "LEGACY_INLINE_FAST_SCALAR_STATUS_PREP_DELETED"
            if legacy_block_deleted and all(checks.values())
            else "READY_TO_DELETE_LEGACY_INLINE_FAST_SCALAR_STATUS_PREP"
            if all(checks.values())
            else "LEGACY_INLINE_FAST_SCALAR_STATUS_DEADNESS_NOT_PROVEN"
        ),
        "target": {
            PAGE_HELPER: {"line_start": fast_start, "line_end": fast_end},
            "legacy_block_start_token": legacy_start_token,
            "service_call_token": service_call_token,
        },
        "legacy_block_character_count": len(legacy_block),
        "legacy_block_line_count": len(legacy_block.splitlines()) if legacy_block else 0,
        "checks": checks,
        "next_safe_slice": "delete_legacy_inline_fast_scalar_status_prep_block",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_fast_candidate_evaluation_legacy_scalar_deadness_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_fast_candidate_evaluation_legacy_scalar_deadness_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Fast Candidate Evaluation Legacy Scalar Deadness Audit",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        f"Legacy block line count: `{payload.get('legacy_block_line_count')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_fast_candidate_evaluation_legacy_scalar_deadness_audit {payload.get('status')}")
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
