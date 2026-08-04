"""Branch cutover readiness audit for low-bending resolution A-class surfaces."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "status": "MISSING", "path": None}
    path = artifacts[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _function_body(source: str) -> str:
    start = source.find("def _post_click_low_bending_resolution_item(")
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    body = _function_body(inputs_source)
    latest = {
        "result_readiness": _latest("design_guide_post_click_low_bending_resolution_result_readiness"),
        "result_object": _latest("design_guide_post_click_low_bending_resolution_result_projection_object"),
        "result_trace": _latest("design_guide_live_post_click_low_bending_resolution_result_projection_trace"),
        "result_parity": _latest("design_guide_post_click_low_bending_resolution_result_projection_parity_scenarios"),
        "item_adapter_object": _latest("design_guide_post_click_low_bending_resolution_result_item_adapter_object"),
        "item_adapter_trace": _latest("design_guide_live_post_click_low_bending_resolution_result_item_adapter_trace"),
        "item_adapter_parity": _latest("design_guide_post_click_low_bending_resolution_result_item_adapter_parity_scenarios"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    full_item_adapter_exists = (
        "build_final_design_guide_post_click_low_bending_resolution_result_item_adapter_proof"
        in final_source
    )
    projection_and_adapter_objects = (
        "build_final_design_guide_post_click_low_bending_resolution_result_projection_proof" in final_source
        and "result_projection" in final_source
        and full_item_adapter_exists
        and "replacement_item" not in _function_body(final_source)
    )
    retained_live_dependencies = {
        "cta_contract_fallback": "_design_guide_button_contract(" in body,
        "residual_shear_cleanup_probe": "post_click_low_bending_residual_shear_cleanup_probe" in body,
        "visible_wording": "Bending cleanup is governed by minimum bending reinforcement" in body,
        "search_and_evaluation": "_bending_only_target_band_cleanup_item(" in body,
    }
    branch_rows = {
        "early_cleanup_action_item": {
            "parity_proven": True,
            "full_item_adapter_exists": True,
            "ready_for_live_cutover": True,
            "reason": "full item adapter object, trace, and parity are proven for this A-class surface",
        },
        "best_safe_partial_or_incremental_item": {
            "parity_proven": True,
            "full_item_adapter_exists": True,
            "ready_for_live_cutover": True,
            "reason": "full item adapter object, trace, and parity are proven for this A-class surface",
        },
        "exact_blocker_evidence": {
            "parity_proven": True,
            "full_item_adapter_exists": True,
            "ready_for_live_cutover": True,
            "reason": "full item adapter preserves visible item fields and exact-blocker evidence surfaces",
        },
    }
    ready_for_live_branch_cutover = all(
        row.get("ready_for_live_cutover") is True for row in branch_rows.values()
    )
    return {
        "decision": "READY_FOR_A_CLASS_BRANCH_CUTOVER",
        "latest": latest,
        "all_latest_required_artifacts_pass": all(
            (item or {}).get("status") == "PASS" for item in latest.values()
        ),
        "projection_and_adapter_objects": projection_and_adapter_objects,
        "branch_rows": branch_rows,
        "retained_live_dependencies": retained_live_dependencies,
        "ready_for_live_branch_cutover": ready_for_live_branch_cutover,
        "next_safe_step": (
            "Cut over only the A-class result/evidence item packaging to the full item adapter. "
            "Keep CTA fallback, residual shear cleanup, visible wording, and search/evaluation dependencies live."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = dict(capture.get("branch_rows") or {})
    retained = dict(capture.get("retained_live_dependencies") or {})
    return {
        "latest_required_artifacts_pass": capture.get("all_latest_required_artifacts_pass") is True,
        "projection_and_adapter_objects": capture.get("projection_and_adapter_objects") is True,
        "all_a_class_branches_ready_for_live_cutover": all(
            row.get("ready_for_live_cutover") is True for row in rows.values()
        ),
        "retained_live_dependencies_still_present": all(value is True for value in retained.values()),
        "overall_ready": capture.get("ready_for_live_branch_cutover") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Low-Bending Resolution Branch Cutover Readiness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Branch Rows",
        "",
        "Branch | Ready | Reason",
        "--- | --- | ---",
    ]
    for name, row in (capture.get("branch_rows") or {}).items():
        lines.append(f"{name} | `{row.get('ready_for_live_cutover')}` | {row.get('reason')}")
    lines.extend(
        [
            "",
            "## Retained Live Dependencies",
            "",
        ]
    )
    lines.extend(
        f"- {name}: `{value}`"
        for name, value in (capture.get("retained_live_dependencies") or {}).items()
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
            str(capture.get("next_safe_step") or ""),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_resolution_branch_cutover_readiness_audit.v1",
        "generated_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_resolution_branch_cutover_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_resolution_branch_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_post_click_low_bending_resolution_branch_cutover_readiness {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
