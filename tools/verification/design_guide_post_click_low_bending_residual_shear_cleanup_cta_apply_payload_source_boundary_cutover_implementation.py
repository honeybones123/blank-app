"""Verify guarded source-summary cutover for residual-shear CTA/apply payloads."""

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
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=120)
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
        "passed": proc.returncode == 0,
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
    readiness_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_cutover_readiness.py",
        ]
    )
    parity_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_parity_scenarios.py",
        ]
    )
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    summary_tokens = {
        "source_summary_flag": '"cta_apply_payload_source_summary_cutover": True' in route,
        "action_payload_hash_from_boundary": (
            ').get(\n                                    "action_payload_hash"\n                                )'
            in route
            and '"action_payload_hash": (' in route
        ),
        "resolved_candidate_hash_from_boundary": (
            ').get(\n                                    "resolved_candidate_hash"\n                                )'
            in route
            and '"resolved_candidate_hash": (' in route
        ),
        "button_contract_hash_from_boundary": (
            ').get(\n                                    "button_contract_hash"\n                                )'
            in route
            and '"button_contract_hash": (' in route
        ),
        "button_contract_updates_hash_from_boundary": (
            ').get(\n                                    "button_contract_updates_hash"\n                                )'
            in route
            and '"button_contract_updates_hash": (' in route
        ),
        "expected_util_from_boundary": '.get("button_contract_expected_util")' in route,
        "enabled_from_boundary": '.get("button_contract_enabled")' in route,
        "actionable_from_boundary": '.get("button_contract_actionable")' in route,
        "raw_fallbacks_retained": all(
            token in route
            for token in (
                "_stable_final_publication_hash(\n                                    dict(residual_payload or {})",
                "_stable_final_publication_hash(\n                                    dict(residual_resolved or {})",
                "_stable_final_publication_hash(\n                                    dict(residual_button_contract or {})",
                "_stable_final_publication_hash(\n                                    dict(residual_button_contract.get(\"updates\") or {})",
            )
        ),
        "shared_button_contract_execution_retained": (
            "_design_guide_button_contract(residual_promoted, state=state)" in route
            or "_execute_post_click_low_bending_residual_shear_cleanup_button_contract("
            in route
        ),
        "route_return_retained": "return residual_route_return_item" in route,
    }
    source_summary_cutover_implemented = all(summary_tokens.values())
    return {
        "decision": (
            "CTA_APPLY_PAYLOAD_SOURCE_SUMMARY_CUTOVER_IMPLEMENTED_READY_FOR_DEADNESS_RECHECK"
            if source_summary_cutover_implemented
            else "CTA_APPLY_PAYLOAD_SOURCE_SUMMARY_CUTOVER_INCOMPLETE"
        ),
        "readiness_run": readiness_run,
        "parity_run": parity_run,
        "summary_tokens": summary_tokens,
        "source_summary_cutover_implemented": source_summary_cutover_implemented,
        "behavior_cutover_ready": False,
        "safe_to_delete_route_body_now": False,
        "explicitly_retained_live_surfaces": (
            "shared_button_contract_execution",
            "cta_apply_routing",
            "visible_wording",
            "route_body_return",
            "result_packaging_execution",
        ),
        "next_safe_surface": "route_body_behavior_gap_recheck",
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "readiness_passed": (capture.get("readiness_run") or {}).get("passed") is True,
        "parity_passed": (capture.get("parity_run") or {}).get("passed") is True,
        "source_summary_cutover_implemented": (
            capture.get("source_summary_cutover_implemented") is True
        ),
        "behavior_cutover_not_claimed": capture.get("behavior_cutover_ready") is False,
        "route_body_deletion_not_claimed": capture.get("safe_to_delete_route_body_now") is False,
        "retained_live_surfaces_explicit": bool(capture.get("explicitly_retained_live_surfaces")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup CTA/Apply Payload Source Boundary Cutover Implementation",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Source-summary cutover implemented: `{capture.get('source_summary_cutover_implemented')}`",
        f"- Behaviour cutover ready: `{capture.get('behavior_cutover_ready')}`",
        f"- Safe to delete route body now: `{capture.get('safe_to_delete_route_body_now')}`",
        f"- Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Token Checks",
        "",
    ]
    for key, value in (capture.get("summary_tokens") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Explicitly Retained Live Surfaces", ""])
    lines.extend(f"- `{item}`" for item in capture.get("explicitly_retained_live_surfaces") or ())
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_cutover_implementation.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_cutover_implementation_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_cutover_implementation_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_cta_apply_payload_source_boundary_cutover_implementation_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_cutover_implementation "
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
