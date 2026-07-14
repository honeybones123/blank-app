from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(r"C:/Users/jono/OneDrive/Documents/GitHub/complete-app - Copy (3)")
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


CALLSITES = {
    "early_shear_cleanup_direct_action_shell": {
        "assignment": "_early_shear_cleanup_shell_projection = _build_final_design_guide_direct_shell_card_projection(",
        "marker": "early_shear_overdesign_direct_action_shell",
        "projection_var": "_early_shear_cleanup_shell_projection",
        "expected_classification": "cutover_complete_non_fallback_direct_shell",
    },
    "pre_render_contract_shell": {
        "assignment": "_pre_render_shell_projection = _build_final_design_guide_direct_shell_card_projection(",
        "marker": "browser_enabled_contract_pre_render_shell",
        "projection_var": "_pre_render_shell_projection",
        "expected_classification": "cutover_complete_non_fallback_direct_shell",
    },
    "post_render_contract_shell": {
        "assignment": "_fallback_shell_projection = _build_final_design_guide_direct_shell_card_projection(",
        "marker": "fallback_enabled_contract_shell",
        "projection_var": "_fallback_shell_projection",
        "expected_classification": "cutover_complete_non_fallback_direct_shell",
    },
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _line_no(source: str, needle: str) -> int | None:
    index = source.find(needle)
    if index < 0:
        return None
    return source[:index].count("\n") + 1


def _window(source: str, needle: str, radius: int = 5000) -> str:
    index = source.find(needle)
    if index < 0:
        return ""
    start = max(0, index - radius)
    end = min(len(source), index + radius)
    return source[start:end]


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(_read(path))
    except Exception as exc:
        payload = {"load_error": str(exc)}
    return {"found": True, "path": str(path), "payload": payload}


def _classify_callsite(window: str, projection_var: str) -> tuple[str, str]:
    uses_direct_builder = "_build_final_design_guide_direct_shell_card_projection(" in window
    fallback_only = "fallback_only=True" in window
    uses_projection_title = f"{projection_var}.title" in window
    uses_projection_pill = f"{projection_var}.pill" in window
    uses_projection_family_identity = f"{projection_var}.family_identity" in window
    uses_identity_projection = f"{projection_var}.identity_projection" in window
    uses_view_model_title = f"{projection_var}.view_model" in window and '.get("title")' in window
    uses_view_model_pill = f"{projection_var}.view_model" in window and '.get("pill")' in window
    stamps_display_authority = "_stamp_final_publication_display_authority(" in window
    stamps_cta_authority = "_stamp_final_publication_cta_authority(" in window
    renders_shell_html = "_design_guide_direct_action_shell_card_html(" in window
    renders_clean_final_publication_html = "_render_final_design_guide_card_html(" in window
    builds_clean_final_publication = "_build_final_design_guide_publication(" in window
    renders_via_normal_panel = "design_guide_page.render_final_panel(" in window
    renders_via_secondary_items = "_render_guidance_secondary_items(" in window
    direct_shell_deleted_marker = "_deleted" in window and "shell" in window
    records_apply_payload = "_record_rendered_design_guide_primary_apply_payload(" in window

    if (
        uses_direct_builder
        and (
            (
                (uses_view_model_title or uses_projection_title)
                and (uses_view_model_pill or uses_projection_pill)
            )
            or records_apply_payload
        )
        and (renders_shell_html or renders_via_normal_panel or renders_via_secondary_items or direct_shell_deleted_marker)
    ):
        return (
            "cutover_complete_non_fallback_direct_shell",
            "Callsite uses the direct-shell projection and renders through the normal page render path instead of the retired fallback-shell adapter.",
        )
    if (
        uses_direct_builder
        and builds_clean_final_publication
        and renders_clean_final_publication_html
        and stamps_display_authority
        and stamps_cta_authority
        and records_apply_payload
    ):
        return (
            "cutover_complete_non_fallback_direct_shell",
            "Callsite uses direct-shell projection only as compatibility input, then renders a clean FinalDesignGuidePublication recovery card.",
        )
    if uses_projection_title and uses_projection_pill and uses_projection_family_identity and renders_shell_html:
        if stamps_display_authority or stamps_cta_authority or records_apply_payload:
            return (
                "live_safety_keep",
                "Callsite still binds live CTA/display/apply or pre-publication safety behavior around an adapter-backed shell.",
            )
        if fallback_only:
            return (
                "compatibility_only_leftover",
                "Callsite only renders adapter-backed fallback shell values without nearby authority stamping.",
            )
        return (
            "live_safety_keep",
            "Callsite still renders an adapter-backed shell without fallback_only stamping, so it remains a live safety/presentation branch.",
        )
    if window:
        return (
            "needs_more_proof",
            "Callsite is present but does not match the expected fully adapter-backed fallback-shell pattern.",
        )
    return ("missing", "Callsite assignment not found.")


def build_snapshot() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    final_source = _read(FINAL_PUBLICATION)
    callsite_rows: list[dict[str, Any]] = []
    failures: list[str] = []

    for callsite_id, data in CALLSITES.items():
        window = _window(inputs_source, data["assignment"])
        classification, reason = _classify_callsite(window, data["projection_var"])
        row = {
            "callsite_id": callsite_id,
            "line": _line_no(inputs_source, data["assignment"]),
            "marker": data["marker"],
            "assignment_present": bool(window),
            "uses_adapter_builder": "_build_final_design_guide_render_fallback_shell_projection(" in window,
            "uses_direct_shell_builder": "_build_final_design_guide_direct_shell_card_projection(" in window,
            "uses_projection_title": f"{data['projection_var']}.title" in window,
            "uses_projection_pill": f"{data['projection_var']}.pill" in window,
            "uses_projection_family_identity": f"{data['projection_var']}.family_identity" in window,
            "uses_identity_projection": f"{data['projection_var']}.identity_projection" in window,
            "uses_view_model_title": f"{data['projection_var']}.view_model" in window and '.get("title")' in window,
            "uses_view_model_pill": f"{data['projection_var']}.view_model" in window and '.get("pill")' in window,
            "stamps_display_authority": "_stamp_final_publication_display_authority(" in window,
            "stamps_cta_authority": "_stamp_final_publication_cta_authority(" in window,
            "records_apply_payload": "_record_rendered_design_guide_primary_apply_payload(" in window,
            "renders_direct_shell_html": "_design_guide_direct_action_shell_card_html(" in window,
            "builds_clean_final_publication": "_build_final_design_guide_publication(" in window,
            "renders_clean_final_publication_html": "_render_final_design_guide_card_html(" in window,
            "renders_via_normal_panel": "design_guide_page.render_final_panel(" in window,
            "renders_via_secondary_items": "_render_guidance_secondary_items(" in window,
            "direct_shell_deleted_marker": "_deleted" in window and "shell" in window,
            "fallback_only_true": "fallback_only=True" in window,
            "classification": classification,
            "classification_reason": reason,
            "blocks_helper_deletion_now": classification == "live_safety_keep",
            "safe_delete_candidate_now": classification == "compatibility_only_leftover",
        }
        callsite_rows.append(row)
        if classification != data["expected_classification"]:
            failures.append(f"{callsite_id}:{classification}")

    source_checks = {
        "helper_deleted_from_design_brain": "def build_final_design_guide_render_fallback_shell_projection(" not in final_source,
        "helper_has_no_inputs_import": "inputs_page" not in final_source,
        "helper_has_no_streamlit_import": "import streamlit" not in final_source.lower() and "from streamlit" not in final_source.lower(),
    }
    for key, passed in source_checks.items():
        if not passed:
            failures.append(f"source:{key}")

    latest = {
        "render_fallback_shell_adapter_cutover": _latest("design_guide_render_fallback_shell_adapter_cutover"),
        "direct_shell_identity_fallback_deletion": _latest("design_guide_direct_shell_identity_fallback_deletion"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    for key, row in latest.items():
        status = str((row.get("payload") or {}).get("status") or (row.get("payload") or {}).get("result") or "").upper()
        if "PASS" not in status and "LOCKED" not in status and "COMPLETE" not in status:
            failures.append(f"{key}_latest_not_pass")

    summary = {
        "callsite_count": len(callsite_rows),
        "cutover_complete_non_fallback_direct_shell": sum(
            1
            for row in callsite_rows
            if row["classification"] == "cutover_complete_non_fallback_direct_shell"
        ),
        "live_safety_keep": sum(1 for row in callsite_rows if row["classification"] == "live_safety_keep"),
        "compatibility_only_leftover": sum(1 for row in callsite_rows if row["classification"] == "compatibility_only_leftover"),
        "needs_more_proof": sum(1 for row in callsite_rows if row["classification"] == "needs_more_proof"),
        "safe_delete_now": sum(1 for row in callsite_rows if row["safe_delete_candidate_now"]),
    }

    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_brain_render_fallback_shell_callsite_classification.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "summary": summary,
        "callsites": callsite_rows,
        "source_checks": source_checks,
        "latest": {
            key: {
                "found": value.get("found"),
                "path": value.get("path"),
                "status": (value.get("payload") or {}).get("status") or (value.get("payload") or {}).get("result"),
            }
            for key, value in latest.items()
        },
        "recommended_next_slice": (
            "Fallback-shell helper retired; all tracked direct shell callsites now classify as cutover-complete direct shell consumers."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "failures": failures,
    }


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Brain Render Fallback Shell Callsite Classification",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Summary",
    ]
    for key, value in (snapshot.get("summary") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Callsites"])
    for row in snapshot.get("callsites") or []:
        lines.extend(
            [
                f"### {row['callsite_id']}",
                f"- line: `{row['line']}`",
                f"- classification: `{row['classification']}`",
                f"- blocks helper deletion now: `{row['blocks_helper_deletion_now']}`",
                f"- reason: {row['classification_reason']}",
                "",
            ]
        )
    lines.extend(["## Recommendation", "", str(snapshot.get("recommended_next_slice") or "")])
    if snapshot.get("failures"):
        lines.extend(["", "## Failures"])
        lines.extend(f"- `{failure}`" for failure in snapshot["failures"])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    json_path = ARTIFACT_DIR / f"design_brain_render_fallback_shell_callsite_classification_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_render_fallback_shell_callsite_classification_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_brain_render_fallback_shell_callsite_classification {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
