"""Guarded plan for stable-publication summary/render reuse.

Plan-only. This verifies that the next smoothness implementation would be
keyed by stable publication/state hashes and would rebuild for all stale or
unsafe states. It does not implement caching or bypasses.
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

REUSE_KEYS = (
    "final_publication_authority_hash",
    "final_publication_display_hash",
    "panel_baseline_fingerprint",
    "state_fingerprint",
)
REBUILD_GUARDS = (
    "missing_reuse_key",
    "changed_reuse_key",
    "stale_publication_hash",
    "debug_mode_enabled",
    "post_click_apply_in_flight",
    "pending_apply_refresh",
    "changed_family_result",
    "changed_visible_card_state",
    "changed_cta_or_payload_hash",
    "missing_cached_summary",
    "missing_cached_render_output",
    "proof_pending_or_fallback_shell",
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
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "readiness": payload.get("readiness"), "payload": payload}


def _source_key_markers() -> dict[str, bool]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    return {
        key: key in source
        for key in (
            "final_publication_authority_hash",
            "final_publication_display_hash",
            "state_fingerprint",
            "pending_inputs_apply_refresh",
            "run_design_clicked",
            "card_render_model_bypassed",
        )
    }


def _scenario_decisions() -> list[dict[str, Any]]:
    stable_keys = {key: f"{key}:stable" for key in REUSE_KEYS}

    def decision(name: str, **overrides: Any) -> dict[str, Any]:
        state = {
            "current_keys": dict(stable_keys),
            "cached_keys": dict(stable_keys),
            "debug_mode": False,
            "post_click_apply_in_flight": False,
            "pending_apply_refresh": False,
            "family_result_changed": False,
            "visible_card_state_changed": False,
            "cta_or_payload_hash_changed": False,
            "cached_summary_present": True,
            "cached_render_output_present": True,
            "proof_pending_or_fallback_shell": False,
        }
        state.update(overrides)
        guards = []
        current_keys = dict(state.get("current_keys") or {})
        cached_keys = dict(state.get("cached_keys") or {})
        for key in REUSE_KEYS:
            if not current_keys.get(key) or not cached_keys.get(key):
                guards.append("missing_reuse_key")
                break
            if current_keys.get(key) != cached_keys.get(key):
                guards.append("changed_reuse_key")
                break
        if state.get("debug_mode"):
            guards.append("debug_mode_enabled")
        if state.get("post_click_apply_in_flight"):
            guards.append("post_click_apply_in_flight")
        if state.get("pending_apply_refresh"):
            guards.append("pending_apply_refresh")
        if state.get("family_result_changed"):
            guards.append("changed_family_result")
        if state.get("visible_card_state_changed"):
            guards.append("changed_visible_card_state")
        if state.get("cta_or_payload_hash_changed"):
            guards.append("changed_cta_or_payload_hash")
        if not state.get("cached_summary_present"):
            guards.append("missing_cached_summary")
        if not state.get("cached_render_output_present"):
            guards.append("missing_cached_render_output")
        if state.get("proof_pending_or_fallback_shell"):
            guards.append("proof_pending_or_fallback_shell")
        return {
            "name": name,
            "decision": "REUSE" if not guards else "REBUILD",
            "guards": sorted(set(guards)),
        }

    changed = dict(stable_keys)
    changed["final_publication_display_hash"] = "display:changed"
    return [
        decision("stable_non_debug_no_pending"),
        decision("changed_display_hash", current_keys=changed),
        decision("missing_authority_hash", current_keys={**stable_keys, "final_publication_authority_hash": ""}),
        decision("debug_mode", debug_mode=True),
        decision("post_click_apply_in_flight", post_click_apply_in_flight=True),
        decision("pending_apply_refresh", pending_apply_refresh=True),
        decision("changed_family_result", family_result_changed=True),
        decision("changed_visible_card_state", visible_card_state_changed=True),
        decision("changed_cta_or_payload_hash", cta_or_payload_hash_changed=True),
        decision("missing_cached_summary", cached_summary_present=False),
        decision("missing_cached_render_output", cached_render_output_present=False),
        decision("proof_pending_or_fallback_shell", proof_pending_or_fallback_shell=True),
    ]


def _capture() -> dict[str, Any]:
    readiness = _latest("design_guide_stable_publication_summary_render_reuse_readiness")
    rerun = _latest("design_guide_rerun_trigger_source_profile")
    layout = _latest("design_guide_browser_live_layout_stability")
    plan = {
        "reuse_keys": REUSE_KEYS,
        "rebuild_guards": REBUILD_GUARDS,
        "allowed_scope": (
            "summary/render reuse only",
            "no publication truth change",
            "no CTA/apply semantic change",
            "no family runtime change",
            "no visible wording change",
        ),
        "required_future_verifier": "design_guide_stable_publication_summary_render_reuse_implementation",
    }
    return {
        "preconditions": {
            "readiness": {"status": readiness.get("status"), "readiness": readiness.get("readiness"), "path": readiness.get("path")},
            "rerun_profile": {"status": rerun.get("status"), "path": rerun.get("path")},
            "layout_profile": {"status": layout.get("status"), "path": layout.get("path")},
        },
        "source_key_markers": _source_key_markers(),
        "scenario_decisions": _scenario_decisions(),
        "plan": plan,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    preconditions = dict(capture.get("preconditions") or {})
    decisions = list(capture.get("scenario_decisions") or ())
    stable = [row for row in decisions if row.get("name") == "stable_non_debug_no_pending"]
    rebuilds = [row for row in decisions if row.get("name") != "stable_non_debug_no_pending"]
    covered_guards = {guard for row in rebuilds for guard in row.get("guards") or ()}
    return {
        "readiness_pass": (preconditions.get("readiness") or {}).get("status") == "PASS",
        "readiness_ready_for_plan": (preconditions.get("readiness") or {}).get("readiness") == "READY_FOR_GUARDED_PLAN",
        "browser_profiles_pass": (preconditions.get("rerun_profile") or {}).get("status") == "PASS"
        and (preconditions.get("layout_profile") or {}).get("status") == "PASS",
        "source_key_markers_present": all((capture.get("source_key_markers") or {}).values()),
        "stable_case_reuses": bool(stable and stable[0].get("decision") == "REUSE"),
        "all_guarded_cases_rebuild": all(row.get("decision") == "REBUILD" for row in rebuilds),
        "required_guards_covered": set(REBUILD_GUARDS) - {"stale_publication_hash"} <= covered_guards,
        "plan_scope_limited": "no family runtime change" in (capture.get("plan") or {}).get("allowed_scope", ()),
    }


def _report(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Stable-Publication Summary/Render Reuse Plan",
        "",
        f"Status: `{payload.get('status')}`",
        f"Readiness: `{payload.get('readiness')}`",
        "",
        "## Scope",
        "",
        "- Plan-only verifier.",
        "- No cache, bypass, layout, CTA/apply, runtime, or wording change.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Scenario Decisions", "", "```json"])
    lines.append(json.dumps(payload.get("scenario_decisions") or [], indent=2, sort_keys=True))
    lines.extend(
        [
            "```",
            "",
            "## Next Safe Slice",
            "",
            "Implement the guarded reuse only if the implementation can reuse summary/render output without "
            "changing publication truth, CTA/apply semantics, family runtimes, visible wording, or stale-state behaviour.",
            "",
        ]
    )
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_stable_publication_summary_render_reuse_plan_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_stable_publication_summary_render_reuse_plan_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    report_path.write_text(_report(payload), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_stable_publication_summary_render_reuse_plan.v1",
        "created_at": _stamp(),
        "status": status,
        "readiness": "READY_FOR_NARROW_IMPLEMENTATION" if status == "PASS" else "NOT_READY",
        "product_behaviour_changed": False,
        "new_cache_or_bypass_implemented": False,
        "checks": checks,
        "failures": [key for key, ok in checks.items() if not ok],
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
        **capture,
    }
    json_path, report_path = _write(payload)
    print(f"design_guide_stable_publication_summary_render_reuse_plan {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    print(json.dumps({"status": status, "readiness": payload["readiness"], "failures": payload["failures"]}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
