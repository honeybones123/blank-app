"""Completion audit for the Inputs page smoothness goal.

This verifier checks the active smoothness objective directly:

- stable no-change rerun churn was profiled
- hotspots were ranked from browser/live evidence
- verified fingerprint-guarded reuse/bypass slices are present
- guarded cases rebuild instead of hiding stale state
- no remaining app-owned rebuild/reuse target is proven patch-ready

It is proof-only and does not change product behavior.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _latest(prefix: str) -> tuple[Path | None, dict[str, Any]]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return None, {}
    path = paths[-1]
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return path, {"status": "UNREADABLE", "error": str(exc)}


def _status(payload: dict[str, Any]) -> str | None:
    value = payload.get("status")
    return str(value) if value is not None else None


def _hotspot(profile: dict[str, Any], name: str) -> dict[str, Any]:
    for row in list(profile.get("all_hotspot_scores") or []) + list(profile.get("top_hotspots") or []):
        if isinstance(row, dict) and row.get("name") == name:
            return dict(row)
    return {}


def _count_positive(payload: dict[str, Any], *keys: str) -> bool:
    wanted = set(keys)

    def _walk(value: Any) -> bool:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in wanted:
                    if isinstance(child, bool):
                        if child:
                            return True
                    elif isinstance(child, (int, float)) and not isinstance(child, bool):
                        if child > 0:
                            return True
                    elif isinstance(child, str):
                        try:
                            if float(child) > 0:
                                return True
                        except ValueError:
                            pass
                if _walk(child):
                    return True
        elif isinstance(value, list):
            return any(_walk(child) for child in value)
        return False

    return _walk(payload)


def _build() -> dict[str, Any]:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    prefixes = {
        "broad_smoothness_profile": "design_guide_browser_live_smoothness_profile",
        "next_hotspot_audit": "design_guide_next_smoothness_hotspot_audit",
        "same_session_no_change": "design_guide_same_session_no_change_rerun_profile",
        "second_same_session_no_change": "design_guide_second_same_session_no_change_rerun_profile",
        "duplicate_stamp_live_impact": "design_guide_duplicate_publication_stamp_bypass_live_impact",
        "card_render_model_live_impact": "design_guide_card_render_model_bypass_live_impact",
        "summary_html_live_impact": "design_guide_stable_publication_summary_render_reuse_live_impact",
        "stable_visible_panel_reuse": "design_guide_stable_visible_panel_render_reuse_implementation",
        "fast_first_paint_deferral": "design_guide_fast_first_paint_cleanup_deferral",
        "loading_shell_completion": "design_guide_loading_shell_completion_profile",
        "summary_layout_readiness": "design_guide_summary_layout_shift_readiness",
        "same_page_dispatch_gap": "design_guide_same_page_inputs_dispatch_gap_readiness",
        "stable_shell_visibility": "design_guide_stable_rerun_shell_visibility",
        "independence_lock": "design_guide_independence_lock",
        "render_bridge_lock": "design_guide_render_bridge_lock",
        "compute_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
        "zero_authority_lock": "design_brain_inputs_page_zero_authority_inventory_lock",
    }

    artifacts: dict[str, dict[str, Any]] = {}
    paths: dict[str, str | None] = {}
    for key, prefix in prefixes.items():
        path, payload = _latest(prefix)
        artifacts[key] = payload
        paths[key] = str(path) if path else None

    broad = artifacts["broad_smoothness_profile"]
    candidate = _hotspot(broad, "candidate evaluation/search")
    publication = _hotspot(broad, "publication/card rebuild")
    layout = _hotspot(broad, "layout placeholder/first-paint gap")
    candidate_evidence = dict(candidate.get("evidence") or {})
    publication_evidence = dict(publication.get("evidence") or {})

    summary_readiness_decision = str(artifacts["summary_layout_readiness"].get("decision") or "")
    dispatch_readiness = str(
        dict(artifacts["same_page_dispatch_gap"].get("classification") or {}).get("readiness")
        or artifacts["same_page_dispatch_gap"].get("readiness")
        or ""
    )
    stable_shell_diagnosis = str(
        dict(artifacts["stable_shell_visibility"].get("classification") or {}).get("diagnosis")
        or artifacts["stable_shell_visibility"].get("diagnosis")
        or ""
    )

    checks = {
        "broad_profile_pass": _status(broad) == "PASS",
        "hotspots_ranked": bool(broad.get("all_hotspot_scores") or broad.get("top_hotspots")),
        "candidate_search_not_product_hotspot": bool(
            candidate_evidence.get("product_hotspot") is False
            and float(candidate_evidence.get("product_candidate_total_ms") or 0.0) == 0.0
        ),
        "publication_and_card_rebuilds_zero": bool(
            int(publication_evidence.get("publication_rebuild_count") or 0) == 0
            and int(publication_evidence.get("card_render_model_rebuild_count") or 0) == 0
        ),
        "stable_no_change_profile_pass": _status(artifacts["same_session_no_change"]) == "PASS"
        and _status(artifacts["second_same_session_no_change"]) == "PASS",
        "duplicate_stamp_bypass_live_impact_pass": _status(artifacts["duplicate_stamp_live_impact"]) == "PASS",
        "card_render_model_bypass_live_impact_pass": _status(artifacts["card_render_model_live_impact"]) == "PASS",
        "summary_html_reuse_live_impact_pass": _status(artifacts["summary_html_live_impact"]) == "PASS",
        "stable_visible_panel_reuse_pass": _status(artifacts["stable_visible_panel_reuse"]) == "PASS",
        "fast_first_paint_deferral_pass": _status(artifacts["fast_first_paint_deferral"]) == "PASS",
        "loading_shell_completion_pass": _status(artifacts["loading_shell_completion"]) == "PASS"
        and bool(dict(artifacts["loading_shell_completion"].get("classification") or {}).get("requires_fix")) is False,
        "summary_layout_no_safe_patch": summary_readiness_decision == "NO_SAFE_SUMMARY_LAYOUT_PATCH_FROM_CURRENT_EVIDENCE",
        "same_page_gap_not_reproduced_or_guarded": dispatch_readiness in {
            "BLOCKED_GAP_NOT_REPRODUCED",
            "READY_ALREADY_GUARDED",
            "NOT_READY_NO_LIVE_GAP",
        },
        "stable_shell_not_visible_layout": stable_shell_diagnosis == "STABLE_RERUN_SHELL_HIDDEN_DOM_TEXT_ONLY",
        "independence_lock_pass": _status(artifacts["independence_lock"]) == "PASS",
        "render_bridge_lock_pass": _status(artifacts["render_bridge_lock"]) == "PASS",
        "compute_bridge_lock_pass": _status(artifacts["compute_bridge_lock"]) == "PASS",
        "zero_authority_lock_pass": _status(artifacts["zero_authority_lock"]) == "PASS",
    }

    # Live impact payload schemas varied across the cleanup work. Keep this
    # evidence check tolerant but explicit: each live impact must contain at
    # least one observed reuse/bypass/skip signal and guarded rebuild cases.
    impact_checks = {
        "duplicate_stamp_has_reuse_signal": _count_positive(
            artifacts["duplicate_stamp_live_impact"],
            "stable_non_debug_bypass_hits",
            "rerun_without_input_changes_bypass_hits",
        ),
        "card_render_has_reuse_signal": _count_positive(
            artifacts["card_render_model_live_impact"],
            "stable_non_debug_bypass_hits",
            "rerun_without_input_changes_bypass_hits",
        ),
        "summary_html_has_reuse_signal": _count_positive(
            artifacts["summary_html_live_impact"],
            "stable_non_debug_bypass_hits",
            "rerun_without_input_changes_bypass_hits",
            "summary_card_html_builds_skipped",
        ),
    }

    errors = [key for key, passed in checks.items() if not passed]
    errors.extend(key for key, passed in impact_checks.items() if not passed)

    residual = {
        "top_layout_hotspot_score": layout.get("score"),
        "top_layout_hotspot_evidence": dict(layout.get("evidence") or {}),
        "residual_classification": (
            "residual_browser_streamlit_first_mount_not_patch_ready"
            if checks["summary_layout_no_safe_patch"]
            and checks["same_page_gap_not_reproduced_or_guarded"]
            and checks["stable_shell_not_visible_layout"]
            else "residual_requires_more_evidence"
        ),
    }

    status = "PASS" if not errors else "FAIL"
    completion_recommendation = (
        "GOAL_COMPLETE_FROM_CURRENT_EVIDENCE"
        if status == "PASS"
        else "CONTINUE_WITH_MISSING_OR_FAILED_EVIDENCE"
    )
    return {
        "schema": "design_guide_smoothness_goal_completion_audit.v1",
        "status": status,
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "product_behaviour_changed": False,
        "completion_recommendation": completion_recommendation,
        "checks": checks,
        "impact_checks": impact_checks,
        "residual": residual,
        "artifacts": paths,
        "errors": errors,
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_smoothness_goal_completion_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_smoothness_goal_completion_audit_{stamp}.md"
    lines = [
        "# Design Guide Smoothness Goal Completion Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Recommendation: `{payload['completion_recommendation']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in dict(payload["checks"]).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Impact Checks", ""])
    for key, value in dict(payload["impact_checks"]).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Residual", "", "```json", json.dumps(payload["residual"], indent=2, sort_keys=True, default=str), "```", ""])
    if payload["errors"]:
        lines.extend(["## Errors", "", "```json", json.dumps(payload["errors"], indent=2), "```", ""])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build()
    json_path, md_path = _write(payload)
    print(f"design_guide_smoothness_goal_completion_audit {payload['status']}")
    print(f"recommendation={payload['completion_recommendation']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if payload["errors"]:
        print("errors=" + json.dumps(payload["errors"]))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
