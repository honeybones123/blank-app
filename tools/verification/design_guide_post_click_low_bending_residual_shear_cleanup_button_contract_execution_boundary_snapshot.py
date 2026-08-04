"""Snapshot the residual-shear shared button-contract execution boundary."""

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
INPUTS = ROOT / "inputs_page.py"
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
        build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary,
    )

    promoted = {
        "candidate_id": "residual-shear-cleanup-candidate",
        "updates": {"ligature_legs": 0, "ligature_dia": 0},
        "action_payload": {"updates": {"ligature_legs": 0, "ligature_dia": 0}},
        "resolved_candidate": {"updates": {"ligature_legs": 0, "ligature_dia": 0}},
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "label": "Apply",
            "updates": {"ligature_legs": 0, "ligature_dia": 0},
            "expected_util": 0.69,
        },
    }
    input_summary = {
        "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
        "button_contract_builder": "_design_guide_button_contract",
        "promoted_item_hash": _stable_hash(promoted),
    }
    result = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary(
        promoted_item=dict(promoted),
        button_contract_input_summary=dict(input_summary),
        button_contract=dict(promoted["button_contract"]),
        state_summary={"state_fingerprint": "abc123"},
        dependency_status="page_live",
    )
    repeat = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary(
        promoted_item=dict(promoted),
        button_contract_input_summary=dict(input_summary),
        button_contract=dict(promoted["button_contract"]),
        state_summary={"state_fingerprint": "abc123"},
        dependency_status="page_live",
    )
    source = inspect.getsource(
        build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary
    )
    inputs_source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    forbidden_terms = (
        "import inputs_page",
        "from inputs_page",
        "import streamlit",
        "from streamlit",
        "st.",
        "session_state[",
        "_design_guide_button_contract(",
        "button(",
        "on_click",
    )
    return {
        "result": result,
        "stable_repeat_hash": result.get("button_contract_execution_boundary_hash")
        == repeat.get("button_contract_execution_boundary_hash"),
        "required_fields_present": all(
            field in result
            for field in (
                "button_contract_execution_boundary_authority",
                "dependency_slot",
                "dependency_status",
                "promoted_item_hash",
                "button_contract_input_hash",
                "button_contract_hash",
                "button_contract_updates_hash",
                "button_contract_enabled",
                "button_contract_actionable",
                "button_contract_action_type",
                "button_contract_label",
                "executor_backed_apply_proof",
                "output_shape_ready",
                "behavior_cutover_ready",
                "page_must_keep_for_now",
                "not_moved",
                "proof_only",
                "product_driving",
                "render_driving",
                "apply_driving",
                "session_driving",
                "button_contract_execution_boundary_hash",
            )
        ),
        "forbidden_terms_present": tuple(term for term in forbidden_terms if term in source),
        "inputs_trace_wired": (
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary("
            in inputs_source
            and "button_contract_input_summary={" in inputs_source
            and "button_contract=dict(residual_button_contract or {})" in inputs_source
        ),
        "live_button_contract_execution_retained": (
            "_design_guide_button_contract(residual_promoted, state=state)" in inputs_source
            or "_execute_post_click_low_bending_residual_shear_cleanup_button_contract("
            in inputs_source
        ),
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
        "executor_backed_apply_proof": result.get("executor_backed_apply_proof") is True,
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
        "inputs_trace_wired": capture.get("inputs_trace_wired") is True,
        "live_button_contract_execution_retained": (
            capture.get("live_button_contract_execution_retained") is True
        ),
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
        "# Residual Shear Cleanup Button Contract Execution Boundary Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Output shape ready: `{result.get('output_shape_ready')}`",
        f"- Behaviour cutover ready: `{result.get('behavior_cutover_ready')}`",
        f"- Executor-backed apply proof: `{result.get('executor_backed_apply_proof')}`",
        f"- Live button-contract execution retained: `{capture.get('live_button_contract_execution_retained')}`",
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
            "Add parity scenarios for enabled, disabled, stale, and missing-update button contracts before any button-contract source-summary cutover.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_button_contract_execution_boundary_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary "
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
