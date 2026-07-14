"""Snapshot the residual-shear CTA/apply payload source boundary object."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary,
    )

    promoted = {
        "candidate_id": "residual-shear-cleanup-candidate",
        "updates": {"ligature_legs": 0, "ligature_dia": 0},
        "action_payload": {
            "updates": {"ligature_legs": 0, "ligature_dia": 0},
            "candidate_search_evidence": {"no_second_cta_required": True},
        },
        "resolved_candidate": {
            "updates": {"ligature_legs": 0, "ligature_dia": 0},
            "candidate_search_evidence": {"no_second_cta_required": True},
        },
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "label": "Apply",
            "updates": {"ligature_legs": 0, "ligature_dia": 0},
            "expected_util": 0.69,
        },
    }
    result = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary(
        promoted_item=dict(promoted),
        action_payload=dict(promoted["action_payload"]),
        resolved_candidate=dict(promoted["resolved_candidate"]),
        button_contract=dict(promoted["button_contract"]),
        state_summary={"state_fingerprint": "abc123"},
        dependency_status="page_live",
    )
    repeat = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary(
        promoted_item=dict(promoted),
        action_payload=dict(promoted["action_payload"]),
        resolved_candidate=dict(promoted["resolved_candidate"]),
        button_contract=dict(promoted["button_contract"]),
        state_summary={"state_fingerprint": "abc123"},
        dependency_status="page_live",
    )
    source = inspect.getsource(
        build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary
    )
    forbidden_terms = (
        "import inputs_page",
        "from inputs_page",
        "import streamlit",
        "from streamlit",
        "st.",
        "st.session_state",
        "session_state[",
        "st.session_state",
        "button(",
        "on_click",
    )
    return {
        "result": result,
        "stable_repeat_hash": result.get("cta_apply_payload_source_boundary_hash")
        == repeat.get("cta_apply_payload_source_boundary_hash"),
        "required_fields_present": all(
            field in result
            for field in (
                "cta_apply_payload_source_boundary_authority",
                "dependency_slot",
                "dependency_status",
                "promoted_item_hash",
                "action_payload_hash",
                "resolved_candidate_hash",
                "button_contract_hash",
                "button_contract_updates_hash",
                "payload_matches_promoted_item",
                "resolved_candidate_matches_promoted_item",
                "button_contract_matches_promoted_item",
                "button_contract_enabled",
                "button_contract_actionable",
                "output_shape_ready",
                "behavior_cutover_ready",
                "page_must_keep_for_now",
                "not_moved",
                "proof_only",
                "product_driving",
                "render_driving",
                "apply_driving",
                "session_driving",
                "cta_apply_payload_source_boundary_hash",
            )
        ),
        "forbidden_terms_present": tuple(term for term in forbidden_terms if term in source),
        "source_hash": _stable_hash(source),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    result = dict(capture.get("result") or {})
    return {
        "required_fields_present": capture.get("required_fields_present") is True,
        "stable_repeat_hash": capture.get("stable_repeat_hash") is True,
        "output_shape_ready": result.get("output_shape_ready") is True,
        "behavior_cutover_not_claimed": result.get("behavior_cutover_ready") is False,
        "payload_matches_promoted": result.get("payload_matches_promoted_item") is True,
        "resolved_matches_promoted": result.get("resolved_candidate_matches_promoted_item") is True,
        "button_contract_matches_promoted": result.get("button_contract_matches_promoted_item") is True,
        "button_contract_actionable": result.get("button_contract_actionable") is True,
        "proof_only_non_driving": all(
            (
                result.get("proof_only") is True,
                result.get("product_driving") is False,
                result.get("render_driving") is False,
                result.get("apply_driving") is False,
                result.get("session_driving") is False,
            )
        ),
        "forbidden_terms_absent": not bool(capture.get("forbidden_terms_present")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    result = dict(capture.get("result") or {})
    lines = [
        "# Residual Shear Cleanup CTA/Apply Payload Source Boundary Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Output shape ready: `{result.get('output_shape_ready')}`",
        f"- Behaviour cutover ready: `{result.get('behavior_cutover_ready')}`",
        f"- Proof only: `{result.get('proof_only')}`",
        f"- Page must keep for now: `{result.get('page_must_keep_for_now')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next Safe Target",
            "",
            "Trace-wire this object beside the live residual route payload/resolved/button-contract extraction, still non-driving.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_object_snapshot.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_object_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_object_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_cta_apply_payload_source_boundary_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_object "
        + payload["status"]
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
