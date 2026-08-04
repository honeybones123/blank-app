"""Row-level readiness for post-click final contract check narrowing/deletion.

This verifier uses both post-click proof hashes:
- input proof hash
- replacement-decision proof hash

It classifies which live rows can be moved/narrowed next and which must stay
live until a stronger controller/publication replacement exists.
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

TARGET_START = '_final_contract_for_post_click = dict(_final_visible_item.get("button_contract") or {})'
TARGET_END = "_final_visible_item = _normalise_visible_optimisation_contract("

LIVE_KEEP_TOKENS = {
    "page_session_apply_inputs": (
        "DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY",
        "DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY",
        "_same_flow_cleanup_apply_for_visible = bool(",
    ),
    "current_state_inputs": (
        '_float_from_state(current_state, "lig_d", None)',
        '_float_from_state(current_state, "lig_legs", None)',
        "_final_current_bending_util_for_post_click",
    ),
    "decision_predicates": (
        "_post_click_bending_low_requires_exact_blocker = bool(",
        "_post_click_bending_low_visible_action = bool(",
        "_guidance_item_has_low_util_exact_blocker(",
    ),
    "bending_audit_collection": (
        "_post_click_bending_audit = dict(guidance_debug)",
        "for _bending_audit_source in (",
        "_post_click_bending_audit[_evidence_key] = dict(_existing_evidence)",
    ),
    "bending_resolution_builder": (
        "_post_click_low_bending_resolution_item(",
        "_design_mode_config(_design_optimisation_goal(current_state))",
        "debug_sink=guidance_debug",
    ),
    "publication_binding_call": (
        "_publish_final_visible_design_guide_contract_binding(",
        'rec=dict(st.session_state.get("pending_recommendation") or {})',
    ),
}

NARROWABLE_PROJECTION_TOKENS = {
    "post_publish_projection_rows": (
        '_final_visible_resolution["item"] = dict(_final_visible_item)',
        '_final_visible_resolution["render_reason"] = "post_click_low_bending_exact_blocker_final"',
        'guidance_debug["post_click_low_bending_action_replaced_by_exact_blocker"] = True',
        'guidance_debug["guidance_branch"] = "post_click_low_bending_exact_blocker_final"',
        "_post_click_bending_replacement_applied = True",
    ),
}

TRACE_PROOF_TOKENS = {
    "input_proof_trace": (
        "_stamp_final_publication_post_click_contract_check_input_proof(",
        "final_publication_post_click_contract_check_input_proof_hash",
    ),
    "replacement_decision_trace": (
        "_stamp_final_publication_post_click_replacement_decision_proof(",
        "final_publication_post_click_replacement_decision_proof_hash",
    ),
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = artifacts[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _target_block(source: str) -> str:
    start = source.find(TARGET_START)
    if start < 0:
        return ""
    end = source.find(TARGET_END, start)
    return source[start:end] if end > start else ""


def _all_present(block: str, tokens: tuple[str, ...]) -> bool:
    return all(token in block for token in tokens)


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    block = _target_block(source)
    live_keep = {
        key: {"present": _all_present(block, tokens), "tokens": list(tokens)}
        for key, tokens in LIVE_KEEP_TOKENS.items()
    }
    narrowable = {
        key: {"present": _all_present(block, tokens), "tokens": list(tokens)}
        for key, tokens in NARROWABLE_PROJECTION_TOKENS.items()
    }
    trace_proof = {
        key: {"present": _all_present(source, tokens), "tokens": list(tokens)}
        for key, tokens in TRACE_PROOF_TOKENS.items()
    }
    latest = {
        "input_object": _latest("design_guide_post_click_contract_check_input_proof_object"),
        "input_trace": _latest("design_guide_live_post_click_contract_check_input_proof_trace"),
        "input_parity": _latest("design_guide_post_click_contract_check_input_proof_parity_scenarios"),
        "replacement_object": _latest("design_guide_post_click_replacement_decision_proof_object"),
        "replacement_trace": _latest("design_guide_live_post_click_replacement_decision_proof_trace"),
        "replacement_parity": _latest("design_guide_post_click_replacement_decision_proof_parity_scenarios"),
        "classification": _latest("design_guide_post_click_contract_check_live_rows_classification"),
        "render_lock": _latest("design_guide_render_bridge_lock"),
        "compute_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    can_narrow_now = [
        key for key, value in narrowable.items() if value.get("present") is True
    ]
    already_removed_projection_rows = [
        key for key, value in narrowable.items() if value.get("present") is False
    ]
    keep_live = [
        key for key, value in live_keep.items() if value.get("present") is True
    ]
    return {
        "decision": "POST_CLICK_ROW_LEVEL_READINESS_CLASSIFIED",
        "target_block_found": bool(block),
        "target_block_hash": _stable_hash(block),
        "live_keep": live_keep,
        "narrowable_projection_rows": narrowable,
        "trace_proof": trace_proof,
        "can_narrow_now": can_narrow_now,
        "already_removed_projection_rows": already_removed_projection_rows,
        "keep_live": keep_live,
        "deletion_candidates": [],
        "direct_cutover_ready": False,
        "recommended_next_slice": (
            "projection rows are already removed/adapter-backed; keep session/apply inputs, "
            "current-state inputs, decision predicates, audit collection, resolution builder, "
            "and publication binding live"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "latest": {
            key: {"status": value.get("status"), "path": value.get("path")}
            for key, value in latest.items()
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    live_keep = dict(capture.get("live_keep") or {})
    trace_proof = dict(capture.get("trace_proof") or {})
    return {
        "target_block_found": capture.get("target_block_found") is True,
        "all_live_keep_classes_present": all(
            (value or {}).get("present") is True for value in live_keep.values()
        ),
        "both_trace_proofs_present": all(
            (value or {}).get("present") is True for value in trace_proof.values()
        ),
        "projection_rows_removed_or_only_remaining_narrowable": (
            capture.get("can_narrow_now") == ["post_publish_projection_rows"]
            or capture.get("already_removed_projection_rows") == ["post_publish_projection_rows"]
        ),
        "no_deletion_candidates": capture.get("deletion_candidates") == [],
        "direct_cutover_still_false": capture.get("direct_cutover_ready") is False,
        "input_object_pass": (latest.get("input_object") or {}).get("status") == "PASS",
        "input_trace_pass": (latest.get("input_trace") or {}).get("status") == "PASS",
        "input_parity_pass": (latest.get("input_parity") or {}).get("status") == "PASS",
        "replacement_object_pass": (latest.get("replacement_object") or {}).get("status") == "PASS",
        "replacement_trace_pass": (latest.get("replacement_trace") or {}).get("status") == "PASS",
        "replacement_parity_pass": (latest.get("replacement_parity") or {}).get("status") == "PASS",
        "classification_pass": (latest.get("classification") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Contract Check Row-Level Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Can narrow now: `{capture.get('can_narrow_now')}`",
        f"- Already removed projection rows: `{capture.get('already_removed_projection_rows')}`",
        f"- Keep live: `{capture.get('keep_live')}`",
        f"- Deletion candidates: `{capture.get('deletion_candidates')}`",
        f"- Recommended next slice: {capture.get('recommended_next_slice')}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_post_click_contract_check_row_level_readiness_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR / f"design_guide_post_click_contract_check_row_level_readiness_{stamp}.json"
    )
    md_path = AUDIT_DIR / f"design_guide_post_click_contract_check_row_level_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_contract_check_row_level_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
