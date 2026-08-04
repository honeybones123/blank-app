"""No-actions landing first-paint reservation readiness snapshot.

Proof-only. This verifies the current smoothness risk is a no-actions landing
card height transition, not Design Brain publication churn. It does not change
layout, wording, CTA/apply semantics, family runtimes, or engineering behavior.
"""

from __future__ import annotations

from datetime import datetime
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
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
    except Exception:
        return path, {}


def _first_paint_shell(source: str) -> str:
    match = re.search(
        r'<div class="inputs-first-paint-shell".*?</div>\s*""",',
        source,
        flags=re.DOTALL,
    )
    return match.group(0) if match else ""


def _source_checks(source: str) -> dict[str, Any]:
    shell = _first_paint_shell(source)
    landing_fn = source[
        source.find("def inputs_show_landing_dashboard() -> bool:"):
        source.find("def inputs_has_design_actions_or_loads() -> bool:")
    ]
    return {
        "first_paint_shell_exists": bool(shell),
        "summary_skeleton_rows_present": shell.count("summary-skeleton-row") >= 4,
        "current_compact_summary_height": "min-height:11.5rem" in shell,
        "landing_card_exists": "Start Your Design" in source and "inputs-landing-wrap" in source,
        "landing_gate_exists": "def inputs_show_landing_dashboard() -> bool:" in source,
        "landing_gate_is_no_actions_based": all(
            token in landing_fn
            for token in ("no_design_actions", "no_loads", "return not capacity_context_matches")
        ),
        "no_existing_landing_reservation": "inputs-first-paint-shell landing" not in shell
        and "inputs-first-paint-landing-shell" not in shell,
        "shell_scope_has_no_design_brain_truth": all(
            token not in shell
            for token in (
                "FinalDesignGuidePublication",
                "button_contract",
                "apply_resolved_candidate",
                "DesignGuideController",
            )
        ),
    }


def _classify(layout_path: Path | None, layout: dict[str, Any], source_checks: dict[str, Any]) -> dict[str, Any]:
    layout_cls = dict(layout.get("classification") or {})
    snapshots = list(layout.get("snapshots") or [])
    shift_sources = " ".join(
        str(source.get("text") or "")
        for snap in snapshots
        for entry in list(snap.get("layout_shift_entries") or [])
        for source in list(entry.get("sources") or [])
    )
    max_shift = float(layout_cls.get("max_layout_shift_total") or 0.0)
    risks = set(layout_cls.get("risks") or [])
    readiness_checks = {
        "layout_stability_artifact_found": layout_path is not None,
        "layout_snapshot_passed": layout.get("status") == "PASS",
        "high_layout_shift_observed": "high_layout_shift" in risks or max_shift > 0.15,
        "start_your_design_in_shift_sources": "Start Your Design" in shift_sources,
        "batch_workspace_in_shift_sources": "Batch design workspace" in shift_sources,
        "not_blank_gap_problem": int(layout_cls.get("max_batch_to_design_guide_gap_px") or 0) == 0,
        **{f"source_{key}": bool(value) for key, value in source_checks.items()},
    }
    ready = all(readiness_checks.values())
    return {
        "status": "PASS" if ready else "FAIL",
        "readiness": "READY_FOR_NO_ACTIONS_LANDING_FIRST_PAINT_RESERVATION" if ready else "NOT_READY",
        "max_layout_shift_total": max_shift,
        "layout_artifact": str(layout_path) if layout_path else None,
        "readiness_checks": readiness_checks,
        "recommended_next_slice": (
            "Add a no-actions landing-aware first-paint shell height while preserving the existing final landing card."
            if ready
            else "Refresh layout stability and inspect first-paint/landing source evidence before changing layout."
        ),
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_no_actions_landing_first_paint_reservation_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_no_actions_landing_first_paint_reservation_readiness_{stamp}.md"
    lines = [
        "# No-Actions Landing First-Paint Reservation Readiness",
        "",
        f"Status: `{payload['status']}`",
        f"Readiness: `{payload['classification']['readiness']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(
        f"- `{key}`: `{value}`"
        for key, value in payload["classification"]["readiness_checks"].items()
    )
    lines.extend(["", "## Next Slice", "", payload["classification"]["recommended_next_slice"], ""])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    layout_path, layout = _latest("design_guide_browser_live_layout_stability")
    classification = _classify(layout_path, layout, _source_checks(source))
    payload = {
        "schema": "design_guide_no_actions_landing_first_paint_reservation_readiness.v1",
        "created_at": _stamp(),
        "status": classification["status"],
        "classification": classification,
        "product_behaviour_changed": False,
    }
    json_path, md_path = _write(payload)
    print(f"design_guide_no_actions_landing_first_paint_reservation_readiness {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
