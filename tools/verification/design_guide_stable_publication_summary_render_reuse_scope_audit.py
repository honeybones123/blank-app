"""Scope audit for stable-publication summary/render reuse.

Audit-only. The guarded reuse plan proved stable keys, but the implementation
boundary still matters: visible Streamlit summary output must continue to render
every rerun. This verifier classifies what may be reused safely before any live
bypass is added.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {
        "found": True,
        "status": status or "UNKNOWN",
        "path": str(path),
        "payload": payload,
    }


def _source_inventory(source: str) -> dict[str, Any]:
    return {
        "has_summary_pack_cache": all(
            token in source
            for token in (
                "summary_cache_miss",
                "_summary_cache_version",
                "_summary_cache_action_fp",
                "summary.overview_pack_rebuild",
            )
        ),
        "has_visible_summary_renderer": all(
            token in source
            for token in (
                "def _render_current_inputs_summary",
                "with summary_container.container():",
                'st.title("Inputs")',
                "render_summary_table(",
            )
        ),
        "has_summary_html_build_surface": all(
            token in source
            for token in (
                "summary_cards_html =",
                "build_summary_check_card_html(",
                "summary-card-stack",
                "st.markdown(f'<div class=\"summary-card-stack\">",
            )
        ),
        "has_existing_card_render_model_bypass": all(
            token in source
            for token in (
                "_FINAL_PUBLICATION_CARD_RENDER_MODEL_CACHE_KEY",
                "card_render_model_bypassed",
                "final_publication_display_hash",
            )
        ),
        "has_debug_force_patterns": all(
            token in source
            for token in (
                "_design_guide_sidebar_debug_enabled()",
                "debug_force_rebuild",
            )
        ),
    }


def _classifications() -> list[dict[str, Any]]:
    return [
        {
            "surface": "summary pack rebuild",
            "classification": "already guarded cache",
            "safe_to_skip_visible_render": False,
            "safe_next_action": "keep existing pack cache; do not add a second cache here",
            "reason": "pack rows already rebuild only when results version or action fingerprint changes",
        },
        {
            "surface": "visible summary container/render call",
            "classification": "must keep live",
            "safe_to_skip_visible_render": False,
            "safe_next_action": "do not bypass _render_current_inputs_summary or st.markdown output",
            "reason": "this creates the visible Inputs heading and summary card stack",
        },
        {
            "surface": "summary card HTML string build",
            "classification": "safe narrow reuse candidate",
            "safe_to_skip_visible_render": False,
            "safe_next_action": "reuse cached summary_cards_html only, then still call st.markdown",
            "reason": "stable no-input reruns can reuse identical generated HTML without hiding output",
        },
        {
            "surface": "Design Guide card render model",
            "classification": "already implemented bypass",
            "safe_to_skip_visible_render": False,
            "safe_next_action": "leave existing display-hash bypass unchanged",
            "reason": "separate card render-model bypass already has its own verifier and impact snapshot",
        },
        {
            "surface": "first-paint placeholder/layout gap",
            "classification": "separate layout issue",
            "safe_to_skip_visible_render": False,
            "safe_next_action": "track separately with browser layout stability snapshots",
            "reason": "HTML reuse may reduce churn but does not by itself remove static vertical spacing",
        },
    ]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    latest = {
        "reuse_plan": _latest("design_guide_stable_publication_summary_render_reuse_plan"),
        "reuse_readiness": _latest("design_guide_stable_publication_summary_render_reuse_readiness"),
        "layout_stability": _latest("design_guide_browser_live_layout_stability"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    inventory = _source_inventory(source)
    classifications = _classifications()
    next_slice = {
        "name": "summary_card_html_reuse_implementation",
        "allowed_change": (
            "cache/reuse generated summary_cards_html for stable no-input reruns while still rendering it"
        ),
        "required_key_inputs": (
            "summary_action_fp",
            "results_version",
            "final_publication_authority_hash",
            "final_publication_display_hash",
            "state_fingerprint",
            "panel_baseline_fingerprint",
        ),
        "required_rebuild_guards": (
            "missing cached HTML",
            "changed summary_action_fp",
            "changed results_version",
            "changed publication/display/state/panel hash",
            "debug mode",
            "post-click/apply in flight",
            "proof-pending or fallback shell",
        ),
        "forbidden_change": (
            "skip visible st.markdown",
            "skip _render_current_inputs_summary",
            "change summary wording",
            "change CTA/apply/family/runtime behaviour",
        ),
    }
    return {
        "latest": latest,
        "source_inventory": inventory,
        "classifications": classifications,
        "next_slice": next_slice,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    inventory = dict(capture.get("source_inventory") or {})
    classifications = list(capture.get("classifications") or [])
    safe_html_candidates = [
        row
        for row in classifications
        if row.get("surface") == "summary card HTML string build"
        and row.get("classification") == "safe narrow reuse candidate"
    ]
    visible_live_rows = [
        row
        for row in classifications
        if row.get("surface") == "visible summary container/render call"
        and row.get("classification") == "must keep live"
    ]
    return {
        "reuse_plan_pass": (latest.get("reuse_plan") or {}).get("status") == "PASS",
        "readiness_pass": (latest.get("reuse_readiness") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "source_inventory_complete": all(bool(value) for value in inventory.values()),
        "visible_render_marked_live": bool(visible_live_rows),
        "html_build_marked_safe_candidate": bool(safe_html_candidates),
        "no_surface_allows_skipping_visible_render": not any(
            bool(row.get("safe_to_skip_visible_render")) for row in classifications
        ),
    }


def _report(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Stable-Publication Summary/Render Reuse Scope Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Readiness: `{payload.get('readiness')}`",
        "",
        "## Decision",
        "",
        "The next smoothness implementation must reuse only the generated summary-card HTML string.",
        "It must still render the visible summary container and `st.markdown(...)` output on every rerun.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Classified Surfaces", "", "| Surface | Classification | Safe next action |", "|---|---|---|"])
    for row in payload.get("classifications") or []:
        lines.append(
            f"| {row.get('surface')} | {row.get('classification')} | {row.get('safe_next_action')} |"
        )
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            "Implement `summary_card_html_reuse_implementation`: cache/reuse generated "
            "`summary_cards_html` under the proven stable keys, but always pass that HTML through "
            "the existing visible `st.markdown(...)` renderer.",
            "",
            "Do not skip the summary container, Inputs heading, Design Guide slot, CTA/apply binding, "
            "family runtimes, visible wording, or engineering calculations.",
            "",
        ]
    )
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_stable_publication_summary_render_reuse_scope_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_stable_publication_summary_render_reuse_scope_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(_report(payload), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "created_at": _stamp(),
        "status": status,
        "readiness": "READY_FOR_SUMMARY_CARD_HTML_REUSE_IMPLEMENTATION" if status == "PASS" else "NOT_READY",
        "checks": checks,
        **capture,
    }
    payload["snapshot_hash"] = _stable_hash(
        {
            "status": payload["status"],
            "readiness": payload["readiness"],
            "checks": checks,
            "classifications": payload["classifications"],
            "next_slice": payload["next_slice"],
        }
    )
    json_path, report_path = _write(payload)
    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
