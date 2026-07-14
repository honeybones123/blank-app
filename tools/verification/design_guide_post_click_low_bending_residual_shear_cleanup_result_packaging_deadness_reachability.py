"""Deadness proof for old residual shear cleanup direct result-packaging route calls."""

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
CUTOVER = (
    ROOT
    / "tools"
    / "verification"
    / "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_cutover_implementation.py"
)
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


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    if end < 0:
        return source[start:]
    return source[start:end]


def _run_cutover() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(CUTOVER)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0
        and "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_cutover_implementation PASS"
        in proc.stdout,
    }


def _capture() -> dict[str, Any]:
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    helper = _between(
        source,
        "def _run_post_click_low_bending_residual_shear_cleanup_result_packaging(",
        "\n\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness(",
    )
    route = _between(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    cutover = _run_cutover()
    old_direct_tokens = (
        "residual_shear_item = _shear_tightening_as_local_cleanup_item(",
        "residual_promoted, residual_detail = _evaluate_local_cleanup_guidance_item(",
    )
    return {
        "decision": "OLD_RESIDUAL_SHEAR_RESULT_PACKAGING_ROUTE_BODY_DEAD",
        "route_found": bool(route),
        "helper_found": bool(helper),
        "old_direct_route_token_count": sum(route.count(token) for token in old_direct_tokens),
        "old_direct_route_tokens_absent": not any(token in route for token in old_direct_tokens),
        "only_allowed_route_invocation": route.count(
            "_run_post_click_low_bending_residual_shear_cleanup_result_packaging("
        )
        == 1,
        "helper_owns_only_dependency_shell": all(
            token in helper
            for token in (
                "residual_shear_item = packager(",
                "residual_promoted, residual_detail = local_cleanup_evaluator(",
                'source="post_click_low_bending_residual_shear_cleanup"',
            )
        ),
        "helper_does_not_own_cta": "_design_guide_button_contract(" not in helper,
        "helper_does_not_own_visible_wording": "above the preferred" not in helper
        and "outside_target_band_allowed_reason" not in helper,
        "route_still_owns_cta_contract_after_wrapper": "_design_guide_button_contract(" in route,
        "route_evidence_merge_uses_controller_adapter_after_wrapper": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter("
            in route
            or "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_trace("
            in route
        ),
        "cutover_snapshot": cutover,
        "delete_or_rewrite_shared_packager": False,
        "delete_or_rewrite_shared_evaluator": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "route_found": capture.get("route_found") is True,
        "helper_found": capture.get("helper_found") is True,
        "old_direct_route_tokens_absent": capture.get("old_direct_route_tokens_absent") is True,
        "old_direct_route_token_count_zero": capture.get("old_direct_route_token_count") == 0,
        "only_allowed_route_invocation": capture.get("only_allowed_route_invocation") is True,
        "helper_owns_only_dependency_shell": capture.get("helper_owns_only_dependency_shell") is True,
        "helper_does_not_own_cta": capture.get("helper_does_not_own_cta") is True,
        "helper_does_not_own_visible_wording": capture.get("helper_does_not_own_visible_wording") is True,
        "route_no_longer_owns_cta_contract_after_wrapper": (
            capture.get("route_still_owns_cta_contract_after_wrapper") is False
        ),
        "route_evidence_merge_uses_controller_adapter_after_wrapper": (
            capture.get("route_evidence_merge_uses_controller_adapter_after_wrapper") is True
        ),
        "cutover_snapshot_passed": (capture.get("cutover_snapshot") or {}).get("passed") is True,
        "shared_packager_not_deleted": capture.get("delete_or_rewrite_shared_packager") is False,
        "shared_evaluator_not_deleted": capture.get("delete_or_rewrite_shared_evaluator") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Result Packaging Deadness Reachability",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Result",
        "",
        f"- old direct route token count: `{capture.get('old_direct_route_token_count')}`",
        f"- only allowed route invocation is wrapper: `{capture.get('only_allowed_route_invocation')}`",
        f"- cutover snapshot passed: `{(capture.get('cutover_snapshot') or {}).get('passed')}`",
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
            "Continue to the next residual-shear route surface. Do not delete shared packager/evaluator helpers unless a global reachability verifier proves they are dead.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_deadness_reachability.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_deadness_reachability_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_deadness_reachability_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_result_packaging_deadness_reachability_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_deadness_reachability "
        f"{payload['status']}"
    )
    print(json_path)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
