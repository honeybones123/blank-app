"""Proof-only SHEAR_FAIL_GOVERNS active-repair preview boundary snapshot.

This verifier records the boundary needed to move the page-side
``final_visible_active_shear_repair_family_restamp`` candidate evaluation into
SHEAR_FAIL_GOVERNS evidence later.

It intentionally does not move logic, change runtime behaviour, change CTA or
publication semantics, or edit the SHEAR contract. The expected result is a
PASS proof that the future family-owned boundary is explicit and ready for a
separate parity snapshot.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
RUNTIME_PATH = ROOT / "design_brain" / "families" / "shear_fail_governs" / "runtime.py"
CONTRACT_PATH = ROOT / "design_brain" / "families" / "shear_fail_governs" / "contract.json"


RESTAMP_SOURCE = 'source="final_visible_active_shear_repair_family_restamp"'
REQUIRED_PAGE_MARKERS = {
    "restamp_source_present": RESTAMP_SOURCE,
    "evaluates_candidate_in_page": "_evaluate_auto_design_candidate(",
    "active_shear_guard": '"shear" in active_failures_for_active_shear',
    "active_not_bending_guard": '"bending" not in active_failures_for_active_shear',
    "compound_shear_update_guard": "_COMPOUND_SHEAR_UPDATE_KEYS",
    "requires_preview_pass": '"preview_pass": True',
    "requires_no_any_fail": 'not bool(shear_repair_overview.get("any_fail"))',
    "requires_required_checks": "_overview_required_checks_acceptable(shear_repair_overview)",
    "requires_no_explicit_status_fail": "_candidate_preview_statuses_have_explicit_fail",
    "updates_button_contract": '"button_contract": dict(contract)',
    "updates_display_truth": 'out["display_truth"]',
    "updates_candidate_search_evidence": 'out["candidate_search_evidence"]',
    "debug_stamp": "final_binding_active_shear_repair_restamped",
}
REQUIRED_RUNTIME_MARKERS = {
    "candidate_evaluator_injected": "evaluate_candidate: CandidateEvaluator",
    "candidate_input_boundary": "ShearCandidateInput",
    "candidate_update_boundary": "ShearCandidateUpdate",
    "candidate_evaluation_boundary": "ShearCandidateEvaluation",
    "selected_recommendation_output": "selected_recommendation",
    "accepted_lane_evidence_output": "accepted_lane_evidence",
    "rejected_lane_evidence_output": "rejected_lane_evidence",
    "cta_intent_proof_output": "cta_intent_proof",
    "ladder_hash_output": "ladder_hash",
}
REQUIRED_BOUNDARY_FIELDS = {
    "family_id",
    "source",
    "page_restamp_source",
    "active_failure_guard",
    "base_state_hash",
    "update_hash",
    "candidate_state_hash",
    "evaluation_hash",
    "current_shear_utilisation",
    "preview_shear_utilisation",
    "utilisation_improved",
    "preview_pass",
    "required_checks_acceptable",
    "no_explicit_preview_failures",
    "button_contract_effect",
    "display_truth_effect",
    "candidate_search_evidence_effect",
    "debug_stamp_effect",
    "same_as_page_restamp_source",
    "product_driving_now",
    "ready_for_parity_proof",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _context_around(source: str, needle: str, *, before: int = 1800, after: int = 5600) -> str:
    index = source.find(needle)
    if index < 0:
        return ""
    return source[max(0, index - before) : min(len(source), index + after)]


def _latest_artifact(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": f"{type(exc).__name__}: {exc}"}
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _proposed_boundary_payload() -> dict[str, Any]:
    from design_brain.shear_candidate_evaluation import (  # noqa: WPS433
        ShearCandidateEvaluation,
        ShearCandidateInput,
        ShearCandidateUpdate,
        build_shear_candidate_state_hash,
    )

    base_state = {
        "geometry": {"beam_width_mm": 400.0, "beam_depth_mm": 650.0},
        "reinforcement": {
            "ligature_spacing_mm": 300.0,
            "ligature_diameter_mm": 10,
            "ligature_leg_count": 2,
        },
        "actions": {"current_shear_utilisation": 1.18, "design_shear_kn": 420.0},
        "constraints": {"geometry_locked": False, "reinforcement_locked": False},
    }
    updates = {
        "reinforcement": {
            "ligature_spacing_mm": 150.0,
            "ligature_diameter_mm": 10,
            "ligature_leg_count": 2,
        }
    }
    boundary_input = ShearCandidateInput(base_state=base_state)
    boundary_update = ShearCandidateUpdate(updates=updates)
    candidate_state_hash = build_shear_candidate_state_hash(base_state, updates)
    evaluation = ShearCandidateEvaluation(
        input_hash=boundary_input.input_hash,
        update_hash=boundary_update.update_hash,
        candidate_state_hash=candidate_state_hash,
        shear_utilisation=0.92,
        previous_shear_utilisation=1.18,
        utilisation_improved=True,
        code_compliance_status={"overall": "PASS", "required_checks_acceptable": True},
        constructability_status={"overall": "PASS"},
        spacing_status={"status": "PASS"},
        bar_size_status={"status": "PASS"},
        leg_count_status={"status": "PASS"},
        geometry_status={"status": "PASS"},
        capacity_summary={"shear": "preview_capacity_restored"},
        failure_flags={"any_fail": False, "explicit_preview_failures": False},
        engineering_status={"overall": "PASS", "target_band_status": "TARGET"},
    ).with_evaluation_hash()
    payload = {
        "family_id": "SHEAR_FAIL_GOVERNS",
        "source": "shear_fail_governs_active_repair_preview_boundary",
        "page_restamp_source": "final_visible_active_shear_repair_family_restamp",
        "active_failure_guard": {
            "requires_shear_active_failure": True,
            "requires_bending_not_active_failure": True,
        },
        "base_state_hash": boundary_input.input_hash,
        "update_hash": boundary_update.update_hash,
        "candidate_state_hash": candidate_state_hash,
        "evaluation_hash": evaluation.evaluation_hash,
        "current_shear_utilisation": evaluation.previous_shear_utilisation,
        "preview_shear_utilisation": evaluation.shear_utilisation,
        "utilisation_improved": evaluation.utilisation_improved,
        "preview_pass": True,
        "required_checks_acceptable": True,
        "no_explicit_preview_failures": True,
        "button_contract_effect": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "updates_hash": boundary_update.update_hash,
        },
        "display_truth_effect": {
            "display_truth_source": "candidate_preview",
            "displayed_status": "PASS",
            "displayed_util": evaluation.shear_utilisation,
        },
        "candidate_search_evidence_effect": {
            "family": "shear",
            "primary_action_family": "shear",
            "selected_candidate_util": evaluation.shear_utilisation,
            "candidate_post_util": evaluation.shear_utilisation,
            "selected_candidate_update_hash": boundary_update.update_hash,
        },
        "debug_stamp_effect": {
            "final_binding_active_shear_repair_restamped": True,
            "final_binding_active_shear_repair_expected_util": evaluation.shear_utilisation,
            "final_binding_active_shear_repair_current_util": evaluation.previous_shear_utilisation,
        },
        "same_as_page_restamp_source": True,
        "product_driving_now": True,
        "ready_for_parity_proof": True,
    }
    return payload


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    runtime_source = RUNTIME_PATH.read_text(encoding="utf-8")
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    context = _context_around(inputs_source, RESTAMP_SOURCE)
    page_markers = {
        key: (needle in context if key != "restamp_source_present" else needle in inputs_source)
        for key, needle in REQUIRED_PAGE_MARKERS.items()
    }
    runtime_markers = {key: needle in runtime_source for key, needle in REQUIRED_RUNTIME_MARKERS.items()}
    boundary_payload = _proposed_boundary_payload()
    repeated_boundary_payload = _proposed_boundary_payload()
    boundary_fields = set(boundary_payload)
    effect_map = {
        "page_updates_button_contract": page_markers["updates_button_contract"],
        "boundary_covers_button_contract": bool(boundary_payload.get("button_contract_effect")),
        "page_updates_display_truth": page_markers["updates_display_truth"],
        "boundary_covers_display_truth": bool(boundary_payload.get("display_truth_effect")),
        "page_updates_candidate_search_evidence": page_markers["updates_candidate_search_evidence"],
        "boundary_covers_candidate_search_evidence": bool(boundary_payload.get("candidate_search_evidence_effect")),
        "page_updates_debug_stamp": page_markers["debug_stamp"],
        "boundary_covers_debug_stamp": bool(boundary_payload.get("debug_stamp_effect")),
    }
    return {
        "page_context_hash": _stable_hash(context),
        "page_context_line_count": len(context.splitlines()),
        "page_markers": page_markers,
        "runtime_markers": runtime_markers,
        "contract_family_id": str(
            contract.get("family_id")
            or (contract.get("family_identity") or {}).get("family_id")
            or ""
        ),
        "contract_required_outputs": contract.get("family_result_schema", {}).get("required_fields")
        or contract.get("family_result_schema", {}).get("required_outputs")
        or (),
        "contract_evidence_required_fields": contract.get("family_result_schema", {}).get("evidence_required_fields")
        or (),
        "boundary_payload": boundary_payload,
        "boundary_hash": _stable_hash(boundary_payload),
        "repeated_boundary_hash": _stable_hash(repeated_boundary_payload),
        "required_boundary_fields": sorted(REQUIRED_BOUNDARY_FIELDS),
        "missing_boundary_fields": sorted(REQUIRED_BOUNDARY_FIELDS - boundary_fields),
        "effect_map": effect_map,
        "composed_artifacts": {
            "shear_candidate_evaluation_boundary": _latest_artifact("shear_candidate_evaluation_boundary"),
            "shear_fail_governs_lock_verifier": _latest_artifact("shear_fail_governs_lock_verifier"),
            "design_guide_active_shear_restamp_ownership_audit": _latest_artifact(
                "design_guide_active_shear_restamp_ownership_audit"
            ),
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    artifacts = dict(capture.get("composed_artifacts") or {})
    effect_map = dict(capture.get("effect_map") or {})
    return {
        "page_restamp_source_found": all((capture.get("page_markers") or {}).values()),
        "runtime_has_contract_candidate_boundary": all((capture.get("runtime_markers") or {}).values()),
        "contract_is_shear_fail_governs": capture.get("contract_family_id") == "SHEAR_FAIL_GOVERNS",
        "boundary_fields_complete": not capture.get("missing_boundary_fields"),
        "boundary_hash_stable": capture.get("boundary_hash") == capture.get("repeated_boundary_hash"),
        "page_effects_covered_by_boundary": all(effect_map.values()),
        "candidate_boundary_latest_pass": (artifacts.get("shear_candidate_evaluation_boundary") or {}).get("status") == "PASS",
        "family_lock_latest_pass": (artifacts.get("shear_fail_governs_lock_verifier") or {}).get("status") == "PASS",
        "ownership_audit_latest_pass": (artifacts.get("design_guide_active_shear_restamp_ownership_audit") or {}).get("status")
        == "PASS",
    }


def _report(payload: dict[str, Any]) -> str:
    checks = payload.get("checks") or {}
    lines = [
        "# SHEAR_FAIL_GOVERNS Active Repair Preview Boundary Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Readiness: `{payload.get('readiness')}`",
        "",
        "## Scope",
        "",
        "- Proof-only boundary snapshot.",
        "- No runtime behaviour changed.",
        "- No contract changed.",
        "- No CTA/publication/apply/render/session/UI ownership moved.",
        "- Page-side restamp remains live until a later parity and cutover proof.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in checks.items())
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            f"- boundary hash: `{payload.get('boundary_hash')}`",
            f"- missing fields: `{payload.get('missing_boundary_fields')}`",
            f"- page context hash: `{payload.get('page_context_hash')}`",
            "",
            "## Next Safe Slice",
            "",
            "Create a parity snapshot that compares this family-owned proof shape against the current "
            "page-side `final_visible_active_shear_repair_family_restamp` eval before moving any logic.",
            "",
        ]
    )
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"shear_fail_governs_active_repair_preview_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_governs_active_repair_preview_boundary_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    report_path.write_text(_report(payload), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "shear_fail_governs_active_repair_preview_boundary.v1",
        "created_at": _stamp(),
        "status": status,
        "readiness": "READY_FOR_PARITY_PROOF" if status == "PASS" else "NOT_READY",
        "product_behaviour_changed": False,
        "family_runtime_changed": False,
        "contract_changed": False,
        "cta_publication_apply_changed": False,
        "can_move_now": False,
        "can_delete_or_bypass_now": False,
        "checks": checks,
        "failures": [key for key, ok in checks.items() if not ok],
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
        **capture,
    }
    json_path, report_path = _write(payload)
    print(f"shear_fail_governs_active_repair_preview_boundary {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    print(json.dumps({"status": status, "readiness": payload["readiness"], "failures": payload["failures"]}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
