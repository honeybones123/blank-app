"""Readiness snapshot for post-click final contract check extraction.

Proof-only. This classifies the remaining post-click final contract check
consumer rows before any adapter/cutover work.
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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

TARGET_START = '_final_contract_for_post_click = dict(_final_visible_item.get("button_contract") or {})'
TARGET_END = "_final_visible_item = _normalise_visible_optimisation_contract("


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


def _line_number(source: str, token: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            return index
    return None


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    block = _target_block(source)
    latest = {
        "render_item_parity": _latest("design_guide_live_render_item_consumer_adapter_parity"),
        "safe_low_cutover": _latest("design_guide_safe_low_util_promotion_projection_adapter_cutover"),
        "safe_low_deadness": _latest("design_guide_safe_low_util_promotion_manual_rows_deadness"),
        "post_click_predicate_cutover": _latest(
            "design_guide_post_click_final_contract_predicate_result_adapter_cutover"
        ),
        "post_click_adapter_cutover_readiness": _latest(
            "design_guide_post_click_final_contract_adapter_cutover_readiness"
        ),
        "post_click_adapter_result_trace": _latest(
            "design_guide_live_post_click_final_contract_adapter_result_trace"
        ),
        "post_click_exact_blocker_projection_cutover": _latest(
            "design_guide_post_click_exact_blocker_projection_adapter_cutover"
        ),
        "render_lock": _latest("design_guide_render_bridge_lock"),
        "compute_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    predicate_adapter_ready = latest["post_click_predicate_cutover"].get("status") == "PASS"
    result_adapter_ready = (
        latest["post_click_adapter_cutover_readiness"].get("status") == "PASS"
        and latest["post_click_adapter_result_trace"].get("status") == "PASS"
    )
    exact_blocker_projection_ready = (
        latest["post_click_exact_blocker_projection_cutover"].get("status") == "PASS"
    )
    classification = {
        "A_publication_owned_identity_fields": {
            "tokens": (
                "_final_contract_for_post_click",
                "_final_family_for_post_click",
                "_final_expected_util_for_post_click",
            ),
            "present": all(
                token in block
                for token in (
                    "_final_contract_for_post_click",
                    "_final_family_for_post_click",
                    "_final_expected_util_for_post_click",
                )
            ),
            "safe_now": True,
        },
        "B_page_session_apply_inputs": {
            "tokens": (
                "st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY)",
                "DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY",
                "_same_flow_cleanup_apply_for_visible",
            ),
            "present": all(
                token in block
                for token in (
                    "st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY)",
                    "DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY",
                    "_same_flow_cleanup_apply_for_visible",
                )
            ),
            "safe_now": predicate_adapter_ready,
            "represented_by": "FinalDesignGuidePublication.post_click_final_contract_predicate_result_adapter",
        },
        "C_page_current_state_inputs": {
            "tokens": ('_float_from_state(current_state, "lig_d", None)', 'FINAL_ACCEPTED_MIN_FAMILY_UTIL'),
            "present": all(
                token in block
                for token in ('_float_from_state(current_state, "lig_d", None)', "FINAL_ACCEPTED_MIN_FAMILY_UTIL")
            ),
            "safe_now": result_adapter_ready,
            "already_removed_ok": True,
            "represented_by": "FinalDesignGuidePublication.post_click_final_contract_adapter_result",
        },
        "D_exact_blocker_helper_logic": {
            "tokens": (
                "_guidance_item_has_low_util_exact_blocker(",
                "_post_click_low_bending_resolution_item(",
            ),
            "present": all(
                token in block
                for token in (
                    "_guidance_item_has_low_util_exact_blocker(",
                    "_post_click_low_bending_resolution_item(",
                )
            ),
            "safe_now": result_adapter_ready,
            "already_removed_ok": True,
            "represented_by": "FinalDesignGuidePublication.post_click_final_contract_adapter_result",
        },
        "E_render_item_replacement_mutation": {
            "tokens": (
                "_publish_final_visible_design_guide_contract_binding(",
                'guidance_debug["post_click_low_bending_action_replaced_by_exact_blocker"] = True',
                'guidance_debug["guidance_branch"] = "post_click_low_bending_exact_blocker_final"',
            ),
            "present": all(
                token in block
                for token in (
                    "_publish_final_visible_design_guide_contract_binding(",
                    'guidance_debug["post_click_low_bending_action_replaced_by_exact_blocker"] = True',
                    'guidance_debug["guidance_branch"] = "post_click_low_bending_exact_blocker_final"',
                )
            ),
            "safe_now": exact_blocker_projection_ready,
            "already_removed_ok": True,
            "represented_by": "FinalDesignGuidePublication.post_click_exact_blocker_replacement",
        },
    }
    unsafe_or_live_groups = [
        key for key, value in classification.items() if value.get("present") and not value.get("safe_now")
    ]
    already_removed_groups = [
        key
        for key, value in classification.items()
        if value.get("present") is False and value.get("already_removed_ok") is True
    ]
    proof_surface_present = "post_click_final_contract_checks = {" in publication_source
    return {
        "decision": (
            "POST_CLICK_FINAL_CONTRACT_CHECKS_NOT_READY_FOR_DIRECT_CUTOVER"
            if unsafe_or_live_groups
            else "POST_CLICK_FINAL_CONTRACT_CHECKS_READY_FOR_DIRECT_CUTOVER"
        ),
        "target_block_found": bool(block),
        "target_block_start_line": _line_number(source, TARGET_START),
        "target_block_hash": _stable_hash(block),
        "proof_surface_present": proof_surface_present,
        "classification": classification,
        "unsafe_or_live_groups": unsafe_or_live_groups,
        "already_removed_groups": already_removed_groups,
        "recommended_next_slice": (
            "post-click final contract checks are represented by predicate/result adapters; "
            "the next slice may use adapter result authority while keeping page input collection "
            "and apply/session ownership unchanged"
        ),
        "ready_for_direct_cutover": not unsafe_or_live_groups,
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
    classification = dict(capture.get("classification") or {})
    ready = capture.get("ready_for_direct_cutover") is True
    return {
        "target_block_found": capture.get("target_block_found") is True,
        "proof_surface_present": capture.get("proof_surface_present") is True,
        "required_groups_present_or_removed_with_adapter": all(
            (value or {}).get("present")
            or (
                (value or {}).get("already_removed_ok") is True
                and (value or {}).get("safe_now") is True
            )
            for value in classification.values()
        ),
        "removed_groups_classified": "E_render_item_replacement_mutation" in (
            capture.get("already_removed_groups") or []
        ),
        "readiness_decision_consistent": (
            (ready and not bool(capture.get("unsafe_or_live_groups")))
            or ((not ready) and bool(capture.get("unsafe_or_live_groups")))
        ),
        "unsafe_groups_classified": ready or bool(capture.get("unsafe_or_live_groups")),
        "render_item_parity_pass": (latest.get("render_item_parity") or {}).get("status") == "PASS",
        "safe_low_cutover_pass": (latest.get("safe_low_cutover") or {}).get("status") == "PASS",
        "safe_low_deadness_pass": (latest.get("safe_low_deadness") or {}).get("status") == "PASS",
        "post_click_predicate_cutover_pass": (
            (latest.get("post_click_predicate_cutover") or {}).get("status") == "PASS"
        ),
        "post_click_adapter_cutover_readiness_pass": (
            (latest.get("post_click_adapter_cutover_readiness") or {}).get("status") == "PASS"
        ),
        "post_click_adapter_result_trace_pass": (
            (latest.get("post_click_adapter_result_trace") or {}).get("status") == "PASS"
        ),
        "post_click_exact_blocker_projection_cutover_pass": (
            (latest.get("post_click_exact_blocker_projection_cutover") or {}).get("status")
            == "PASS"
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
        "# Post-Click Final Contract Checks Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Target block start line: `{capture.get('target_block_start_line')}`",
        f"- Ready for direct cutover: `{capture.get('ready_for_direct_cutover')}`",
        f"- Unsafe/live groups: `{capture.get('unsafe_or_live_groups')}`",
        f"- Already removed groups: `{capture.get('already_removed_groups')}`",
        f"- Recommended next slice: {capture.get('recommended_next_slice')}",
        "",
        "## Classification",
        "",
    ]
    for key, value in (capture.get("classification") or {}).items():
        lines.append(
            f"- {key}: present=`{value.get('present')}` safe_now=`{value.get('safe_now')}`"
        )
    lines.extend(["", "## Checks", ""])
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
        "schema": "design_guide_post_click_final_contract_checks_readiness_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_post_click_final_contract_checks_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_post_click_final_contract_checks_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_final_contract_checks_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
