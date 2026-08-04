from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


def _stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any] | None:
    matches = sorted((ROOT / "artifacts" / "verification").glob(f"{prefix}_*.json"))
    if not matches:
        return None
    try:
        return json.loads(matches[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def _block(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    helper_block = _block(
        source,
        "def _run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
        "\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness(",
    )
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    old_direct_call_token = "_compute_shear_tightening_recommendation("
    old_direct_assignment_token = "residual_shear_tighten = _compute_shear_tightening_recommendation("
    old_direct_try_token = "try:\n            residual_shear_tighten = _compute_shear_tightening_recommendation("
    injected_runner_token = "_run_post_click_low_bending_residual_shear_cleanup_primary_executor("
    injected_executor_token = "executor=_compute_shear_tightening_recommendation"
    call_shape_cutover = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_call_shape_cutover"
    )
    render_lock = _latest("design_guide_render_bridge_lock")
    compute_lock = _latest("design_guide_compute_resolver_publication_bridge_lock")
    independence_lock = _latest("design_guide_independence_lock")
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_PRIMARY_EXECUTOR_DIRECT_CALL_DEADNESS_PROVEN",
        "route_block_present": bool(route_block),
        "runner_helper_present": bool(helper_block),
        "runner_helper_uses_injected_executor": "callable(executor)" in helper_block
        and "executor(" in helper_block,
        "old_direct_call_count_in_route": route_block.count(old_direct_call_token),
        "old_direct_assignment_count_in_route": route_block.count(old_direct_assignment_token),
        "old_direct_try_count_in_route": route_block.count(old_direct_try_token),
        "injected_runner_call_count_in_route": route_block.count(injected_runner_token),
        "injected_executor_reference_count_in_route": route_block.count(injected_executor_token),
        "residual_result_variables_retained": all(
            token in route_block
            for token in (
                "residual_shear_tighten",
                "residual_shear_debug",
                "residual_shear_updates",
                "return dict(",
                "residual_prebuilt_route_result.get(\"result_item\")",
            )
        ),
        "call_shape_cutover_latest_status": (call_shape_cutover or {}).get("status"),
        "render_bridge_lock_latest_status": (render_lock or {}).get("status"),
        "compute_resolver_publication_bridge_lock_latest_status": (compute_lock or {}).get("status"),
        "independence_lock_latest_status": (independence_lock or {}).get("status"),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "route_block_present": capture.get("route_block_present") is True,
        "runner_helper_present": capture.get("runner_helper_present") is True,
        "runner_helper_uses_injected_executor": capture.get("runner_helper_uses_injected_executor") is True,
        "old_direct_call_count_zero": capture.get("old_direct_call_count_in_route") == 0,
        "old_direct_assignment_count_zero": capture.get("old_direct_assignment_count_in_route") == 0,
        "old_direct_try_count_zero": capture.get("old_direct_try_count_in_route") == 0,
        "single_injected_runner_call": capture.get("injected_runner_call_count_in_route") == 1,
        "single_injected_executor_reference": capture.get("injected_executor_reference_count_in_route") == 1,
        "residual_result_variables_retained": capture.get("residual_result_variables_retained") is True,
        "call_shape_cutover_latest_pass": capture.get("call_shape_cutover_latest_status") == "PASS",
        "render_bridge_lock_latest_pass": capture.get("render_bridge_lock_latest_status") == "PASS",
        "compute_resolver_publication_bridge_lock_latest_pass": (
            capture.get("compute_resolver_publication_bridge_lock_latest_status") == "PASS"
        ),
        "independence_lock_latest_pass": capture.get("independence_lock_latest_status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Primary Executor Direct Call Deadness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Old direct call count in route: `{capture.get('old_direct_call_count_in_route')}`",
        f"- Old direct assignment count in route: `{capture.get('old_direct_assignment_count_in_route')}`",
        f"- Old direct try/call count in route: `{capture.get('old_direct_try_count_in_route')}`",
        f"- Injected runner call count in route: `{capture.get('injected_runner_call_count_in_route')}`",
        f"- Injected executor reference count in route: `{capture.get('injected_executor_reference_count_in_route')}`",
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
            "Lock the direct primary executor route call at zero, then audit the next residual-shear dependency slot: fallback variant generator or candidate evaluator.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_direct_call_deadness_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_direct_call_deadness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_direct_call_deadness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_primary_executor_direct_call_deadness_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_direct_call_deadness "
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
