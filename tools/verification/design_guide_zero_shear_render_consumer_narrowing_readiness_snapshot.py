"""Readiness proof for narrowing the zero-shear render-item consumer.

Proof-only. This snapshot checks whether the FinalDesignGuidePublication render
consumer proof fully represents the zero-shear page mutations before any
page-side narrowing or deletion is attempted.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
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

ZERO_SHEAR_MUTATION_TOKENS = {
    "clears_item_exact_blockers": 'if "shear" in _zero_shear_exact:',
    "stamps_stale_blocker_cleared": 'guidance_debug["zero_shear_accepted_stale_blocker_cleared"] = True',
    "builds_terminal_stop_row": "_zero_shear_terminal_stop_row = {",
    "stamps_item_blocker_attempt": '_final_visible_item["blocker_attempts_by_family"] = dict(_zero_shear_attempts)',
    "stamps_item_candidate_evidence": '_final_visible_item["candidate_search_evidence"] = dict(_zero_shear_candidate_evidence)',
    "stamps_debug_blocker_attempt": 'guidance_debug["blocker_attempts_by_family"] = dict(_guidance_zero_shear_attempts)',
    "stamps_debug_candidate_evidence": 'guidance_debug["candidate_search_evidence"] = dict(_guidance_zero_shear_evidence)',
    "stamps_session_debug": '_session_zero_shear_debug["candidate_search_evidence"] = dict(',
}
ADAPTER_CALL = "_apply_final_design_guide_zero_shear_render_consumer_projection("
ADAPTER_IMPORT = (
    "apply_final_design_guide_zero_shear_render_consumer_projection "
    "as _apply_final_design_guide_zero_shear_render_consumer_projection"
)


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


def _proof_sample() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_publication,
        build_final_design_guide_render_item_consumer_proof,
        stable_final_publication_hash,
    )

    terminal_row = {
        "attempted": True,
        "cleanup_search_ran": True,
        "no_link_candidate_already_active": True,
        "attempted_candidate_count": 1,
        "attempted_updates": {},
        "current_util": 0.0,
        "attempted_util": 0.0,
        "attempted_passed": True,
        "rejection_category": "Zero shear demand terminal cleanup proof",
        "failed_check_name": "zero shear demand cleanup target",
        "reason": "With Vu* = 0.0 kN, shear utilisation remains 0.00 and shear links are already removed.",
    }
    candidate_search_evidence = {"blocker_attempts_by_family": {"shear": terminal_row}}
    item = {
        "published_item_id": "zero-shear-proof-item",
        "family": "shear",
        "selected_family_id": "SHEAR_OVERDESIGN_GOVERNS",
        "status": "PASS",
        "blocking_reason": "zero_shear_no_cleanup_required",
        "post_click_design_guide_state": "zero_shear_no_cleanup_required",
        "zero_shear_accepted_stale_blocker_cleared": True,
        "candidate_search_evidence": candidate_search_evidence,
        "blocker_attempts_by_family": {"shear": terminal_row},
    }
    debug = {
        "selected_family_id": "SHEAR_OVERDESIGN_GOVERNS",
        "zero_shear_accepted_stale_blocker_cleared": True,
        "candidate_search_evidence": candidate_search_evidence,
        "blocker_attempts_by_family": {"shear": terminal_row},
    }
    publication = build_final_design_guide_publication(
        item=item,
        debug=debug,
        design_brain_result={"selected_family_id": "SHEAR_OVERDESIGN_GOVERNS"},
        publication_reason="zero_shear_render_consumer_narrowing_readiness",
    )
    proof = build_final_design_guide_render_item_consumer_proof(
        publication,
        selected_item=item,
        final_visible_resolution={"item": item, "render_reason": "zero_shear_terminal_stop"},
        guidance_debug=debug,
    ).to_dict()
    zero = dict(proof.get("zero_shear_cleanup") or {})
    return {
        "proof": proof,
        "zero_shear_cleanup": zero,
        "terminal_row": terminal_row,
        "terminal_row_hash": stable_final_publication_hash(terminal_row),
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    sample = _proof_sample()
    zero = dict(sample.get("zero_shear_cleanup") or {})
    mutation_tokens = {key: token in source for key, token in ZERO_SHEAR_MUTATION_TOKENS.items()}
    old_manual_rows_deleted = not any(
        mutation_tokens.get(key)
        for key in (
            "stamps_item_blocker_attempt",
            "stamps_item_candidate_evidence",
            "stamps_debug_blocker_attempt",
            "stamps_debug_candidate_evidence",
            "stamps_session_debug",
        )
    )
    adapter_source = {
        "import_present": ADAPTER_IMPORT in source,
        "adapter_call_present": ADAPTER_CALL in source,
        "terminal_row_still_built": "_zero_shear_terminal_stop_row = {" in source,
        "session_storage_page_owned": "_session_zero_shear_debug.update(" in source,
        "old_manual_rows_deleted": old_manual_rows_deleted,
    }
    required_payload_fields = {
        "stale_blocker_cleared": zero.get("stale_blocker_cleared") is True,
        "has_shear_attempt": zero.get("has_shear_attempt") is True,
        "shear_attempt_hash": zero.get("shear_attempt_hash") == sample.get("terminal_row_hash"),
        "candidate_search_evidence_hash": bool(zero.get("candidate_search_evidence_hash")),
        "terminal_state": bool(zero.get("terminal_state")),
        "shear_attempt": isinstance(zero.get("shear_attempt"), dict) and bool(zero.get("shear_attempt")),
        "stale_blocker_cleanup_projection": isinstance(
            zero.get("stale_blocker_cleanup_projection"), dict
        )
        and bool(zero.get("stale_blocker_cleanup_projection")),
    }
    latest = {
        "parity": _latest("design_guide_live_render_item_consumer_adapter_parity"),
        "trace": _latest("design_guide_live_render_item_consumer_adapter_trace"),
        "object": _latest("design_guide_render_item_consumer_adapter_object"),
        "manual_rows_deadness": _latest(
            "design_guide_zero_shear_render_consumer_manual_rows_deadness"
        ),
        "render_lock": _latest("design_guide_render_bridge_lock"),
        "compute_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    adapter_mediated = (
        all(adapter_source.values())
        and latest["manual_rows_deadness"].get("status") == "PASS"
    )
    ready = (
        (all(mutation_tokens.values()) or adapter_mediated)
        and all(required_payload_fields.values())
        and (latest["parity"].get("status") == "PASS")
    )
    return {
        "decision": (
            "ZERO_SHEAR_RENDER_CONSUMER_READY_TO_NARROW"
            if ready
            else "ZERO_SHEAR_RENDER_CONSUMER_PROOF_SURFACE_INCOMPLETE"
        ),
        "page_mutation_tokens_present": mutation_tokens,
        "adapter_source": adapter_source,
        "adapter_mediated": adapter_mediated,
        "required_payload_fields": required_payload_fields,
        "ready_to_narrow": ready,
        "deletion_safe_now": False,
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
    manual_or_adapter = all(
        (capture.get("page_mutation_tokens_present") or {}).values()
    ) or capture.get("adapter_mediated") is True
    return {
        "manual_rows_present_or_adapter_mediated": manual_or_adapter,
        "required_payload_fields_present": all(
            (capture.get("required_payload_fields") or {}).values()
        ),
        "ready_to_narrow": capture.get("ready_to_narrow") is True,
        "deletion_safe_false": capture.get("deletion_safe_now") is False,
        "parity_snapshot_pass": (latest.get("parity") or {}).get("status") == "PASS",
        "trace_snapshot_pass": (latest.get("trace") or {}).get("status") == "PASS",
        "object_snapshot_pass": (latest.get("object") or {}).get("status") == "PASS",
        "manual_rows_deadness_pass_if_adapter_mediated": (
            capture.get("adapter_mediated") is not True
            or (latest.get("manual_rows_deadness") or {}).get("status") == "PASS"
        ),
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
        "# Zero-Shear Render Consumer Narrowing Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Ready to narrow: `{capture.get('ready_to_narrow')}`",
        f"- Deletion safe now: `{capture.get('deletion_safe_now')}`",
        "",
        "## Required Payload Fields",
        "",
    ]
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in (capture.get("required_payload_fields") or {}).items()
    )
    lines.extend(["", "## Page Mutation Tokens", ""])
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in (capture.get("page_mutation_tokens_present") or {}).items()
    )
    lines.extend(["", "## Adapter-Mediated Projection", ""])
    lines.append(f"- Adapter mediated: `{capture.get('adapter_mediated')}`")
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in (capture.get("adapter_source") or {}).items()
    )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", ""])
    if capture.get("ready_to_narrow"):
        lines.append(
            "Next safe slice: mark or move the zero-shear render consumer through the publication-owned proof surface, "
            "then prove the page mutation rows are compatibility-only before deletion."
        )
    else:
        lines.append(
            "Do not narrow yet. Extend the proof surface until every required zero-shear mutation field is represented."
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_zero_shear_render_consumer_narrowing_readiness_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_zero_shear_render_consumer_narrowing_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_zero_shear_render_consumer_narrowing_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_zero_shear_render_consumer_narrowing_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
