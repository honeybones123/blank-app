"""Audit the first-paint layout gap around Inputs/Batch/Design Guide.

Proof-only. This consumes the latest browser/live smoothness profile and source
layout markers to identify whether the visible jump is caused by Design Brain
truth churn or by page layout reservation.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"


def _latest(prefix: str) -> tuple[Path | None, dict[str, Any]]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return None, {}
    path = paths[-1]
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return path, {}


def _source_find(source: str, token: str) -> dict[str, Any]:
    for line_no, line in enumerate(source.splitlines(), start=1):
        if token in line:
            return {"found": True, "line": line_no, "token": token}
    return {"found": False, "line": None, "token": token}


def _layout_shift_summary(profile: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for scenario in list(profile.get("scenarios") or []):
        if not isinstance(scenario, dict) or scenario.get("skipped"):
            continue
        layout = dict(scenario.get("layout") or {})
        entries = list(layout.get("layout_shift_entries_tail") or [])
        dominant = max(entries, key=lambda row: float(row.get("value") or 0.0), default={})
        source_texts = []
        for source in list(dominant.get("sources") or []):
            text = str(dict(source).get("text") or "").strip()
            if text:
                source_texts.append(text[:140])
        rows.append(
            {
                "scenario_id": scenario.get("scenario_id"),
                "layout_shift_total": float(layout.get("layout_shift_total") or 0.0),
                "dominant_shift_value": float(dominant.get("value") or 0.0),
                "dominant_shift_start_ms": dominant.get("startTime"),
                "dominant_sources": source_texts,
            }
        )
    max_shift = max((row["layout_shift_total"] for row in rows), default=0.0)
    dominant_source_joined = " | ".join(
        text for row in rows for text in row.get("dominant_sources", [])
    )
    return {
        "scenario_rows": rows,
        "max_layout_shift_total": max_shift,
        "dominant_mentions_batch_design": "Batch design" in dominant_source_joined,
        "dominant_mentions_design_guide": "Design Guide" in dominant_source_joined,
        "dominant_mentions_design_mode": "Design mode" in dominant_source_joined,
        "dominant_mentions_active_set": "Active set" in dominant_source_joined,
    }


def _build() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    profile_path, profile = _latest("design_guide_browser_live_smoothness_profile")
    gap_profile_path, gap_profile = _latest("design_guide_first_paint_layout_gap_profile")
    shift = _layout_shift_summary(profile)
    gap_classification = dict(gap_profile.get("classification") or {})
    latest_snapshot = (list(gap_profile.get("snapshots") or []) or [{}])[-1]
    latest_gaps = dict(latest_snapshot.get("gaps") or {})
    result_to_batch_gap = dict(latest_gaps.get("result_band_to_batch_design") or {})
    blank_excessive_count = int(gap_classification.get("blank_excessive_gap_count") or 0)
    result_to_batch_px = int(result_to_batch_gap.get("px") or 0) if result_to_batch_gap.get("measured") else None
    source_checks = {
        "first_paint_shell_exists": _source_find(source, "inputs-first-paint-shell"),
        "first_paint_shell_currently_small": {
            "found": "Preparing current summary..." in source,
            "reason": "current shell is a compact message before final summary/check rows",
        },
        "summary_container_replaced_later": _source_find(source, "with summary_container.container():"),
        "batch_design_renders_before_dg_slot": {
            "found": source.find('st.markdown("### Batch design")') >= 0
            and source.find("design_guide_page.render_pre_widget_placeholder") >= 0
            and source.find('st.markdown("### Batch design")')
            < source.find("design_guide_page.render_pre_widget_placeholder"),
        },
        "design_guide_placeholder_has_min_height": _source_find(source, "min-height:10.5rem"),
    }
    measured_gap_resolved = bool(
        gap_profile.get("status") == "PASS"
        and result_to_batch_px is not None
        and result_to_batch_px <= 48
        and blank_excessive_count == 0
    )
    diagnosis = (
        "measured_batch_gap_resolved"
        if measured_gap_resolved
        else (
            "page_layout_reservation_gap"
            if shift["max_layout_shift_total"] >= 0.15
            and shift["dominant_mentions_batch_design"]
            and shift["dominant_mentions_design_guide"]
            else "insufficient_evidence"
        )
    )
    recommended_fix = (
        "Keep the compact first-paint summary shell and collapsed summary cards; no fixed blank "
        "Batch-design gap is currently measured."
        if measured_gap_resolved
        else (
            "Replace the compact first-paint summary message with a stable skeleton that reserves "
            "the final summary/check band height before Batch design and Design Guide render."
        )
    )
    errors: list[str] = []
    if not profile:
        errors.append("missing_browser_live_smoothness_profile")
    if diagnosis not in {"page_layout_reservation_gap", "measured_batch_gap_resolved"}:
        errors.append("layout_gap_diagnosis_not_proven")
    status = "PASS" if not errors else "FAIL"
    return {
        "schema": "design_guide_first_paint_layout_gap_audit.v1",
        "status": status,
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "product_behavior_changed": False,
        "profile_path": str(profile_path) if profile_path else None,
        "profile_status": profile.get("status"),
        "gap_profile_path": str(gap_profile_path) if gap_profile_path else None,
        "gap_profile_status": gap_profile.get("status"),
        "gap_profile_summary": {
            "result_band_to_batch_design_px": result_to_batch_px,
            "blank_excessive_gap_count": blank_excessive_count,
            "largest_gap": gap_classification.get("largest_gap"),
            "recommended_first_fix": gap_classification.get("recommended_first_fix"),
        },
        "layout_shift_summary": shift,
        "source_checks": source_checks,
        "diagnosis": diagnosis,
        "recommended_fix": recommended_fix,
        "errors": errors,
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_first_paint_layout_gap_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_first_paint_layout_gap_audit_{stamp}.md"
    lines = [
        "# Design Guide First-Paint Layout Gap Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Diagnosis: `{payload['diagnosis']}`",
        f"Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Layout Shift",
        "",
        f"- Max layout shift total: `{payload['layout_shift_summary']['max_layout_shift_total']}`",
        f"- Dominant mentions Batch design: `{payload['layout_shift_summary']['dominant_mentions_batch_design']}`",
        f"- Dominant mentions Design Guide: `{payload['layout_shift_summary']['dominant_mentions_design_guide']}`",
        f"- Dominant mentions Design mode: `{payload['layout_shift_summary']['dominant_mentions_design_mode']}`",
        "",
        "## Recommendation",
        "",
        payload["recommended_fix"],
        "",
    ]
    if payload["errors"]:
        lines.extend(["## Errors", "", "```json", json.dumps(payload["errors"], indent=2), "```", ""])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build()
    json_path, md_path = _write(payload)
    print(f"design_guide_first_paint_layout_gap_audit {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if payload["errors"]:
        print("errors=" + json.dumps(payload["errors"]))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
