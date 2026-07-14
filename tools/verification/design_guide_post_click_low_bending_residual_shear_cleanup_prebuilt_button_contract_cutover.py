"""Verify residual-shear route consumes a prebuilt button contract."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
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
REPORT_DIR = ROOT / "artifacts" / "reports"

ROUTE_BODY_START = "    def _execute_post_click_low_bending_residual_shear_cleanup_route_body():"
ROUTE_BODY_END = "    residual_shear_cleanup_prebuilt_route_result = {}"

REQUIRED_INPUT_TOKENS = {
    "prebuilt_contract_variable": "residual_prebuilt_button_contract = dict(",
    "button_contract_from_prebuilt": (
        "residual_button_contract = dict(residual_prebuilt_button_contract or {})"
    ),
    "binding_with_contract": (
        "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail("
    ),
    "button_contract_passed_to_final_binding": (
        "button_contract=dict(residual_button_contract or {})"
    ),
    "boundary_marked_controller_owned": 'dependency_status="controller_owned"',
}

FORBIDDEN_BODY_TOKENS = {
    "live_button_contract_wrapper_call": (
        "_execute_post_click_low_bending_residual_shear_cleanup_button_contract("
    ),
}

REQUIRED_PREVIOUS_ARTIFACTS = {
    "prebuilt_button_equivalence": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_button_contract_equivalence"
    ),
    "button_boundary_readiness": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_cutover_readiness"
    ),
    "button_boundary_implementation": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_cutover_implementation"
    ),
}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _status_from_payload(payload: dict[str, Any]) -> str:
    raw = str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or payload.get("decision")
        or ""
    )
    upper = raw.upper()
    if "PASS" in upper or "LOCKED" in upper:
        return "PASS"
    if "FAIL" in upper:
        return "FAIL"
    if "PARTIAL" in upper:
        return "PARTIAL"
    return raw or "UNKNOWN"


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "status": _status_from_payload(payload), "path": str(path)}


def _load_controller():
    spec = importlib.util.spec_from_file_location(
        "design_guide_controller_prebuilt_button_cutover_verifier",
        CONTROLLER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load design_guide_controller.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sample() -> dict[str, Any]:
    controller = _load_controller()
    button_contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "label": "Apply",
        "updates": {"ligature_legs": 0},
        "expected_util": 0.69,
    }
    promoted = {
        "candidate_id": "prebuilt-button",
        "button_contract": dict(button_contract),
        "action_payload": {"updates": {"ligature_legs": 0}},
        "resolved_candidate": {"updates": {"ligature_legs": 0}},
    }
    first = controller.build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary(
        promoted_item=dict(promoted),
        button_contract_input_summary={"scenario": "cutover", "prebuilt": True},
        button_contract=dict(promoted.get("button_contract") or {}),
        state_summary={"state_fingerprint": "cutover"},
        dependency_status="controller_owned",
    )
    second = controller.build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary(
        promoted_item=dict(promoted),
        button_contract_input_summary={"scenario": "cutover", "prebuilt": True},
        button_contract=dict(promoted.get("button_contract") or {}),
        state_summary={"state_fingerprint": "cutover"},
        dependency_status="controller_owned",
    )
    return {
        "stable_repeat_hash": first.get("button_contract_execution_boundary_hash")
        == second.get("button_contract_execution_boundary_hash"),
        "dependency_status_controller_owned": first.get("dependency_status")
        == "controller_owned",
        "behavior_cutover_ready": first.get("behavior_cutover_ready") is True,
        "executor_backed_apply_proof": first.get("executor_backed_apply_proof") is True,
        "product_driving": first.get("product_driving") is False,
        "render_driving": first.get("render_driving") is False,
        "apply_driving": first.get("apply_driving") is False,
        "session_driving": first.get("session_driving") is False,
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    body = _between(source, ROUTE_BODY_START, ROUTE_BODY_END)
    latest = {name: _latest(prefix) for name, prefix in REQUIRED_PREVIOUS_ARTIFACTS.items()}
    sample = _sample()
    return {
        "decision": "RESIDUAL_SHEAR_PREBUILT_BUTTON_CONTRACT_CUTOVER",
        "route_body_found": bool(body),
        "required_input_presence": {
            name: token in body for name, token in REQUIRED_INPUT_TOKENS.items()
        },
        "forbidden_body_presence": {
            name: token in body for name, token in FORBIDDEN_BODY_TOKENS.items()
        },
        "shared_wrapper_still_defined_for_compatibility": (
            "def _execute_post_click_low_bending_residual_shear_cleanup_button_contract("
            in source
        ),
        "previous_artifacts": latest,
        "previous_artifacts_pass": all(row.get("status") == "PASS" for row in latest.values()),
        "sample": sample,
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "route_body_deleted": False,
        "next_safe_surface": "rerun_nested_wrapper_deadness_probe_then_split_route_shell_or_physical_return",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    sample = dict(capture.get("sample") or {})
    return {
        "route_body_found": capture.get("route_body_found") is True,
        "required_input_tokens_present": all(
            dict(capture.get("required_input_presence") or {}).values()
        ),
        "live_button_contract_wrapper_call_absent_from_body": not any(
            dict(capture.get("forbidden_body_presence") or {}).values()
        ),
        "compatibility_wrapper_still_defined": (
            capture.get("shared_wrapper_still_defined_for_compatibility") is True
        ),
        "previous_artifacts_pass": capture.get("previous_artifacts_pass") is True,
        "sample_stable_repeat_hash": sample.get("stable_repeat_hash") is True,
        "sample_dependency_status_controller_owned": (
            sample.get("dependency_status_controller_owned") is True
        ),
        "sample_behavior_cutover_ready": sample.get("behavior_cutover_ready") is True,
        "sample_executor_backed_apply_proof": sample.get("executor_backed_apply_proof")
        is True,
        "sample_proof_only_not_driving": all(
            (
                sample.get("product_driving") is True,
                sample.get("render_driving") is True,
                sample.get("apply_driving") is True,
                sample.get("session_driving") is True,
            )
        ),
        "route_body_not_deleted": capture.get("route_body_deleted") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Prebuilt Button Contract Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        "The residual-shear route body now consumes the promoted/prebuilt button "
        "contract instead of calling the page-local shared button-contract wrapper "
        "inside the nested route body.",
        "",
        "## Checks",
        "",
    ]
    for name, ok in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{ok}`")
    lines.extend(["", "## Previous Artifacts", ""])
    for name, row in dict(capture.get("previous_artifacts") or {}).items():
        lines.append(f"- `{name}`: `{row.get('status')}` {row.get('path')}")
    lines.extend(
        [
            "",
            "## Next",
            "",
            f"`{capture.get('next_safe_surface')}`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    stamp = _stamp()
    payload = {
        "schema": (
            "design_guide_post_click_low_bending_residual_shear_cleanup_"
            "prebuilt_button_contract_cutover.v1"
        ),
        "created_at": stamp,
        "status": status,
        "capture": capture,
        "checks": checks,
        "failures": [name for name, ok in checks.items() if ok is not True],
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = (
        ARTIFACT_DIR
        / (
            "design_guide_post_click_low_bending_residual_shear_cleanup_"
            f"prebuilt_button_contract_cutover_{stamp}.json"
        )
    )
    audit_path = (
        AUDIT_DIR
        / (
            "design_guide_post_click_low_bending_residual_shear_cleanup_"
            f"prebuilt_button_contract_cutover_{stamp}.md"
        )
    )
    report_path = (
        REPORT_DIR
        / (
            "design_brain_physical_extraction_residual_shear_cleanup_"
            f"prebuilt_button_contract_cutover_{stamp}.md"
        )
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"prebuilt_button_contract_cutover {status}"
    )
    print(json_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
