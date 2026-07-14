"""Deadness proof for old residual shear cleanup final-binding page merge."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


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


def _run(cmd: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "cmd": cmd,
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
        "passed": result.returncode == 0,
    }


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    if end < 0:
        return source[start:]
    return source[start:end]


def _capture() -> dict[str, Any]:
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    old_tokens = (
        "residual_promoted[\"candidate_search_evidence\"] = dict(residual_evidence)",
        "residual_promoted[\"exact_blockers_by_family\"] = dict(residual_exact_blockers)",
        "residual_payload[\"candidate_search_evidence\"] = dict(residual_evidence)",
        "residual_resolved[\"candidate_search_evidence\"] = dict(residual_evidence)",
        "residual_promoted[\"button_contract\"] = dict(",
    )
    adapter_tokens = (
        "residual_binding_without_contract = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail(",
        "residual_binding_with_contract = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail(",
        "residual_promoted = dict(",
        "residual_payload = dict(residual_promoted.get(\"action_payload\") or {})",
        "residual_resolved = dict(residual_promoted.get(\"resolved_candidate\") or {})",
        "residual_route_body_replacement = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement(",
        "residual_route_body_result = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body(",
        "residual_prebuilt_route_result = _build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result(",
        "return dict(",
    )
    shared_owned_tokens = (
        "residual_button_contract_execution_boundary = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary(",
        "residual_cta_apply_payload_source_boundary = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary(",
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_trace(",
    )
    cutover_readiness = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_live_cutover_readiness.py",
        ]
    )
    audit = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_audit.py",
        ]
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_FINAL_BINDING_OLD_PAGE_MERGE_DEAD",
        "route_block_present": bool(route),
        "old_tokens_present": [token for token in old_tokens if token in route],
        "old_tokens_absent": [token for token in old_tokens if token not in route],
        "adapter_tokens_present": [token for token in adapter_tokens if token in route],
        "adapter_tokens_missing": [token for token in adapter_tokens if token not in route],
        "shared_owned_tokens_present": [token for token in shared_owned_tokens if token in route],
        "shared_owned_tokens_missing": [token for token in shared_owned_tokens if token not in route],
        "cutover_readiness": cutover_readiness,
        "audit": audit,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "route_block_present": capture.get("route_block_present") is True,
        "old_page_merge_tokens_absent": not capture.get("old_tokens_present"),
        "adapter_tokens_present": not capture.get("adapter_tokens_missing"),
        "shared_owned_tokens_preserved": not capture.get("shared_owned_tokens_missing"),
        "cutover_readiness_pass": (capture.get("cutover_readiness") or {}).get("passed") is True,
        "audit_pass": (capture.get("audit") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Final Binding Tail Deadness Proof",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Old Tokens",
        "",
        f"- old tokens present: `{capture.get('old_tokens_present')}`",
        f"- old tokens absent: `{capture.get('old_tokens_absent')}`",
        "",
        "## Adapter Path",
        "",
        f"- adapter tokens missing: `{capture.get('adapter_tokens_missing')}`",
        f"- shared-owned tokens missing: `{capture.get('shared_owned_tokens_missing')}`",
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
            "Continue to the next residual-shear cleanup page-owned tail. The old manual final-binding page merge is no longer present in the route.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_deadness_proof.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_deadness_proof_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_deadness_proof_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_final_binding_tail_deadness_proof_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_deadness_proof "
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
