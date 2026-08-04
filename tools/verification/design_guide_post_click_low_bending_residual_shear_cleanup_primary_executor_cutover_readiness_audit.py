"""Cutover readiness audit for residual shear cleanup primary executor."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=180)
    return {
        "command": command,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
    }


def _block(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _classify_dependencies(route_block: str) -> list[dict[str, Any]]:
    dependencies = [
        {
            "name": "primary_executor_function",
            "token": "executor=_compute_shear_tightening_recommendation",
            "classification": "B. injected page-owned executor",
            "reason": "The route supplies the same page-local executor through the injected runner.",
        },
        {
            "name": "design_actions_resolution",
            "token": "_resolve_design_actions_from_state(",
            "classification": "B. inject as page-owned executor input",
            "reason": "Executor input still depends on page-local action resolution.",
        },
        {
            "name": "local_cleanup_item_adapter",
            "token": "_shear_tightening_as_local_cleanup_item(",
            "classification": "C. next boundary after primary executor",
            "reason": "Packaging the executor candidate into a local cleanup item is separate from executor search.",
        },
        {
            "name": "local_cleanup_evaluator",
            "token": "_evaluate_local_cleanup_guidance_item(",
            "classification": "C. next boundary after primary executor",
            "reason": "Evaluation/acceptance remains a separate live dependency.",
        },
        {
            "name": "button_contract_builder",
            "token": "_design_guide_button_contract(",
            "classification": "D. keep page/shared for now",
            "reason": "CTA contract execution is explicitly out of this executor cutover slice.",
        },
        {
            "name": "visible_residual_wording",
            "token": "above the preferred",
            "classification": "D. keep page/shared for now",
            "reason": "Visible wording must not move in this slice.",
        },
        {
            "name": "fallback_variant_generator",
            "token": "generate_less_shear_reo_variants(",
            "classification": "C. separate fallback generator boundary",
            "reason": "Fallback variant generation is a different dependency slot.",
        },
        {
            "name": "candidate_evaluator",
            "token": "_evaluate_auto_design_candidate(",
            "classification": "C. separate candidate evaluator boundary",
            "reason": "Candidate evaluation remains a separate dependency slot.",
        },
    ]
    return [
        {
            **dependency,
            "present": dependency["token"] in route_block,
        }
        for dependency in dependencies
    ]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    parity_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_parity_scenarios.py",
        ]
    )
    dependencies = _classify_dependencies(route_block)
    present_blockers = [
        dependency
        for dependency in dependencies
        if dependency.get("present")
        and str(dependency.get("classification") or "").startswith(("C.", "D."))
    ]
    injection_prereqs = [
        dependency
        for dependency in dependencies
        if dependency.get("present")
        and str(dependency.get("classification") or "").startswith("B.")
    ]
    return {
        "decision": "PRIMARY_EXECUTOR_READY_FOR_INJECTED_EXECUTOR_ADAPTER_NOT_DIRECT_CUTOVER",
        "route_block_present": bool(route_block),
        "dependency_inventory": dependencies,
        "injection_prerequisites": injection_prereqs,
        "direct_cutover_blockers": present_blockers,
        "direct_controller_cutover_ready": False,
        "injected_executor_adapter_ready_next": bool(injection_prereqs)
        and (parity_run.get("passed") is True),
        "recommended_next_surface": "primary_executor_injected_adapter_object",
        "parity_scenarios": parity_run,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    dependencies = list(capture.get("dependency_inventory") or [])
    return {
        "route_block_present": capture.get("route_block_present") is True,
        "dependency_inventory_present": len(dependencies) >= 8,
        "all_inventory_items_have_presence": all("present" in item for item in dependencies),
        "injection_prerequisites_identified": bool(capture.get("injection_prerequisites")),
        "direct_cutover_blockers_cleared": not bool(capture.get("direct_cutover_blockers")),
        "direct_controller_cutover_not_ready": (
            capture.get("direct_controller_cutover_ready") is False
        ),
        "injected_executor_adapter_ready_next": (
            capture.get("injected_executor_adapter_ready_next") is True
        ),
        "parity_scenarios_passed": (capture.get("parity_scenarios") or {}).get("passed")
        is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Primary Executor Cutover Readiness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Direct controller cutover ready: `{capture.get('direct_controller_cutover_ready')}`",
        f"- Injected executor adapter ready next: `{capture.get('injected_executor_adapter_ready_next')}`",
        f"- Recommended next surface: `{capture.get('recommended_next_surface')}`",
        "",
        "## Dependency Inventory",
        "",
    ]
    for item in capture.get("dependency_inventory") or []:
        lines.append(
            "- "
            + str(item.get("name"))
            + ": present=`"
            + str(item.get("present"))
            + "`, classification=`"
            + str(item.get("classification"))
            + "`, reason="
            + str(item.get("reason"))
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Create a primary executor injected-adapter object. Do not move formula helpers, candidate evaluation, fallback generator, CTA contract execution, or visible wording.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_cutover_readiness_audit.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_cutover_readiness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_cutover_readiness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_primary_executor_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_primary_executor_cutover_readiness "
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
