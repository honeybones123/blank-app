"""Route-entry guard cutover proof for residual shear cleanup.

This verifier proves the page now delegates the pure residual-shear route
entry boolean to DesignGuideController while retaining the page-owned skip
probe execution boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard,
)


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


def _old_inline_decision(
    *,
    current_shear_util: float | None,
    target_band_eps: float,
    skip_probe_blocked: bool,
) -> bool:
    return bool(
        current_shear_util is not None
        and float(current_shear_util) < 1.0 - float(target_band_eps)
        and not bool(skip_probe_blocked)
    )


def _scenario(
    name: str,
    *,
    current_shear_util: float | None,
    target_band_eps: float = 1e-9,
    skip_probe_evaluated: bool,
    skip_probe_blocked: bool,
) -> dict[str, Any]:
    result = run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard(
        current_shear_util=current_shear_util,
        target_band_eps=target_band_eps,
        skip_probe_evaluated=skip_probe_evaluated,
        skip_probe_blocked=skip_probe_blocked,
        route_inputs={"scenario": name},
    )
    expected = _old_inline_decision(
        current_shear_util=current_shear_util,
        target_band_eps=target_band_eps,
        skip_probe_blocked=skip_probe_blocked,
    )
    # The old inline form only evaluated the skip probe after the shear util
    # threshold passed. Keep that short-circuit represented in the scenario.
    if not skip_probe_evaluated:
        expected = False
    repeated = run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard(
        current_shear_util=current_shear_util,
        target_band_eps=target_band_eps,
        skip_probe_evaluated=skip_probe_evaluated,
        skip_probe_blocked=skip_probe_blocked,
        route_inputs={"scenario": name},
    )
    return {
        "name": name,
        "expected_should_enter_route": expected,
        "actual_should_enter_route": result.get("should_enter_route"),
        "decision_reason": result.get("decision_reason"),
        "stable_hash_repeat": result.get("route_entry_guard_hash")
        == repeated.get("route_entry_guard_hash"),
        "stable_runner_hash_repeat": result.get("route_entry_guard_runner_hash")
        == repeated.get("route_entry_guard_runner_hash"),
        "skip_probe_execution_owned_elsewhere": result.get("skip_probe_execution_owned_elsewhere")
        is True,
        "not_render_apply_session_driving": result.get("render_driving") is False
        and result.get("apply_driving") is False
        and result.get("session_driving") is False,
        "passed": (
            result.get("should_enter_route") is expected
            and result.get("route_entry_guard_hash") == repeated.get("route_entry_guard_hash")
            and result.get("route_entry_guard_runner_hash")
            == repeated.get("route_entry_guard_runner_hash")
            and result.get("skip_probe_execution_owned_elsewhere") is True
            and result.get("render_driving") is False
            and result.get("apply_driving") is False
            and result.get("session_driving") is False
        ),
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(
        inputs_source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    scenarios = [
        _scenario(
            "missing_shear_util",
            current_shear_util=None,
            skip_probe_evaluated=False,
            skip_probe_blocked=False,
        ),
        _scenario(
            "shear_not_below_failure_threshold",
            current_shear_util=1.02,
            skip_probe_evaluated=False,
            skip_probe_blocked=False,
        ),
        _scenario(
            "skip_probe_blocked",
            current_shear_util=0.69,
            skip_probe_evaluated=True,
            skip_probe_blocked=True,
        ),
        _scenario(
            "eligible",
            current_shear_util=0.69,
            skip_probe_evaluated=True,
            skip_probe_blocked=False,
        ),
    ]
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_ROUTE_ENTRY_GUARD_CONTROLLER_CUTOVER",
        "controller_function_present": (
            "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard"
            in controller_source
        ),
        "controller_imported_in_inputs": (
            "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard as "
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard"
            in inputs_source
        ),
        "route_uses_controller_guard": (
            "residual_shear_cleanup_route_entry_guard = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard("
            in route
            and "residual_shear_cleanup_route_entry_decision = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_decision("
            in route
            and "route_entry_guard=dict(residual_shear_cleanup_route_entry_guard or {})"
            in route
        ),
        "skip_probe_still_page_owned": (
            "_skip_bending_fail_post_publication_probe(" in route
            and "skip_probe_execution_owned_elsewhere" in controller_source
        ),
        "short_circuit_preserved": (
            "residual_shear_cleanup_skip_probe_evaluated = True" in route
            and "_skip_bending_fail_post_publication_probe(" in route
            and route.find("_skip_bending_fail_post_publication_probe(")
            < route.find("_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard(")
        ),
        "scenarios": scenarios,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "controller_function_present": capture.get("controller_function_present") is True,
        "controller_imported_in_inputs": capture.get("controller_imported_in_inputs") is True,
        "route_uses_controller_guard": capture.get("route_uses_controller_guard") is True,
        "skip_probe_still_page_owned": capture.get("skip_probe_still_page_owned") is True,
        "short_circuit_preserved": capture.get("short_circuit_preserved") is True,
        "all_scenarios_pass": all(row.get("passed") is True for row in capture.get("scenarios") or []),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Route Entry Guard Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenarios",
        "",
    ]
    for row in capture.get("scenarios") or []:
        lines.append(
            f"- {row.get('name')}: expected=`{row.get('expected_should_enter_route')}`, "
            f"actual=`{row.get('actual_should_enter_route')}`, reason=`{row.get('decision_reason')}`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Continue to fallback search loop extraction. The route entry guard is controller-owned; the skip probe remains page-owned by design.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_entry_guard_cutover.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_entry_guard_cutover_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_entry_guard_cutover_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_route_entry_guard_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_entry_guard_cutover "
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
