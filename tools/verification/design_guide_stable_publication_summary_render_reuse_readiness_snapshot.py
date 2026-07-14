"""Readiness proof for stable-publication summary/render reuse.

Proof-only. This composes browser/live rerun and layout stability profiles to
decide whether the next smoothness slice may introduce a guarded reuse/bypass
for summary/render rebuilds. No app behaviour is changed here.
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

REQUIRED_STABLE_HASH_KEYS = (
    "final_publication_authority_hash",
    "final_publication_display_hash",
    "panel_baseline_fingerprint",
    "state_fingerprint",
)


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
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": f"{type(exc).__name__}: {exc}", "payload": {}}
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _stable_hash_key_report(profile: dict[str, Any]) -> dict[str, Any]:
    classification = dict(profile.get("classification") or {})
    compared = dict(classification.get("compared_hashes") or {})
    return {
        key: {
            "present": key in compared,
            "matches": bool((compared.get(key) or {}).get("matches")),
            "before_count": len((compared.get(key) or {}).get("before") or ()),
            "after_count": len((compared.get(key) or {}).get("after") or ()),
        }
        for key in REQUIRED_STABLE_HASH_KEYS
    }


def _capture() -> dict[str, Any]:
    rerun = _latest("design_guide_rerun_trigger_source_profile")
    layout = _latest("design_guide_browser_live_layout_stability")
    rerun_payload = dict(rerun.get("payload") or {})
    layout_payload = dict(layout.get("payload") or {})
    rerun_cls = dict(rerun_payload.get("classification") or {})
    layout_cls = dict(layout_payload.get("classification") or {})
    stable_key_report = _stable_hash_key_report(rerun_payload)
    return {
        "source_artifacts": {
            "rerun_trigger_source_profile": {"status": rerun.get("status"), "path": rerun.get("path")},
            "layout_stability": {"status": layout.get("status"), "path": layout.get("path")},
        },
        "rerun_classification": {
            "stable_publication_or_state_hashes": rerun_cls.get("stable_publication_or_state_hashes"),
            "design_guide_rebuilt": rerun_cls.get("design_guide_rebuilt"),
            "summary_rebuilt": rerun_cls.get("summary_rebuilt"),
            "stable_slot_shell_path_seen": rerun_cls.get("stable_slot_shell_path_seen"),
            "browser_probe_rebuilt": rerun_cls.get("browser_probe_rebuilt"),
            "final_card_visible_after_reload": rerun_cls.get("final_card_visible_after_reload"),
            "design_guide_heading_visible_after_reload": rerun_cls.get("design_guide_heading_visible_after_reload"),
            "proof_pending_shell_visible_after_reload": rerun_cls.get("proof_pending_shell_visible_after_reload"),
            "pending_flags_after_reload": rerun_cls.get("pending_flags_after_reload"),
            "likely_sources": list(rerun_cls.get("likely_sources") or ()),
            "largest_gap": rerun_cls.get("largest_gap"),
        },
        "layout_classification": {
            "audit_result": layout_cls.get("audit_result"),
            "risks": list(layout_cls.get("risks") or ()),
            "max_summary_to_batch_gap_px": layout_cls.get("max_summary_to_batch_gap_px"),
            "max_batch_to_design_guide_gap_px": layout_cls.get("max_batch_to_design_guide_gap_px"),
            "max_layout_shift_total": layout_cls.get("max_layout_shift_total"),
            "scroll_locked_while_scrollable": bool(((layout_cls.get("scroll_probe") or {}).get("locked_while_scrollable"))),
        },
        "stable_key_report": stable_key_report,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rerun_sources = dict(capture.get("source_artifacts") or {}).get("rerun_trigger_source_profile") or {}
    layout_sources = dict(capture.get("source_artifacts") or {}).get("layout_stability") or {}
    rerun = dict(capture.get("rerun_classification") or {})
    layout = dict(capture.get("layout_classification") or {})
    key_report = dict(capture.get("stable_key_report") or {})
    pending = dict(rerun.get("pending_flags_after_reload") or {})
    return {
        "rerun_profile_pass": rerun_sources.get("status") == "PASS",
        "layout_profile_pass": layout_sources.get("status") == "PASS",
        "required_keys_present_and_stable": all(
            (key_report.get(key) or {}).get("present") and (key_report.get(key) or {}).get("matches")
            for key in REQUIRED_STABLE_HASH_KEYS
        ),
        "stable_hashes_with_rebuilds_observed": bool(rerun.get("stable_publication_or_state_hashes"))
        and bool(rerun.get("design_guide_rebuilt"))
        and bool(rerun.get("summary_rebuilt")),
        "no_pending_apply_or_run_flags": not any(bool(value) for value in pending.values()),
        "final_or_heading_visible_not_proof_pending": (
            bool(rerun.get("final_card_visible_after_reload"))
            or bool(rerun.get("design_guide_heading_visible_after_reload"))
        )
        and not bool(rerun.get("proof_pending_shell_visible_after_reload")),
        "layout_gap_risk_captured_or_resolved": (
            bool(set(layout.get("risks") or ()) & {"large_summary_to_batch_gap", "large_batch_to_design_guide_gap"})
            or str(layout.get("audit_result") or "") == "NO_MAJOR_LAYOUT_RISK_DETECTED"
        ),
        "scroll_not_locked_in_latest_profile": not bool(layout.get("scroll_locked_while_scrollable")),
    }


def _report(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Stable-Publication Summary/Render Reuse Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Readiness: `{payload.get('readiness')}`",
        "",
        "## Scope",
        "",
        "- Proof-only readiness.",
        "- No cache, bypass, layout, publication, CTA/apply, runtime, or wording change.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Stable Keys",
            "",
            "```json",
            json.dumps(payload.get("stable_key_report") or {}, indent=2, sort_keys=True),
            "```",
            "",
            "## Next Safe Slice",
            "",
            "Create a guarded implementation plan for summary/render reuse keyed by "
            "`final_publication_authority_hash`, `final_publication_display_hash`, "
            "`panel_baseline_fingerprint`, and `state_fingerprint`. Separately keep the "
            "large placeholder/gap risk visible until first-paint placeholder height is proven.",
            "",
        ]
    )
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_stable_publication_summary_render_reuse_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_stable_publication_summary_render_reuse_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    report_path.write_text(_report(payload), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_stable_publication_summary_render_reuse_readiness.v1",
        "created_at": _stamp(),
        "status": status,
        "readiness": "READY_FOR_GUARDED_PLAN" if status == "PASS" else "NOT_READY",
        "product_behaviour_changed": False,
        "new_cache_or_bypass_implemented": False,
        "checks": checks,
        "failures": [key for key, ok in checks.items() if not ok],
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
        **capture,
    }
    json_path, report_path = _write(payload)
    print(f"design_guide_stable_publication_summary_render_reuse_readiness {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    print(json.dumps({"status": status, "readiness": payload["readiness"], "failures": payload["failures"]}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
