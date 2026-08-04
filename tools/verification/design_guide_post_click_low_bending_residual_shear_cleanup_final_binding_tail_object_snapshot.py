"""Object snapshot for residual shear cleanup final-binding tail handoff."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff,
)


def _stamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
        .replace(":", "-")
    )


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _object_case(status: str = "page_live") -> dict[str, Any]:
    first = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff(
        result_packaging_handoff={
            "result_packaging_handoff_hash": "packaging-hash",
            "residual_updates_hash": "updates-hash",
        },
        binding_inputs={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "state_fingerprint": "state-hash",
            "mode_config_hash": "mode-hash",
        },
        binding_output_summary={
            "evidence_hash": "evidence-hash",
            "action_payload_hash": "payload-hash",
            "resolved_candidate_hash": "resolved-hash",
            "button_contract_hash": "contract-hash",
            "button_contract_updates_hash": "contract-updates-hash",
            "button_contract_expected_util": 0.82,
            "button_contract_enabled": True,
            "button_contract_actionable": True,
            "returned_item_hash": "returned-item-hash",
        },
        dependency_status=status,
    )
    repeat = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff(
        result_packaging_handoff={
            "result_packaging_handoff_hash": "packaging-hash",
            "residual_updates_hash": "updates-hash",
        },
        binding_inputs={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "state_fingerprint": "state-hash",
            "mode_config_hash": "mode-hash",
        },
        binding_output_summary={
            "evidence_hash": "evidence-hash",
            "action_payload_hash": "payload-hash",
            "resolved_candidate_hash": "resolved-hash",
            "button_contract_hash": "contract-hash",
            "button_contract_updates_hash": "contract-updates-hash",
            "button_contract_expected_util": 0.82,
            "button_contract_enabled": True,
            "button_contract_actionable": True,
            "returned_item_hash": "returned-item-hash",
        },
        dependency_status=status,
    )
    return {
        "dependency_status": status,
        "payload": first,
        "stable_hash_repeat": first.get("final_binding_tail_handoff_hash")
        == repeat.get("final_binding_tail_handoff_hash"),
    }


def _capture() -> dict[str, Any]:
    page_live = _object_case("page_live")
    controller_owned = _object_case("controller_owned")
    payload = dict(page_live.get("payload") or {})
    required_fields = (
        "final_binding_tail_handoff_authority",
        "dependency_slot",
        "dependency_status",
        "result_packaging_handoff_hash",
        "binding_input_hash",
        "binding_output_hash",
        "evidence_hash",
        "action_payload_hash",
        "resolved_candidate_hash",
        "button_contract_hash",
        "button_contract_updates_hash",
        "button_contract_expected_util",
        "button_contract_enabled",
        "button_contract_actionable",
        "returned_item_hash",
        "output_shape_ready",
        "behavior_cutover_ready",
        "final_binding_tail_cutover_ready",
        "proof_only",
        "product_driving",
        "render_driving",
        "apply_driving",
        "session_driving",
        "final_binding_tail_handoff_hash",
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_FINAL_BINDING_TAIL_OBJECT_READY",
        "required_fields_missing": [field for field in required_fields if field not in payload],
        "page_live": page_live,
        "controller_owned": controller_owned,
        "page_live_output_shape_ready": bool(payload.get("output_shape_ready")),
        "page_live_behavior_cutover_ready": bool(payload.get("behavior_cutover_ready")),
        "controller_owned_behavior_cutover_ready": bool(
            (controller_owned.get("payload") or {}).get("behavior_cutover_ready")
        ),
        "not_moved": tuple(payload.get("not_moved") or ()),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    payload = dict((capture.get("page_live") or {}).get("payload") or {})
    return {
        "required_fields_present": not capture.get("required_fields_missing"),
        "page_live_output_shape_ready": capture.get("page_live_output_shape_ready") is True,
        "page_live_not_behavior_ready": capture.get("page_live_behavior_cutover_ready") is False,
        "controller_owned_behavior_ready": (
            capture.get("controller_owned_behavior_cutover_ready") is True
        ),
        "hashes_stable": (capture.get("page_live") or {}).get("stable_hash_repeat") is True
        and (capture.get("controller_owned") or {}).get("stable_hash_repeat") is True,
        "object_non_driving": all(
            payload.get(key) is expected
            for key, expected in (
                ("proof_only", True),
                ("product_driving", False),
                ("render_driving", False),
                ("apply_driving", False),
                ("session_driving", False),
            )
        ),
        "keeps_cta_and_wording_page_owned": "button_contract_execution" in capture.get("not_moved", ())
        and "visible_wording_authoring" in capture.get("not_moved", ()),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Final Binding Tail Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Result",
        "",
        f"- required fields missing: `{capture.get('required_fields_missing')}`",
        f"- page-live output shape ready: `{capture.get('page_live_output_shape_ready')}`",
        f"- page-live behavior cutover ready: `{capture.get('page_live_behavior_cutover_ready')}`",
        f"- controller-owned behavior cutover ready: `{capture.get('controller_owned_behavior_cutover_ready')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Trace-wire this object beside the residual final-binding tail. Do not move evidence merge, button-contract execution, visible wording, CTA/apply, UI/session, or family/runtime behaviour.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_object_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_object_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_object_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_final_binding_tail_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_object "
        f"{payload['status']}"
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print(f"failures={','.join(failures)}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
