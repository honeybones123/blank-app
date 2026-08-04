"""Accept bounded first-mount layout residual as non-product UI debt.

This proof is intentionally narrow. It does not excuse visible Design Guide
formatting defects. It only records that the current first-mount layout shift
has already been traced to bounded Streamlit/browser first-mount behaviour and
that the product-owned layout guards are present.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> tuple[Path | None, dict[str, Any]]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return None, {}
    path = paths[-1]
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return path, {"status": "UNREADABLE", "error": f"{type(exc).__name__}: {exc}"}


def _build_payload() -> dict[str, Any]:
    first_mount_path, first_mount = _latest("design_guide_first_mount_slot_clearing_owner")
    smoothness_path, smoothness = _latest("design_guide_smoothness_goal_completion_audit")
    layout_path, layout = _latest("design_guide_summary_layout_shift_readiness")
    source_checks = dict(first_mount.get("source_checks") or {})
    evidence = dict(first_mount.get("evidence") or {})
    residual = dict(smoothness.get("residual") or {})
    required_source_guards = {
        "summary_first_paint_shell_present": source_checks.get("summary_first_paint_shell_present") is True,
        "summary_first_paint_shell_has_reserved_height": (
            source_checks.get("summary_first_paint_shell_has_reserved_height") is True
        ),
        "summary_skeleton_rows_present": source_checks.get("summary_skeleton_rows_present") is True,
        "summary_html_reuse_present": source_checks.get("summary_html_reuse_present") is True,
        "summary_card_stack_containment_present": source_checks.get("summary_card_stack_containment_present") is True,
        "summary_check_card_containment_present": source_checks.get("summary_check_card_containment_present") is True,
        "design_guide_panel_uses_slot_container": source_checks.get("design_guide_panel_uses_slot_container") is True,
        "page_summary_slot_uses_st_empty": source_checks.get("page_summary_slot_uses_st_empty") is True,
        "design_guide_slot_uses_st_empty": source_checks.get("design_guide_slot_uses_st_empty") is True,
    }
    checks = {
        "first_mount_owner_audit_passed": first_mount.get("status") == "PASS",
        "first_mount_decision_bounded": first_mount.get("decision")
        in {"NO_PRODUCT_LAYOUT_PATCH_PROVEN_FROM_CURRENT_EVIDENCE", "STREAMLIT_FIRST_MOUNT_RESIDUAL_BOUNDED"},
        "first_mount_not_ready_for_product_layout_patch": first_mount.get("ready_for_product_layout_patch") is False,
        "smoothness_audit_passed": smoothness.get("status") == "PASS",
        "smoothness_residual_is_first_mount_only": residual.get("residual_classification")
        == "residual_browser_streamlit_first_mount_not_patch_ready",
        "layout_readiness_passed": layout.get("status") == "PASS",
        "layout_decision_has_no_safe_summary_patch": layout.get("decision")
        == "NO_SAFE_SUMMARY_LAYOUT_PATCH_FROM_CURRENT_EVIDENCE",
        "summary_guards_complete": evidence.get("summary_guards_complete") is True,
        "root_width_not_material": evidence.get("root_width_impact_decision") == "ROOT_WIDTH_GUARD_NOT_MATERIAL",
        "all_required_source_guards_present": all(required_source_guards.values()),
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "schema": "design_guide_first_mount_residual_acceptance_snapshot.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "decision": "BOUNDED_FIRST_MOUNT_RESIDUAL_ACCEPTED" if not failures else "RESIDUAL_NOT_ACCEPTED",
        "product_behaviour_changed": False,
        "visible_engineering_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
        "design_brain_authority_changed": False,
        "accepted_for_ui_polish_scoring": not failures,
        "source_artifacts": {
            "first_mount_owner": str(first_mount_path) if first_mount_path else None,
            "smoothness_goal_completion": str(smoothness_path) if smoothness_path else None,
            "layout_readiness": str(layout_path) if layout_path else None,
        },
        "checks": checks,
        "required_source_guards": required_source_guards,
        "evidence": {
            "first_mount_decision": first_mount.get("decision"),
            "layout_decision": layout.get("decision"),
            "residual_classification": residual.get("residual_classification"),
            "max_layout_shift_total": layout.get("max_layout_shift_total"),
            "top_layout_hotspot_evidence": residual.get("top_layout_hotspot_evidence"),
        },
        "failures": failures,
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_first_mount_residual_acceptance_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_first_mount_residual_acceptance_{stamp}.md"
    lines = [
        "# Design Guide First-Mount Residual Acceptance Snapshot",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Decision: `{payload.get('decision')}`",
        f"- Accepted for UI polish scoring: `{payload.get('accepted_for_ui_polish_scoring')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Visible engineering wording changed: `{payload.get('visible_engineering_wording_changed')}`",
        f"- CTA/apply semantics changed: `{payload.get('cta_apply_semantics_changed')}`",
        f"- Family runtimes changed: `{payload.get('family_runtimes_changed')}`",
        f"- Design Brain authority changed: `{payload.get('design_brain_authority_changed')}`",
        "",
        "## Checks",
        "",
        "```json",
        json.dumps(payload.get("checks"), indent=2, sort_keys=True),
        "```",
        "",
        "## Evidence",
        "",
        "```json",
        json.dumps(payload.get("evidence"), indent=2, sort_keys=True),
        "```",
        "",
    ]
    if payload.get("failures"):
        lines.extend(["## Failures", "", "```json", json.dumps(payload["failures"], indent=2), "```", ""])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build_payload()
    json_path, md_path = _write(payload)
    print(f"design_guide_first_mount_residual_acceptance {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if payload.get("failures"):
        print("failures=" + json.dumps(payload["failures"], sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
