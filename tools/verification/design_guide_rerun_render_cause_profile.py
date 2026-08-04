"""Aggregate browser/live rerun and render-cause profile for Design Guide smoothness.

Audit-only. This composes the focused browser/live measurements around loading
gap, scroll lock, first paint, top-gap layout, and Design Guide render
eligibility. It does not change product behaviour.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

REQUIRED_ARTIFACTS = {
    "loading_scroll_lock": "design_guide_loading_scroll_lock_profile",
    "first_paint_layout_gap": "design_guide_first_paint_layout_gap_profile",
    "top_gap_layout": "design_guide_top_gap_layout",
    "live_render_gate": "design_guide_live_render_gate_audit",
    "stable_rerun_shell_visibility": "design_guide_stable_rerun_shell_visibility",
    "next_smoothness_hotspot": "design_guide_next_smoothness_hotspot_audit",
    "design_guide_independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "path": str(path), "status": payload.get("status"), "payload": payload}


def _classify(artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    render_gate = dict(artifacts["live_render_gate"].get("payload") or {})
    render_classification = dict(render_gate.get("classification") or {})
    first_paint = dict(artifacts["first_paint_layout_gap"].get("payload") or {})
    stable_shell = dict(artifacts["stable_rerun_shell_visibility"].get("payload") or {})
    stable_shell_classification = dict(stable_shell.get("classification") or {})
    next_hotspot = dict(artifacts["next_smoothness_hotspot"].get("payload") or {})
    largest_gap = dict(first_paint.get("largest_gap") or {})
    first_slice = dict(next_hotspot.get("first_recommended_next_slice") or {})

    render_gate_blockers = list(render_classification.get("blockers") or [])
    render_gate_diagnosis = render_classification.get("diagnosis")
    page_gate_blocks_slot = render_gate_diagnosis == "page_level_actions_or_loads_gate_prevents_design_guide_slot"
    real_dg_created = bool(render_classification.get("real_design_guide_created"))
    stable_shell_text_visible = bool(render_classification.get("stable_rerun_shell_visible"))
    stable_shell_layout_visible = bool(stable_shell_classification.get("layout_visible"))
    stable_shell_hidden_dom_only = (
        stable_shell_classification.get("diagnosis") == "STABLE_RERUN_SHELL_HIDDEN_DOM_TEXT_ONLY"
    )
    stable_shell_visible = bool(stable_shell_layout_visible or (stable_shell_text_visible and not stable_shell_hidden_dom_only))
    start_shell_visible = bool(render_classification.get("start_your_design_visible"))

    gap_px = largest_gap.get("px")
    try:
        gap_px_num = float(gap_px)
    except (TypeError, ValueError):
        gap_px_num = None

    likely_primary_cause = "UNKNOWN"
    if page_gate_blocks_slot:
        likely_primary_cause = "PAGE_LEVEL_RENDER_ELIGIBILITY_GATE"
    elif stable_shell_visible or start_shell_visible:
        likely_primary_cause = "SHELL_VISIBLE_DURING_STABLE_RERUN"
    elif gap_px_num is not None and gap_px_num >= 320:
        likely_primary_cause = "LARGE_LAYOUT_GAP"
    elif first_slice.get("area"):
        likely_primary_cause = "RERUN_TRIGGER_PROFILING_NEEDED"

    return {
        "likely_primary_cause": likely_primary_cause,
        "page_gate_blocks_design_guide_slot": page_gate_blocks_slot,
        "real_design_guide_created": real_dg_created,
        "stable_rerun_shell_visible": stable_shell_visible,
        "stable_rerun_shell_text_detected": stable_shell_text_visible,
        "stable_rerun_shell_layout_visible": stable_shell_layout_visible,
        "stable_rerun_shell_hidden_dom_only": stable_shell_hidden_dom_only,
        "start_your_design_visible": start_shell_visible,
        "render_gate_blockers": render_gate_blockers,
        "largest_gap_px": gap_px_num,
        "largest_gap_id": largest_gap.get("id"),
        "next_hotspot_area": first_slice.get("area"),
        "next_hotspot_classification": first_slice.get("classification"),
        "smallest_next_slice": (
            "Add a trace-only render eligibility adapter beside the page-level actions/load gate, "
            "then prove which selected-family/blocker/final-publication states should create the real "
            "Design Guide slot even when action/load inputs are zero."
            if page_gate_blocks_slot
            else "Add rerun-cause markers around Apply, batch controls, constraints info, and Design Guide panel render."
        ),
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Rerun/Render Cause Profile",
        "",
        f"- Status: `{payload['status']}`",
        f"- Likely primary cause: `{payload['classification']['likely_primary_cause']}`",
        f"- Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Classification",
        "",
        "```json",
        json.dumps(payload["classification"], indent=2, sort_keys=True),
        "```",
        "",
        "## Supporting Artifacts",
        "",
        "| Artifact | Status | Path |",
        "|---|---|---|",
    ]
    for key, row in payload["supporting_artifacts"].items():
        lines.append(f"| {_escape_md(key)} | {_escape_md(row.get('status'))} | {_escape_md(row.get('path'))} |")
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Next Safe Slice", "", payload["classification"]["smallest_next_slice"]])
    return "\n".join(lines) + "\n"


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    artifacts = {key: _latest(prefix) for key, prefix in REQUIRED_ARTIFACTS.items()}
    classification = _classify(artifacts)
    failures = [
        f"{key}_not_passed"
        for key, row in artifacts.items()
        if row.get("status") != "PASS"
    ]
    if classification["likely_primary_cause"] == "UNKNOWN":
        failures.append("unknown_primary_cause")

    payload = {
        "status": "PASS" if not failures else "FAIL",
        "schema": "design_guide_rerun_render_cause_profile.v1",
        "created_at": stamp,
        "product_behaviour_changed": False,
        "classification": classification,
        "supporting_artifacts": {
            key: {"found": row.get("found"), "status": row.get("status"), "path": row.get("path")}
            for key, row in artifacts.items()
        },
        "failures": failures,
        "snapshot_hash": _stable_hash(
            {
                "classification": classification,
                "supporting_artifacts": {
                    key: row.get("path") for key, row in artifacts.items()
                },
            }
        ),
    }
    json_path = ARTIFACT_DIR / f"design_guide_rerun_render_cause_profile_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_rerun_render_cause_profile_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_rerun_render_cause_profile {payload['status']}")
    print(f"primary_cause={classification['likely_primary_cause']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print(f"failures={json.dumps(failures, sort_keys=True)}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
