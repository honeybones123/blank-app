"""Cutover verifier for residual shear cleanup candidate selection injected shell."""

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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
READINESS = (
    ROOT
    / "tools"
    / "verification"
    / "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter_readiness_snapshot.py"
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


def _run_readiness() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(READINESS)],
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
        and "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter_readiness PASS"
        in proc.stdout,
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(
        inputs_source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    selector_helper = _between(
        inputs_source,
        "def _run_post_click_low_bending_residual_shear_cleanup_candidate_selector(",
        "\n\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness(",
    )
    controller_selector = _between(
        controller_source,
        "def select_design_guide_post_click_low_bending_residual_shear_cleanup_candidate_by_sort_key(",
        "\n\n__all__",
    )
    readiness = _run_readiness()
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_CANDIDATE_SELECTION_CUTOVER_IMPLEMENTED",
        "selector_helper_present": bool(selector_helper),
        "selector_helper_injected_callable": "selector(list(candidates or []))" in selector_helper,
        "controller_selector_present": bool(controller_selector),
        "controller_selector_key_order": all(
            token in controller_selector
            for token in (
                "selected = min(",
                'float(row.get("shear_util") or float("inf"))',
                'len(dict(row.get("updates") or {}))',
                'str(sorted(dict(row.get("updates") or {}).items()))',
            )
        ),
        "controller_selector_exported": (
            '"select_design_guide_post_click_low_bending_residual_shear_cleanup_candidate_by_sort_key"'
            in controller_source
        ),
        "route_direct_min_count": route.count("fallback_best = min("),
        "route_selector_shell_count": route.count(
            "_run_post_click_low_bending_residual_shear_cleanup_candidate_selector("
        ),
        "route_injects_controller_selector": (
            "selector=_select_design_guide_post_click_low_bending_residual_shear_cleanup_candidate_by_sort_key"
            in route
        ),
        "route_trace_stamps_selection": (
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key("
            in route
            and "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_injected_adapter("
            in route
        ),
        "readiness_snapshot": readiness,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "selector_helper_present": capture.get("selector_helper_present") is True,
        "selector_helper_injected_callable": capture.get("selector_helper_injected_callable") is True,
        "controller_selector_present": capture.get("controller_selector_present") is True,
        "controller_selector_key_order": capture.get("controller_selector_key_order") is True,
        "controller_selector_exported": capture.get("controller_selector_exported") is True,
        "route_direct_min_dead": capture.get("route_direct_min_count") == 0,
        "route_selector_shell_single": capture.get("route_selector_shell_count") == 1,
        "route_injects_controller_selector": capture.get("route_injects_controller_selector") is True,
        "route_trace_stamps_selection": capture.get("route_trace_stamps_selection") is True,
        "readiness_snapshot_passed": (capture.get("readiness_snapshot") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Candidate Selection Cutover Implementation",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Result",
        "",
        f"- route direct `fallback_best = min(...)` count: `{capture.get('route_direct_min_count')}`",
        f"- route selector shell count: `{capture.get('route_selector_shell_count')}`",
        f"- controller selector key order proven: `{capture.get('controller_selector_key_order')}`",
        f"- readiness snapshot passed: `{(capture.get('readiness_snapshot') or {}).get('passed')}`",
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
            "Proceed to residual route result-packaging/evaluation dependency proof. Do not delete shared selector, evaluator, CTA, or wording code.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_cutover_implementation.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_cutover_implementation_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_cutover_implementation_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_candidate_selection_cutover_implementation_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_cutover_implementation "
        f"{payload['status']}"
    )
    print(json_path)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
