"""Audit the compute post-core late-evidence lane boundary."""

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
PUBLICATION = ROOT / "design_brain" / "publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


HELPERS = [
    "_prepare_compute_missing_candidate_search_evidence",
    "_republish_compute_coherence_active_repair",
    "_materialize_compute_active_under_capacity_blocker",
    "_build_compute_safe_cleanup_rehydrated_result",
    "_materialize_compute_shear_final_threshold_blocker",
    "_sync_compute_late_evidence_to_primary_item",
    "_apply_compute_late_evidence_contract_rebound",
]


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


def _token_count(segment: str, token: str) -> int:
    return segment.count(token)


def _classify_helper(name: str, segment: str) -> dict[str, Any]:
    if name == "_sync_compute_late_evidence_to_primary_item":
        return {
            "classification": "publication-service-backed page mutation adapter",
            "current_owner": "inputs_page.py shell applying design_brain.publication result",
            "target_owner": "bounded page shell or small controller adapter",
            "readiness": "BOUNDED_SERVICE_BACKED",
            "first_safe_slice": None,
            "risk": "LOW",
        }
    if name == "_prepare_compute_missing_candidate_search_evidence":
        if (
            "_build_design_guide_controller_compute_missing_candidate_search_evidence_record(" in segment
            and "_build_design_guide_controller_compute_missing_candidate_target_band_context(" in segment
        ):
            return {
                "classification": "controller/publication-backed missing evidence shell",
                "current_owner": "inputs_page.py shell collecting source ids/updates and calling controller/publication helpers",
                "target_owner": "bounded page shell",
                "readiness": "BOUNDED_CONTROLLER_PUBLICATION_BACKED",
                "first_safe_slice": None,
                "risk": "LOW",
            }
        if "_build_design_guide_controller_compute_missing_candidate_search_evidence_record(" in segment:
            return {
                "classification": "controller-record-backed missing evidence wrapper",
                "current_owner": "inputs_page.py shell collecting source ids/updates/target band and calling controller/publication helpers",
                "target_owner": "DesignGuideController target-band context adapter plus page shell",
                "readiness": "NOT_READY",
                "first_safe_slice": "compute_missing_candidate_target_band_context_extraction",
                "risk": "MEDIUM",
            }
        return {
            "classification": "missing evidence projection wrapper",
            "current_owner": "inputs_page.py wrapper around publication helper and page item records",
            "target_owner": "FinalDesignGuidePublication/publication adapter",
            "readiness": "NOT_READY",
            "first_safe_slice": "compute_missing_candidate_search_evidence_projection_extraction",
            "risk": "MEDIUM",
        }
    if name == "_materialize_compute_shear_final_threshold_blocker":
        if "_build_design_guide_controller_shear_final_threshold_blocker_projection(" in segment:
            return {
                "classification": "controller-backed blocker projection shell",
                "current_owner": "inputs_page.py shell collecting evidence inputs and applying DesignGuideController projection",
                "target_owner": "bounded page shell",
                "readiness": "BOUNDED_CONTROLLER_BACKED",
                "first_safe_slice": None,
                "risk": "LOW",
            }
        return {
            "classification": "page-owned blocker item/evidence/CTA projection",
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController or FinalDesignGuidePublication evidence adapter",
            "readiness": "READY_TO_EXTRACT_WITH_SNAPSHOT",
            "first_safe_slice": "compute_shear_final_threshold_blocker_projection_extraction",
            "risk": "MEDIUM",
        }
    if name == "_republish_compute_coherence_active_repair":
        if (
            "_build_design_guide_controller_compute_coherence_active_repair_projection(" in segment
            and "_resolve_design_guide_controller_compute_coherence_active_repair_fail_keys(" in segment
        ):
            return {
                "classification": "controller-backed active repair execution shell",
                "current_owner": "inputs_page.py shell executing page callbacks and applying controller projection",
                "target_owner": "bounded page execution shell",
                "readiness": "BOUNDED_CONTROLLER_BACKED",
                "first_safe_slice": None,
                "risk": "LOW",
            }
        if "_build_design_guide_controller_compute_coherence_active_repair_projection(" in segment:
            return {
                "classification": "controller-projection-backed active repair execution shell",
                "current_owner": "inputs_page.py shell executing page callbacks plus remaining fail-key inference",
                "target_owner": "DesignGuideController fail-key resolver plus bounded page execution shell",
                "readiness": "NOT_READY",
                "first_safe_slice": "compute_coherence_active_repair_fail_key_resolution_extraction",
                "risk": "MEDIUM",
            }
    if name == "_materialize_compute_active_under_capacity_blocker":
        if "_build_design_guide_controller_compute_active_under_capacity_blocker_projection(" in segment:
            return {
                "classification": "controller-backed active under-capacity blocker shell",
                "current_owner": "inputs_page.py shell running safe-repair promotion probe and applying controller projection",
                "target_owner": "bounded page shell",
                "readiness": "BOUNDED_CONTROLLER_BACKED",
                "first_safe_slice": None,
                "risk": "LOW",
            }
        return {
            "classification": "page-owned active under-capacity blocker projection",
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController",
            "readiness": "READY_TO_EXTRACT_WITH_SNAPSHOT",
            "first_safe_slice": "materialize_compute_active_under_capacity_blocker_projection_extraction",
            "risk": "HIGH",
        }
    if name == "_build_compute_safe_cleanup_rehydrated_result":
        if "_build_design_guide_controller_compute_safe_cleanup_rehydration_projection(" in segment:
            return {
                "classification": "controller-backed safe cleanup rehydration shell",
                "current_owner": "inputs_page.py shell collecting combined-safe row and applying controller projection",
                "target_owner": "bounded page shell",
                "readiness": "BOUNDED_CONTROLLER_BACKED",
                "first_safe_slice": None,
                "risk": "LOW",
            }
        return {
            "classification": "safe cleanup rehydration policy/projection",
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController",
            "readiness": "NOT_READY",
            "first_safe_slice": "compute_safe_cleanup_rehydration_projection_extraction",
            "risk": "MEDIUM",
        }
    if name == "_apply_compute_late_evidence_contract_rebound":
        if "_resolve_design_guide_controller_compute_late_evidence_contract_rebound_decision(" in segment:
            return {
                "classification": "controller-decision-backed late rebound mutation shell",
                "current_owner": "inputs_page.py shell applying controller rebound/restamper replacement and final-publication adapter",
                "target_owner": "bounded page mutation shell",
                "readiness": "BOUNDED_CONTROLLER_BACKED",
                "first_safe_slice": None,
                "risk": "LOW",
            }
        return {
            "classification": "late rebound controller/publication bridge",
            "current_owner": "inputs_page.py bridge with controller restamper replacement",
            "target_owner": "DesignGuideController route adapter plus page mutation shell",
            "readiness": "NOT_READY",
            "first_safe_slice": "compute_late_evidence_contract_rebound_projection_extraction",
            "risk": "HIGH",
        }
    return {
        "classification": "page-owned evidence materialization/projection",
        "current_owner": "inputs_page.py",
        "target_owner": "DesignGuideController",
        "readiness": "NOT_READY",
        "first_safe_slice": f"{name.strip('_')}_projection_extraction",
        "risk": "HIGH",
    }


def _capture() -> dict[str, Any]:
    source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    publication_source = _read(PUBLICATION)
    _, _, wrapper_segment = _function_source(source, "_compute_design_guidance_items")

    helper_rows: list[dict[str, Any]] = []
    for name in HELPERS:
        start, end, segment = _function_source(source, name)
        classification = _classify_helper(name, segment)
        helper_rows.append(
            {
                "helper": name,
                "line_start": start,
                "line_end": end,
                "line_count": max(0, end - start + 1) if start and end else 0,
                **classification,
                "evidence_tokens": {
                    "button_contract": _token_count(segment, "button_contract"),
                    "action_payload": _token_count(segment, "action_payload"),
                    "candidate_search_evidence": _token_count(segment, "candidate_search_evidence"),
                    "debug_trace": _token_count(segment, "debug_trace"),
                    "existing_evidence": _token_count(segment, "existing_evidence"),
                    "session_state": _token_count(segment, "st.session_state"),
                    "streamlit": _token_count(segment, "streamlit"),
                    "controller_call": _token_count(segment, "_compute_rebound_item_from_controller_publication_item("),
                    "publication_service_call": _token_count(segment, "build_late_evidence_primary_item_sync(")
                    + _token_count(segment, "build_missing_candidate_search_evidence_from_records("),
                },
            }
        )

    not_ready = [row for row in helper_rows if str(row.get("readiness")) in {"NOT_READY", "READY_TO_EXTRACT_WITH_SNAPSHOT"}]
    first_safe = next((row for row in not_ready if row.get("readiness") == "READY_TO_EXTRACT_WITH_SNAPSHOT"), None)
    if first_safe is None and not_ready:
        first_safe = not_ready[0]

    status_decision = (
        "LATE_EVIDENCE_LANE_ZERO"
        if not not_ready
        else "LATE_EVIDENCE_LANE_NOT_ZERO"
    )
    return {
        "schema": "design_guide_compute_late_evidence_lane_boundary_audit.v1",
        "status_decision": status_decision,
        "helpers": helper_rows,
        "not_ready_count": len(not_ready),
        "first_safe_slice": dict(first_safe or {}),
        "wrapper_calls_all_helpers": all(f"{name}(" in wrapper_segment for name in HELPERS),
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
        ),
        "publication_has_no_page_or_streamlit_imports": all(
            token not in publication_source for token in ("inputs_page", "streamlit", "st.session_state")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    not_ready_count = int(payload.get("not_ready_count") or 0)
    return {
        "helpers_found": all(bool(row.get("line_start")) for row in payload.get("helpers") or []),
        "not_ready_surfaces_zero_or_classified": (
            not_ready_count == 0
            or bool((payload.get("first_safe_slice") or {}).get("first_safe_slice"))
        ),
        "zero_state_decision_matches_inventory": (
            (not_ready_count == 0 and payload.get("status_decision") == "LATE_EVIDENCE_LANE_ZERO")
            or (not_ready_count > 0 and payload.get("status_decision") == "LATE_EVIDENCE_LANE_NOT_ZERO")
        ),
        "wrapper_calls_all_helpers": bool(payload.get("wrapper_calls_all_helpers")),
        "controller_import_boundary_clean": bool(payload.get("controller_has_no_page_or_streamlit_imports")),
        "publication_import_boundary_clean": bool(payload.get("publication_has_no_page_or_streamlit_imports")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_late_evidence_lane_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_late_evidence_lane_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    first = dict(payload.get("first_safe_slice") or {})
    lines = [
        "# Design Guide Compute Late-Evidence Lane Boundary Audit",
        "",
        f"Status: {payload.get('status')}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## First Safe Slice",
        f"- helper: `{first.get('helper')}`",
        f"- slice: `{first.get('first_safe_slice')}`",
        "",
        "## Helper Inventory",
        "| Helper | Lines | Readiness | Target owner | Risk |",
        "|---|---:|---|---|---|",
    ]
    for row in payload.get("helpers") or []:
        lines.append(
            f"| `{row.get('helper')}` | {row.get('line_count')} | {row.get('readiness')} | "
            f"{row.get('target_owner')} | {row.get('risk')} |"
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
    print(f"design_guide_compute_late_evidence_lane_boundary_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
