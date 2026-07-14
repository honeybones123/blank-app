"""Audit first-mount slot clearing ownership for Inputs / Design Guide UI polish.

Proof-only. This composes the current first-paint/layout artifacts and source
markers to decide whether the remaining layout shift is patchable product UI
work or an already-bounded Streamlit first-mount residual.

It must not change engineering behaviour, visible wording, CTA/apply semantics,
family runtimes, Design Brain authority, widget keys, or render ownership.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
DESIGN_GUIDE_PAGE = ROOT / "design_guide_page.py"
SUMMARY_SOURCE = ROOT / "ui" / "summary_sections.py"
APP_PY = ROOT / "app.py"


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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _source_checks() -> dict[str, Any]:
    inputs = _read(INPUTS_PAGE)
    page = _read(DESIGN_GUIDE_PAGE)
    summary = _read(SUMMARY_SOURCE)
    app = _read(APP_PY)
    return {
        "summary_first_paint_shell_present": "inputs-first-paint-shell" in inputs,
        "summary_first_paint_shell_has_reserved_height": "_first_paint_shell_min_height" in inputs
        and "__FIRST_PAINT_MIN_HEIGHT__" in inputs,
        "summary_skeleton_rows_present": inputs.count("summary-skeleton-row") >= 4,
        "summary_html_reuse_present": "_final_publication_summary_card_html_cache" in inputs,
        "summary_card_stack_containment_present": "summary-card-stack" in summary
        and "contain: layout paint" in summary,
        "summary_check_card_containment_present": "summary-check-card" in summary
        and "contain: layout paint" in summary,
        "design_guide_panel_uses_slot_container": "with slot.container():" in page
        and "render_final_panel" in page,
        "page_summary_slot_uses_st_empty": "summary_container = st.empty()" in inputs,
        "design_guide_slot_uses_st_empty": "design_guide_slot = st.empty()" in inputs,
        "app_wide_main_width_guard_scoped": '.stApp [data-testid="stMainBlockContainer"]' in app,
        "unscoped_main_width_guard_absent": '\n  [data-testid="stMainBlockContainer"],\n  .block-container,' not in app,
    }


def _build_payload() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    hotspot_path, hotspot = _latest("design_guide_first_paint_layout_hotspot_owner")
    source_node_path, source_node = _latest("design_guide_streamlit_layout_shift_source_node")
    summary_readiness_path, summary_readiness = _latest("design_guide_summary_layout_shift_readiness")
    containment_path, containment = _latest("design_guide_summary_card_layout_containment_readiness")
    root_impact_path, root_impact = _latest("design_guide_streamlit_root_width_guard_impact")
    gap_path, gap = _latest("design_guide_first_paint_layout_gap_audit")
    height_path, height = _latest("design_guide_summary_first_paint_shell_height_readiness")

    source_node_summary = dict(source_node.get("summary") or {})
    source_values = dict(source_node_summary.get("layout_shift_owner_values") or {})
    source_counts = dict(source_node_summary.get("layout_shift_owner_counts") or {})
    checks = _source_checks()

    artifacts = {
        "hotspot_owner": str(hotspot_path) if hotspot_path else None,
        "source_node": str(source_node_path) if source_node_path else None,
        "summary_layout_readiness": str(summary_readiness_path) if summary_readiness_path else None,
        "summary_card_containment_readiness": str(containment_path) if containment_path else None,
        "root_width_guard_impact": str(root_impact_path) if root_impact_path else None,
        "first_paint_layout_gap_audit": str(gap_path) if gap_path else None,
        "summary_height_readiness": str(height_path) if height_path else None,
    }

    required_pass = {
        "hotspot_owner": hotspot.get("status"),
        "source_node": source_node.get("status"),
        "summary_layout_readiness": summary_readiness.get("status"),
        "summary_card_containment_readiness": containment.get("status"),
        "root_width_guard_impact": root_impact.get("status"),
        "first_paint_layout_gap_audit": gap.get("status"),
        "summary_height_readiness": height.get("status"),
    }
    failures = [name for name, status in required_pass.items() if status != "PASS"]

    summary_layout_decision = str(summary_readiness.get("decision") or "")
    containment_decision = str(containment.get("decision") or "")
    root_impact_decision = str(root_impact.get("decision") or "")
    gap_diagnosis = str(gap.get("diagnosis") or "")
    height_decision = str(height.get("decision") or dict(height.get("summary") or {}).get("decision") or "")
    top_owner = str(source_node_summary.get("top_owner_by_value") or "")
    fixed_gap_resolved = bool(summary_readiness.get("fixed_gap_resolved")) and gap_diagnosis == "measured_batch_gap_resolved"
    summary_guards_complete = bool(summary_readiness.get("existing_guards_complete")) and all(
        bool(checks.get(key))
        for key in (
            "summary_first_paint_shell_present",
            "summary_first_paint_shell_has_reserved_height",
            "summary_skeleton_rows_present",
            "summary_html_reuse_present",
            "summary_card_stack_containment_present",
            "summary_check_card_containment_present",
        )
    )
    root_width_nonmaterial = root_impact_decision == "ROOT_WIDTH_GUARD_NOT_MATERIAL"
    no_summary_patch = (
        summary_layout_decision == "NO_SAFE_SUMMARY_LAYOUT_PATCH_FROM_CURRENT_EVIDENCE"
        and containment_decision == "NOT_READY_FOR_SUMMARY_CARD_CONTAINMENT"
        and fixed_gap_resolved
        and summary_guards_complete
        and height_decision == "NO_MATERIAL_HEIGHT_MISMATCH"
    )

    if failures:
        decision = "NEEDS_FRESH_LAYOUT_EVIDENCE"
        patch_ready = False
        next_slice = "Refresh all first-mount/layout artifacts before UI patching."
    elif no_summary_patch and root_width_nonmaterial:
        decision = "NO_PRODUCT_LAYOUT_PATCH_PROVEN_FROM_CURRENT_EVIDENCE"
        patch_ready = False
        next_slice = (
            "Do not add broad spacing, summary containment, or root-width CSS. Move to a lower-risk polish "
            "surface such as proof-pending shell style extraction, or reproduce a user-specific live gap first."
        )
    elif top_owner in {"summary_first_paint_or_cards", "batch_design_panel", "design_guide_panel"}:
        decision = "POTENTIAL_PRODUCT_LAYOUT_PATCH_NEEDS_NARROW_PARITY"
        patch_ready = True
        next_slice = f"Create a narrow readiness/impact proof for `{top_owner}` before product CSS changes."
    else:
        decision = "STREAMLIT_FIRST_MOUNT_RESIDUAL_BOUNDED"
        patch_ready = False
        next_slice = "Treat as bounded first-mount residual and continue with non-layout shared UI polish."

    return {
        "schema": "design_guide_first_mount_slot_clearing_owner_audit.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "decision": decision,
        "product_behaviour_changed": False,
        "visible_engineering_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
        "design_brain_authority_changed": False,
        "ready_for_product_layout_patch": patch_ready,
        "recommended_next_slice": next_slice,
        "source_checks": checks,
        "artifact_statuses": required_pass,
        "source_artifacts": artifacts,
        "evidence": {
            "top_owner_by_value": top_owner,
            "candidate_patch_target": source_node_summary.get("candidate_patch_target"),
            "layout_shift_total_source_node": source_node_summary.get("layout_shift_total"),
            "layout_shift_owner_values": source_values,
            "layout_shift_owner_counts": source_counts,
            "summary_layout_decision": summary_layout_decision,
            "summary_layout_max_shift": summary_readiness.get("max_layout_shift_total"),
            "summary_layout_post_apply_shift": summary_readiness.get("post_apply_layout_shift_total"),
            "summary_guards_complete": summary_guards_complete,
            "summary_containment_decision": containment_decision,
            "fixed_gap_resolved": fixed_gap_resolved,
            "gap_diagnosis": gap_diagnosis,
            "height_decision": height_decision,
            "root_width_impact_decision": root_impact_decision,
        },
        "failures": failures,
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_first_mount_slot_clearing_owner_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_first_mount_slot_clearing_owner_{stamp}.md"
    lines = [
        "# Design Guide First-Mount Slot Clearing Owner Audit",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Decision: `{payload.get('decision')}`",
        f"- Ready for product layout patch: `{payload.get('ready_for_product_layout_patch')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Visible engineering wording changed: `{payload.get('visible_engineering_wording_changed')}`",
        f"- CTA/apply semantics changed: `{payload.get('cta_apply_semantics_changed')}`",
        f"- Family runtimes changed: `{payload.get('family_runtimes_changed')}`",
        f"- Design Brain authority changed: `{payload.get('design_brain_authority_changed')}`",
        "",
        "## Evidence",
        "",
        "```json",
        json.dumps(payload.get("evidence"), indent=2, sort_keys=True, default=str),
        "```",
        "",
        "## Source Checks",
        "",
        "```json",
        json.dumps(payload.get("source_checks"), indent=2, sort_keys=True, default=str),
        "```",
        "",
        "## Recommendation",
        "",
        str(payload.get("recommended_next_slice") or ""),
        "",
    ]
    if payload.get("failures"):
        lines.extend(["## Failures", "", "```json", json.dumps(payload["failures"], indent=2), "```", ""])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build_payload()
    json_path, md_path = _write(payload)
    print(f"design_guide_first_mount_slot_clearing_owner {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
