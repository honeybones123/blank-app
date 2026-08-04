"""Readiness snapshot for remaining summary/card layout-shift work.

Proof-only. This verifier consumes the latest browser/live smoothness profile,
layout source-node snapshot, first-paint skeleton proof, and summary height
readiness proof to decide whether a narrow summary/card reservation patch is
justified. It does not change product behavior.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
SUMMARY_SOURCE = ROOT / "ui" / "summary_sections.py"


def _latest(prefix: str) -> tuple[Path | None, dict[str, Any]]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return None, {}
    path = paths[-1]
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return path, {"status": "UNREADABLE", "error": str(exc)}


def _source_line(source: str, token: str) -> int | None:
    for line_no, line in enumerate(source.splitlines(), start=1):
        if token in line:
            return line_no
    return None


def _scenario_shift_rows(profile: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario in list(profile.get("scenarios") or []):
        if not isinstance(scenario, dict) or scenario.get("skipped"):
            continue
        layout = dict(scenario.get("layout") or {})
        rows.append(
            {
                "scenario_id": scenario.get("scenario_id"),
                "layout_shift_total": float(layout.get("layout_shift_total") or 0.0),
                "layout_shift_cumulative_initial": layout.get("layout_shift_cumulative_initial"),
                "layout_shift_cumulative_final": layout.get("layout_shift_cumulative_final"),
                "summary_cards_ms": dict(dict(scenario.get("milestones") or {}).get("summary_cards") or {}).get("elapsed_ms"),
                "rendered_design_guide_card_ms": dict(dict(scenario.get("milestones") or {}).get("rendered_design_guide_card") or {}).get("elapsed_ms"),
            }
        )
    return rows


def _build() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    smooth_path, smooth = _latest("design_guide_browser_live_smoothness_profile")
    source_node_path, source_node = _latest("design_guide_streamlit_layout_shift_source_node")
    skeleton_path, skeleton = _latest("design_guide_first_paint_layout_skeleton_implementation")
    summary_height_path, summary_height = _latest("design_guide_summary_first_paint_shell_height_readiness")
    gap_path, gap = _latest("design_guide_first_paint_layout_gap_audit")

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    summary_source = SUMMARY_SOURCE.read_text(encoding="utf-8", errors="replace") if SUMMARY_SOURCE.exists() else ""

    top_hotspot = dict((smooth.get("top_hotspots") or smooth.get("all_hotspot_scores") or [{}])[0] or {})
    source_summary = dict(source_node.get("summary") or {})
    summary_height_summary = dict(summary_height.get("summary") or {})
    gap_summary = dict(gap.get("gap_profile_summary") or {})

    scenario_rows = _scenario_shift_rows(smooth)
    max_shift = max((float(row.get("layout_shift_total") or 0.0) for row in scenario_rows), default=0.0)
    post_apply_shift = max(
        (
            float(row.get("layout_shift_total") or 0.0)
            for row in scenario_rows
            if str(row.get("scenario_id") or "") == "post_click_apply"
        ),
        default=0.0,
    )

    source_checks = {
        "summary_card_stack_containment_present": bool(
            re.search(r"\.summary-card-stack\s*\{[^}]*contain:\s*layout\s+paint", summary_source, re.DOTALL)
        ),
        "summary_check_card_containment_present": bool(
            re.search(r"\.summary-check-card\s*\{[^}]*contain:\s*layout\s+paint", summary_source, re.DOTALL)
        ),
        "first_paint_shell_present": "inputs-first-paint-shell" in inputs_source,
        "first_paint_shell_has_reserved_height": "_first_paint_shell_min_height" in inputs_source
        and "__FIRST_PAINT_MIN_HEIGHT__" in inputs_source,
        "summary_skeleton_rows_present": inputs_source.count("summary-skeleton-row") >= 4,
        "summary_html_reuse_present": "_final_publication_summary_card_html_cache" in inputs_source,
        "summary_html_reuse_debug_present": "_final_publication_summary_card_html_bypass_debug" in inputs_source,
        "first_paint_shell_line": _source_line(inputs_source, "inputs-first-paint-shell"),
        "summary_stack_render_line": _source_line(inputs_source, "summary-card-stack"),
    }

    existing_guards_complete = bool(
        source_checks["summary_card_stack_containment_present"]
        and source_checks["summary_check_card_containment_present"]
        and source_checks["first_paint_shell_present"]
        and source_checks["first_paint_shell_has_reserved_height"]
        and source_checks["summary_skeleton_rows_present"]
        and source_checks["summary_html_reuse_present"]
    )
    material_height_mismatch = not bool(
        (summary_height.get("decision") or summary_height_summary.get("decision")) == "NO_MATERIAL_HEIGHT_MISMATCH"
    )
    fixed_gap_resolved = bool(
        gap.get("diagnosis") == "measured_batch_gap_resolved"
        and int(gap_summary.get("blank_excessive_gap_count") or 0) == 0
    )
    source_target = str(source_summary.get("candidate_patch_target") or "")
    top_is_layout = str(top_hotspot.get("name") or "") == "layout placeholder/first-paint gap"

    ready_for_patch = bool(
        top_is_layout
        and source_target == "summary_first_paint_or_cards"
        and not existing_guards_complete
    )
    if ready_for_patch:
        decision = "READY_FOR_NARROW_SUMMARY_LAYOUT_PATCH"
        next_slice = "Add only the missing summary/card reservation guard identified by source_checks."
    elif top_is_layout and existing_guards_complete and fixed_gap_resolved and not material_height_mismatch:
        decision = "NO_SAFE_SUMMARY_LAYOUT_PATCH_FROM_CURRENT_EVIDENCE"
        next_slice = (
            "Do not add more summary/card CSS from current evidence. Run a focused browser/live "
            "measurement of initial blank-to-summary mount timing or inspect Streamlit page-content "
            "slot clearing before product changes."
        )
    else:
        decision = "NEEDS_FRESH_BROWSER_LIVE_EVIDENCE"
        next_slice = "Refresh broad smoothness, source-node, gap, and summary-height proofs before patching."

    failures: list[str] = []
    for name, payload in {
        "smoothness_profile": smooth,
        "source_node": source_node,
        "skeleton": skeleton,
        "summary_height": summary_height,
        "gap": gap,
    }.items():
        if payload.get("status") != "PASS":
            failures.append(f"{name}_not_pass")
    if decision == "NEEDS_FRESH_BROWSER_LIVE_EVIDENCE":
        failures.append("fresh_browser_live_evidence_needed")

    return {
        "schema": "design_guide_summary_layout_shift_readiness_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "product_behaviour_changed": False,
        "decision": decision,
        "top_hotspot": top_hotspot,
        "source_node_summary": {
            "candidate_patch_target": source_target,
            "layout_shift_total": source_summary.get("layout_shift_total"),
            "top_owner_by_value": source_summary.get("top_owner_by_value"),
            "fixed_gap_observed": source_summary.get("fixed_gap_observed"),
        },
        "scenario_shift_rows": scenario_rows,
        "max_layout_shift_total": max_shift,
        "post_apply_layout_shift_total": post_apply_shift,
        "existing_guards_complete": existing_guards_complete,
        "material_height_mismatch": material_height_mismatch,
        "fixed_gap_resolved": fixed_gap_resolved,
        "source_checks": source_checks,
        "artifacts": {
            "smoothness_profile": str(smooth_path) if smooth_path else None,
            "source_node": str(source_node_path) if source_node_path else None,
            "skeleton": str(skeleton_path) if skeleton_path else None,
            "summary_height": str(summary_height_path) if summary_height_path else None,
            "gap": str(gap_path) if gap_path else None,
        },
        "next_slice": next_slice,
        "failures": failures,
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_summary_layout_shift_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_summary_layout_shift_readiness_{stamp}.md"
    lines = [
        "# Design Guide Summary Layout Shift Readiness",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{payload['decision']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Summary",
        "",
        f"- Existing guards complete: `{payload['existing_guards_complete']}`",
        f"- Material height mismatch: `{payload['material_height_mismatch']}`",
        f"- Fixed gap resolved: `{payload['fixed_gap_resolved']}`",
        f"- Max layout shift total: `{payload['max_layout_shift_total']}`",
        f"- Post-Apply layout shift total: `{payload['post_apply_layout_shift_total']}`",
        "",
        "## Source Checks",
        "",
    ]
    for key, value in dict(payload["source_checks"]).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Next Slice", "", str(payload["next_slice"]), ""])
    if payload["failures"]:
        lines.extend(["## Failures", "", "```json", json.dumps(payload["failures"], indent=2), "```", ""])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build()
    json_path, md_path = _write(payload)
    print(f"design_guide_summary_layout_shift_readiness {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if payload["failures"]:
        print("failures=" + json.dumps(payload["failures"]))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
