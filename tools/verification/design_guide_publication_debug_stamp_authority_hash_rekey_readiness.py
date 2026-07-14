"""Readiness proof for rekeying debug publication stamps to authority hash.

Proof-only. This verifier uses the latest same-session browser/live audits plus
source checks to decide whether duplicate debug/session publication stamps can
be keyed by the stable FinalDesignGuidePublication authority hash rather than
the drifting verifier/debug payload hash.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

APPROVED_CANDIDATES = {
    "duplicate_debug_session_publication_stamps",
    "repeated_verifier_debug_payload_stamping",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}, "passed": False}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "path": str(path), "payload": {}, "passed": False, "error": str(exc)}
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    passed = "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper()
    return {"found": True, "path": str(path), "payload": payload, "passed": passed}


def _source_window(source: str, needle: str, *, radius: int = 1400) -> str:
    index = source.find(needle)
    if index < 0:
        return ""
    return source[max(0, index - radius): index + len(needle) + radius]


def _same_session_evidence() -> dict[str, Any]:
    profile = _latest("design_guide_same_session_no_change_rerun_profile")
    rerun = _latest("design_guide_same_session_rerun_trigger_ownership")
    instability = _latest("design_guide_same_session_publication_debug_stamp_hash_instability")
    profile_cls = dict((profile.get("payload") or {}).get("classification") or {})
    rerun_cls = dict((rerun.get("payload") or {}).get("classification") or {})
    instability_cls = dict((instability.get("payload") or {}).get("classification") or {})
    return {
        "profile": profile,
        "rerun": rerun,
        "instability": instability,
        "stable_authority_hashes": bool(
            profile_cls.get("stable_authority_hashes")
            and rerun_cls.get("stable_authority_hashes")
            and instability_cls.get("stable_authority_hashes")
        ),
        "candidate_eval_zero": int(profile_cls.get("candidate_evaluation_count_after") or 0) == 0
        and int(rerun_cls.get("candidate_evaluation_count_after") or 0) == 0,
        "card_rebuild_zero": int(profile_cls.get("card_render_model_rebuild_count_after") or 0) == 0
        and int(rerun_cls.get("card_render_model_rebuild_count_after") or 0) == 0,
        "debug_stamp_rebuilds_only": int(rerun_cls.get("publication_rebuild_count_after") or 0) == 2,
        "pre_click_verifier_payload_not_ready": profile_cls.get("before_debug_payload_ready") is False
        or instability_cls.get("before_verifier_payload_ready") is False,
        "after_click_verifier_payload_ready": profile_cls.get("after_debug_payload_ready") is True
        or instability_cls.get("after_verifier_payload_ready") is True,
        "same_session_rekey_needed": (
            "publication_debug_stamp_rebuild_after_stable_manual_rerun"
            in list(rerun_cls.get("likely_sources") or [])
        ),
    }


def _source_evidence() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8")
    current_hash_helper = _source_window(source, "def _final_publication_current_hash_from_debug")
    decision_helper = _source_window(
        source,
        "def _final_publication_duplicate_stamp_bypass_decision",
        radius=2600,
    )
    stamp_helper = _source_window(source, "def _stamp_final_publication_same_object_verifier_payload")
    legacy_helper = _source_window(source, "def _canonicalize_legacy_design_guide_publication_session_storage")
    return {
        "approved_candidates_present": all(candidate in source for candidate in APPROVED_CANDIDATES),
        "current_hash_helper_prefers_debug_payload_hash": (
            'payload.get("publication_hash")' in current_hash_helper
            and current_hash_helper.find('payload.get("publication_hash")')
            < current_hash_helper.find('debug_sink.get("publication_hash")')
        ),
        "stable_authority_hash_available": "final_publication_authority_hash" in current_hash_helper
        and "final_publication_authority_hash" in source,
        "decision_helper_has_debug_force_guard": "debug_force_rebuild" in decision_helper,
        "decision_helper_rebuilds_missing_hash": "missing_current_publication_hash" in decision_helper
        and "missing_previous_publication_hash" in decision_helper,
        "decision_helper_rebuilds_stale_hash": "stale_or_changed_publication_hash" in decision_helper,
        "stamp_surfaces_non_authoritative": all(
            token in source
            for token in (
                '"affects_final_publication": False',
                '"affects_cta": False',
                '"affects_display": False',
                '"affects_apply_payload": False',
                '"affects_visible_wording": False',
            )
        ),
        "verifier_stamp_surface": bool(stamp_helper),
        "legacy_session_stamp_surface": bool(legacy_helper),
        "apply_routing_not_in_stamp_helpers": "_record_rendered_design_guide_primary_apply_payload" not in stamp_helper
        and "_record_rendered_design_guide_primary_apply_payload" not in legacy_helper,
        "rendering_not_in_stamp_helpers": "_design_guide_dashboard_card_html_from_render_model" not in stamp_helper
        and "_design_guide_dashboard_card_html_from_render_model" not in legacy_helper,
    }


def _locks() -> dict[str, Any]:
    return {
        "duplicate_stamp_bypass_live_impact": _latest("design_guide_duplicate_publication_stamp_bypass_live_impact"),
        "same_session_rerun_trigger_ownership": _latest("design_guide_same_session_rerun_trigger_ownership"),
        "same_session_no_change_rerun_profile": _latest("design_guide_same_session_no_change_rerun_profile"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "zero_authority_lock": _latest("design_brain_inputs_page_zero_authority_inventory_lock"),
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Publication Debug Stamp Authority-Hash Rekey Readiness",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Executive Summary",
        "",
        f"- Ready for guarded rekey: `{payload['ready_for_guarded_rekey']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Live Evidence",
        "",
        "```json",
        json.dumps(payload["same_session_evidence"], indent=2, sort_keys=True, default=str),
        "```",
        "",
        "## Source Evidence",
        "",
        "```json",
        json.dumps(payload["source_evidence"], indent=2, sort_keys=True, default=str),
        "```",
        "",
        "## Failures",
        "",
    ]
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Recommendation", "", payload["recommended_next_slice"]])
    return "\n".join(lines) + "\n"


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    same_session = _same_session_evidence()
    source = _source_evidence()
    locks = _locks()
    failures: list[str] = []

    for name, row in locks.items():
        if row.get("passed") is not True:
            failures.append(f"{name}_not_passed")
    for key in (
        "stable_authority_hashes",
        "candidate_eval_zero",
        "card_rebuild_zero",
        "debug_stamp_rebuilds_only",
        "same_session_rekey_needed",
    ):
        if same_session.get(key) is not True:
            failures.append(f"same_session_evidence_failed::{key}")
    for key in (
        "approved_candidates_present",
        "current_hash_helper_prefers_debug_payload_hash",
        "stable_authority_hash_available",
        "decision_helper_has_debug_force_guard",
        "decision_helper_rebuilds_missing_hash",
        "decision_helper_rebuilds_stale_hash",
        "stamp_surfaces_non_authoritative",
        "verifier_stamp_surface",
        "legacy_session_stamp_surface",
        "apply_routing_not_in_stamp_helpers",
        "rendering_not_in_stamp_helpers",
    ):
        if source.get(key) is not True:
            failures.append(f"source_evidence_failed::{key}")

    ready = not failures
    stamp = _stamp()
    payload = {
        "schema": "design_guide_publication_debug_stamp_authority_hash_rekey_readiness.v1",
        "created_at": stamp,
        "status": "PASS" if ready else "FAIL",
        "ready_for_guarded_rekey": ready,
        "failures": failures,
        "same_session_evidence": same_session,
        "source_evidence": source,
        "locks": {
            name: {"path": row.get("path"), "passed": row.get("passed"), "found": row.get("found")}
            for name, row in locks.items()
        },
        "product_behavior_changed": False,
        "recommended_next_slice": (
            "Implement guarded duplicate debug/session stamp rekey to stable "
            "FinalDesignGuidePublication authority/publication hash, preserving debug/missing/stale rebuild guards."
            if ready
            else "Do not rekey yet; fix the failed readiness evidence first."
        ),
    }
    json_path = ARTIFACT_DIR / f"design_guide_publication_debug_stamp_authority_hash_rekey_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_publication_debug_stamp_authority_hash_rekey_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_publication_debug_stamp_authority_hash_rekey_readiness {payload['status']}")
    print(f"ready_for_guarded_rekey={payload['ready_for_guarded_rekey']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
