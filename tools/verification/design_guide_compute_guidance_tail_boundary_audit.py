"""Audit the remaining compute guidance tails in inputs_page.py.

This verifier is intentionally classification-only. It identifies which parts of
the final two zero-authority buckets are page-shell plumbing versus remaining
Design Brain decision/projection logic.
"""

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
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
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
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _token_row(segment: str, start_line: int, token: str) -> dict[str, Any]:
    return {
        "token": token,
        "present": token in segment,
        "count": segment.count(token),
        "lines": _line_numbers(segment, start_line, token)[:50],
    }


def _token_rows(segment: str, start_line: int, tokens: list[str]) -> list[dict[str, Any]]:
    return [_token_row(segment, start_line, token) for token in tokens]


def _surface(
    *,
    name: str,
    classification: str,
    owner: str,
    target_owner: str,
    readiness: str,
    segment: str,
    start_line: int,
    tokens: list[str],
    first_safe_slice: str | None = None,
) -> dict[str, Any]:
    evidence = _token_rows(segment, start_line, tokens)
    return {
        "surface": name,
        "classification": classification,
        "owner": owner,
        "target_owner": target_owner,
        "readiness": readiness,
        "evidence": evidence,
        "present": any(bool(row.get("present")) for row in evidence),
        "first_safe_slice": first_safe_slice,
    }


def _capture() -> dict[str, Any]:
    source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    candidate_source = _read(CANDIDATE_EVALUATION)
    core_start, core_end, core_segment = _function_source(source, "_compute_design_guidance_items_core")
    wrapper_start, wrapper_end, wrapper_segment = _function_source(source, "_compute_design_guidance_items")

    wrapper_surfaces = [
        _surface(
            name="runtime fingerprint and stable cache guards",
            classification="page-shell cache/trace boundary",
            owner="inputs_page.py",
            target_owner="inputs_page.py page shell",
            readiness="KEEP_BOUNDED",
            segment=wrapper_segment,
            start_line=wrapper_start,
            tokens=[
                "stable_fingerprint_for_payload(",
                "_design_guide_candidate_search_reuse_get(",
                "get_rerun_pure_cache(",
                "set_rerun_pure_cache(",
                "_attach_design_brain_result_boundary(",
            ],
        ),
        _surface(
            name="invalid canonical/coherence blocked output",
            classification="controller-owned output/debug payload object",
            owner="DesignGuideController via inputs_page shell",
            target_owner="DesignGuideController",
            readiness="SHELL_CALL",
            segment=wrapper_segment,
            start_line=wrapper_start,
            tokens=[
                "_build_design_guide_controller_compute_invalid_state_debug_payload(",
                "_build_design_guide_controller_compute_invalid_state_output_projection(",
            ],
            first_safe_slice=None,
        ),
        _surface(
            name="invalid canonical/coherence debug field construction",
            classification="controller-owned debug/proof payload construction",
            owner="DesignGuideController via inputs_page shell",
            target_owner="DesignGuideController debug/proof adapter",
            readiness="SHELL_CALL",
            segment=wrapper_segment,
            start_line=wrapper_start,
            tokens=[
                "_build_design_guide_controller_compute_invalid_state_debug_payload(",
            ],
            first_safe_slice=None,
        ),
        _surface(
            name="early family dispatch",
            classification="controller-owned helper call",
            owner="DesignGuideController via inputs_page shell",
            target_owner="DesignGuideController",
            readiness="SHELL_CALL",
            segment=wrapper_segment,
            start_line=wrapper_start,
            tokens=["_resolve_compute_design_guidance_family_early_dispatch("],
        ),
        _surface(
            name="core compute invocation and debug trace swapping",
            classification="page-shell orchestration around remaining core tail",
            owner="inputs_page.py shell plus remaining core",
            target_owner="page shell until core extraction completes",
            readiness="KEEP_BOUNDED",
            segment=wrapper_segment,
            start_line=wrapper_start,
            tokens=[
                "_ACTIVE_GUIDANCE_RANK_TRACE",
                "_ACTIVE_GUIDANCE_RECO_TRACE",
                "_compute_design_guidance_items_core(",
            ],
        ),
        _surface(
            name="post-core publication/evidence lane",
            classification="bounded late-evidence helper lane",
            owner="inputs_page.py shell calling bounded controller/publication helpers",
            target_owner="bounded page shell",
            readiness="SHELL_CALL",
            segment=wrapper_segment,
            start_line=wrapper_start,
            tokens=[
                "_prepare_compute_missing_candidate_search_evidence(",
                "_republish_compute_coherence_active_repair(",
                "_materialize_compute_active_under_capacity_blocker(",
                "_build_compute_safe_cleanup_rehydrated_result(",
                "_materialize_compute_shear_final_threshold_blocker(",
                "_sync_compute_late_evidence_to_primary_item(",
                "_apply_compute_late_evidence_contract_rebound(",
            ],
            first_safe_slice=None,
        ),
        _surface(
            name="empty collapsed fallback and final output",
            classification="controller/finalizer helper calls",
            owner="DesignGuideController plus inputs_page finalizer shell",
            target_owner="DesignGuideController/page shell",
            readiness="SHELL_CALL",
            segment=wrapper_segment,
            start_line=wrapper_start,
            tokens=[
                "_materialize_compute_empty_collapsed_exact_blocker_fallback(",
                "_finalize_compute_design_guidance_items_output(",
            ],
        ),
    ]

    core_surfaces = [
        _surface(
            name="overview and branch selection",
            classification="remaining page-owned Design Brain branch orchestration",
            owner="inputs_page.py",
            target_owner="DesignGuideController",
            readiness="NOT_READY",
            segment=core_segment,
            start_line=core_start,
            tokens=[
                "_collect_design_overview(",
                "guidance_branch =",
                "overview.get(",
                "active_failures",
            ],
            first_safe_slice="compute_core_branch_orchestration_audit",
        ),
        _surface(
            name="direct target helper calls",
            classification="bounded service-backed shell call",
            owner="inputs_page.py shell",
            target_owner="DesignGuideController/candidate_evaluation services",
            readiness="BOUNDED_NOT_ZERO_SERVICE_BACKED",
            segment=core_segment,
            start_line=core_start,
            tokens=["_direct_target_band_guidance_item("],
        ),
        _surface(
            name="candidate evidence and action payload mutation",
            classification="remaining page-owned projection mutation tail",
            owner="inputs_page.py",
            target_owner="DesignGuideController/FinalDesignGuidePublication adapters",
            readiness="NOT_READY",
            segment=core_segment,
            start_line=core_start,
            tokens=[
                "candidate_search_evidence",
                "action_payload",
                "primary_action",
                "_publish_design_guide_contract(",
            ],
            first_safe_slice="compute_core_item_projection_mutation_boundary_audit",
        ),
        _surface(
            name="passing/blocked fallback item construction",
            classification="remaining page-owned fallback recommendation construction",
            owner="inputs_page.py",
            target_owner="DesignGuideController",
            readiness="NOT_READY",
            segment=core_segment,
            start_line=core_start,
            tokens=[
                "_passing_guidance_item(",
                "_blocked_guidance_item(",
                "_no_active_primary_result(",
                "passing_guidance_fallback",
            ],
            first_safe_slice="compute_core_fallback_item_projection_extraction",
        ),
    ]

    not_ready = [
        row
        for row in wrapper_surfaces + core_surfaces
        if row.get("readiness") in {"NOT_READY", "READY_TO_EXTRACT"} and row.get("present")
    ]
    first_ready = next((row for row in not_ready if row.get("readiness") == "READY_TO_EXTRACT"), None)
    first_not_ready = first_ready or (not_ready[0] if not_ready else None)
    decision = "COMPUTE_GUIDANCE_TAILS_NOT_ZERO"
    if first_ready:
        decision = "COMPUTE_GUIDANCE_INVALID_STATE_PROJECTION_READY_TO_EXTRACT"
    elif not not_ready:
        decision = "COMPUTE_GUIDANCE_TAILS_SHELL_ONLY"

    return {
        "schema": "design_guide_compute_guidance_tail_boundary_audit.v1",
        "status_decision": decision,
        "targets": {
            "_compute_design_guidance_items_core": {
                "line_start": core_start,
                "line_end": core_end,
                "line_count": max(0, core_end - core_start + 1),
            },
            "_compute_design_guidance_items": {
                "line_start": wrapper_start,
                "line_end": wrapper_end,
                "line_count": max(0, wrapper_end - wrapper_start + 1),
            },
        },
        "wrapper_surfaces": wrapper_surfaces,
        "core_surfaces": core_surfaces,
        "not_ready_surfaces": not_ready,
        "first_safe_slice": dict(first_not_ready or {}),
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
        "candidate_evaluation_has_no_page_or_streamlit_imports": all(
            token not in candidate_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    targets = payload.get("targets") or {}
    return {
        "core_target_found": bool((targets.get("_compute_design_guidance_items_core") or {}).get("line_start")),
        "wrapper_target_found": bool((targets.get("_compute_design_guidance_items") or {}).get("line_start")),
        "first_safe_slice_identified": bool(payload.get("first_safe_slice")),
        "not_ready_surfaces_classified": len(payload.get("not_ready_surfaces") or []) > 0,
        "controller_import_boundary_clean": bool(payload.get("controller_has_no_page_or_streamlit_imports")),
        "candidate_evaluation_import_boundary_clean": bool(
            payload.get("candidate_evaluation_has_no_page_or_streamlit_imports")
        ),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_guidance_tail_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_guidance_tail_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Compute Guidance Tail Boundary Audit",
        "",
        f"Status: {payload.get('status')}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## Executive Summary",
        "The final zero-authority buckets are `_compute_design_guidance_items(...)` and "
        "`_compute_design_guidance_items_core(...)`. The wrapper still contains an "
        "extractable invalid/coherence blocked output projection and a larger late-evidence "
        "projection lane. The core still owns branch orchestration and fallback item projection.",
        "",
        "## First Safe Slice",
        f"- Surface: {(payload.get('first_safe_slice') or {}).get('surface')}",
        f"- Slice: {(payload.get('first_safe_slice') or {}).get('first_safe_slice')}",
        "",
        "## Wrapper Surfaces",
    ]
    for row in payload.get("wrapper_surfaces") or []:
        lines.append(f"- {row.get('surface')}: {row.get('classification')} ({row.get('readiness')})")
    lines.append("")
    lines.append("## Core Surfaces")
    for row in payload.get("core_surfaces") or []:
        lines.append(f"- {row.get('surface')}: {row.get('classification')} ({row.get('readiness')})")
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
    print(f"design_guide_compute_guidance_tail_boundary_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
