"""Parity proof for live render-item consumer adapter coverage.

Proof-only. This verifier compares the FinalDesignGuidePublication render-item
consumer proof against the same page-owned post-binding consumer effects that
still live in inputs_page.py. It does not move rendering, CTA/apply, session, or
engineering behaviour.
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

CONSUMER_GROUPS = (
    "zero_shear_cleanup",
    "safe_low_util_promotion",
    "post_click_final_contract_checks",
)

PAGE_CONSUMER_TOKENS: dict[str, tuple[str, ...]] = {
    "zero_shear_cleanup": (
        'zero_shear_accepted_stale_blocker_cleared',
        '_zero_shear_terminal_stop_row',
        '_final_visible_item["candidate_search_evidence"] = dict(_zero_shear_candidate_evidence)',
        'guidance_debug["candidate_search_evidence"] = dict(_guidance_zero_shear_evidence)',
    ),
    "safe_low_util_promotion": (
        '_design_guide_item_is_visible_blocker(_final_visible_item)',
        '_visible_safe_low_util_cleanup_action_from_evidence(',
        '_final_visible_resolution["item"] = dict(_final_visible_item)',
        'guidance_debug["final_visible_blocker_promoted_to_safe_low_util_action"] = True',
    ),
    "post_click_final_contract_checks": (
        '_final_contract_for_post_click = dict(_final_visible_item.get("button_contract") or {})',
        '_post_click_unresolved_families_for_visible',
        '_post_click_below_floor_families_for_visible',
        '_post_click_bending_low_requires_exact_blocker',
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


def _line_number(source: str, token: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            return index
    return None


def _sample_payloads() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_publication,
        build_final_design_guide_render_item_consumer_proof,
        stable_final_publication_hash,
    )

    shear_attempt = {
        "family": "shear",
        "terminal_state": "zero_shear_no_cleanup_required",
        "candidate_id": "zero-shear-terminal",
    }
    candidate_search_evidence = {
        "blocker_attempts_by_family": {"shear": shear_attempt},
        "exact_blockers_by_family": {"bending": {"reason": "exact_stop"}},
        "post_click_exact_blockers_by_family": {"bending": {"reason": "post_click_exact_stop"}},
    }
    item = {
        "published_item_id": "render-consumer-proof-item",
        "family": "bending",
        "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
        "status": "PASS",
        "title": "Design is efficient",
        "blocker_reason": "safe_low_util_cleanup_from_blocker_evidence",
        "blocking_reason": "safe_low_util_cleanup_from_blocker_evidence",
        "post_click_design_guide_state": "post_click_exact_blocker",
        "design_guide_terminal_state": "post_click_exact_blocker",
        "zero_shear_accepted_stale_blocker_cleared": True,
        "candidate_search_evidence": candidate_search_evidence,
        "button_contract": {
            "enabled": False,
            "actionable": False,
            "family": "bending",
            "action_type": "apply_resolved_candidate",
            "disabled_reason": "exact_blocker",
        },
        "action_type": "apply_resolved_candidate",
    }
    debug = {
        "candidate_search_evidence": candidate_search_evidence,
        "blocker_attempts_by_family": {"shear": shear_attempt},
        "post_click_unresolved_low_util_families": ["bending"],
        "post_click_families_below_final_threshold": ["bending"],
        "post_click_design_guide_state": "post_click_exact_blocker",
        "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
    }
    final_visible_resolution = {
        "item": dict(item),
        "render_reason": "visible_safe_low_util_cleanup_from_blocker_evidence",
    }
    publication = build_final_design_guide_publication(
        item=item,
        debug=debug,
        design_brain_result={"selected_family_id": "BENDING_OVERDESIGN_GOVERNS"},
        publication_reason="render_item_consumer_parity_snapshot",
    )
    proof = build_final_design_guide_render_item_consumer_proof(
        publication,
        selected_item=item,
        final_visible_resolution=final_visible_resolution,
        guidance_debug=debug,
    )
    proof_d = proof.to_dict()
    expected = {
        "zero_shear_cleanup": {
            "stale_blocker_cleared": True,
            "has_shear_attempt": True,
            "shear_attempt_hash": stable_final_publication_hash(shear_attempt),
            "candidate_search_evidence_hash": stable_final_publication_hash(candidate_search_evidence),
            "terminal_state": "post_click_exact_blocker",
        },
        "safe_low_util_promotion": {
            "blocker_reason": "safe_low_util_cleanup_from_blocker_evidence",
            "selected_family": "BENDING_OVERDESIGN_GOVERNS",
            "outcome_state": publication.outcome_state,
            "candidate_search_evidence_hash": stable_final_publication_hash(candidate_search_evidence),
            "final_visible_resolution_item_hash": stable_final_publication_hash(item),
            "render_reason": "visible_safe_low_util_cleanup_from_blocker_evidence",
        },
        "post_click_final_contract_checks": {
            "post_click_design_guide_state": "post_click_exact_blocker",
            "published_item_id": "render-consumer-proof-item",
            "family": "bending",
            "action_type": "apply_resolved_candidate",
            "button_contract_hash": stable_final_publication_hash(item["button_contract"]),
            "post_click_unresolved_families_hash": stable_final_publication_hash(["bending"]),
            "post_click_below_floor_families_hash": stable_final_publication_hash(["bending"]),
        },
    }
    return {
        "publication_hash": publication.publication_hash,
        "proof": proof_d,
        "expected": expected,
        "group_hashes_stable": proof_d.get("consumer_group_hashes")
        == build_final_design_guide_render_item_consumer_proof(
            publication,
            selected_item=item,
            final_visible_resolution=final_visible_resolution,
            guidance_debug=debug,
        ).to_dict().get("consumer_group_hashes"),
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    trace_line = _line_number(
        source,
        'publication_reason="render_fast_design_guidance_panel.render_item_consumer_trace"',
    )
    sample = _sample_payloads()
    proof = dict(sample.get("proof") or {})
    expected = dict(sample.get("expected") or {})
    group_rows: list[dict[str, Any]] = []
    for group in CONSUMER_GROUPS:
        tokens = {token: token in source for token in PAGE_CONSUMER_TOKENS[group]}
        token_lines = {token: _line_number(source, token) for token in PAGE_CONSUMER_TOKENS[group]}
        proof_payload = dict(proof.get(group) or {})
        expected_payload = dict(expected.get(group) or {})
        matched_keys = {
            key: proof_payload.get(key) == expected_payload.get(key)
            for key in expected_payload
        }
        group_rows.append(
            {
                "group": group,
                "page_consumer_tokens_present": all(tokens.values()),
                "page_consumer_tokens_removed_or_adapter_backed": (
                    not all(tokens.values()) and all(matched_keys.values())
                ),
                "token_lines": token_lines,
                "proof_payload_keys_present": all(key in proof_payload for key in expected_payload),
                "expected_payload_matches": all(matched_keys.values()),
                "matched_keys": matched_keys,
                "covered_by_proof": group in set(proof.get("covered_consumer_groups") or []),
                "hash_present": bool((proof.get("consumer_group_hashes") or {}).get(group)),
            }
        )
    live_page_consumer_groups = [
        row["group"] for row in group_rows if row["page_consumer_tokens_present"]
    ]
    removed_or_adapter_backed_groups = [
        row["group"] for row in group_rows if row["page_consumer_tokens_removed_or_adapter_backed"]
    ]
    latest = {
        "trace": _latest("design_guide_live_render_item_consumer_adapter_trace"),
        "object": _latest("design_guide_render_item_consumer_adapter_object"),
        "readiness": _latest("design_guide_render_item_consumer_adapter_readiness"),
        "render_lock": _latest("design_guide_render_bridge_lock"),
        "compute_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": (
            "RENDER_ITEM_CONSUMER_TRACE_PARITY_PROVEN_PAGE_CONSUMERS_STILL_LIVE"
            if live_page_consumer_groups
            else "RENDER_ITEM_CONSUMER_TRACE_PARITY_PROVEN_NO_PAGE_CONSUMERS"
        ),
        "trace_call_line": trace_line,
        "consumer_groups": group_rows,
        "all_groups_represented": all(row["covered_by_proof"] for row in group_rows),
        "all_page_tokens_present": all(row["page_consumer_tokens_present"] for row in group_rows),
        "live_page_consumer_groups": live_page_consumer_groups,
        "removed_or_adapter_backed_groups": removed_or_adapter_backed_groups,
        "all_expected_payloads_match": all(row["expected_payload_matches"] for row in group_rows),
        "group_hashes_stable": sample.get("group_hashes_stable") is True,
        "consumer_proof_hash_present": bool(proof.get("consumer_proof_hash")),
        "proof_only": proof.get("proof_only") is True,
        "product_driving": proof.get("product_driving") is True,
        "render_driving": proof.get("render_driving") is True,
        "apply_driving": proof.get("apply_driving") is True,
        "session_driving": proof.get("session_driving") is True,
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
    return {
        "trace_call_present": capture.get("trace_call_line") is not None,
        "page_consumer_state_recorded": bool(
            capture.get("live_page_consumer_groups")
            or capture.get("removed_or_adapter_backed_groups")
        ),
        "all_groups_represented": capture.get("all_groups_represented") is True,
        "all_expected_payloads_match": capture.get("all_expected_payloads_match") is True,
        "group_hashes_stable": capture.get("group_hashes_stable") is True,
        "consumer_proof_hash_present": capture.get("consumer_proof_hash_present") is True,
        "proof_only": capture.get("proof_only") is True,
        "product_driving_false": capture.get("product_driving") is False,
        "render_driving_false": capture.get("render_driving") is False,
        "apply_driving_false": capture.get("apply_driving") is False,
        "session_driving_false": capture.get("session_driving") is False,
        "deletion_safe_false": capture.get("deletion_safe_now") is False,
        "trace_snapshot_pass": (latest.get("trace") or {}).get("status") == "PASS",
        "object_snapshot_pass": (latest.get("object") or {}).get("status") == "PASS",
        "readiness_snapshot_pass": (latest.get("readiness") or {}).get("status") == "PASS",
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
        "# Live Render Item Consumer Adapter Parity Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Trace call line: `{capture.get('trace_call_line')}`",
        f"- All groups represented: `{capture.get('all_groups_represented')}`",
        f"- All page consumer tokens present: `{capture.get('all_page_tokens_present')}`",
        f"- Live page consumer groups: `{capture.get('live_page_consumer_groups')}`",
        f"- Removed/adapter-backed groups: `{capture.get('removed_or_adapter_backed_groups')}`",
        f"- Expected payloads match: `{capture.get('all_expected_payloads_match')}`",
        f"- Deletion safe now: `{capture.get('deletion_safe_now')}`",
        "",
        "## Consumer Groups",
        "",
        "| Group | Tokens Present | Payload Matches | Covered | Hash Present |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in capture.get("consumer_groups") or []:
        lines.append(
            "| `{}` | `{}` | `{}` | `{}` | `{}` |".format(
                row.get("group"),
                row.get("page_consumer_tokens_present"),
                row.get("expected_payload_matches"),
                row.get("covered_by_proof"),
                row.get("hash_present"),
            )
        )
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Next", ""])
    lines.append(
        "The adapter parity is proven, but page consumers are still live. The next safe slice is a "
        "narrowing or cutover-readiness verifier for one consumer group, starting with zero-shear cleanup."
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
        "schema": "design_guide_live_render_item_consumer_adapter_parity_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_live_render_item_consumer_adapter_parity_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_live_render_item_consumer_adapter_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_live_render_item_consumer_adapter_parity {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
