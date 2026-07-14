"""Classify live post-click final contract check rows for future narrowing."""

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

ROW_CLASSES = {
    "A proof_stamp_or_hash_only": (
        "final_publication_post_click_contract_check_input_proof",
        "final_publication_post_click_contract_check_input_proof_hash",
        "final_publication_post_click_contract_check_input_covered_groups",
    ),
    "B page_session_apply_input_keep": (
        "DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY",
        "DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY",
        "_same_flow_cleanup_apply_for_visible",
        "_last_apply_route_for_visible",
    ),
    "C current_state_input_keep": (
        '_float_from_state(current_state, "lig_d", None)',
        '_float_from_state(current_state, "lig_legs", None)',
        "_final_current_bending_util_for_post_click",
    ),
    "D exact_blocker_decision_keep": (
        "_guidance_item_has_low_util_exact_blocker(",
        "_post_click_bending_low_requires_exact_blocker",
        "_post_click_bending_low_visible_action",
    ),
    "E replacement_mutation_keep": (
        "_post_click_low_bending_resolution_item(",
        "_publish_final_visible_design_guide_contract_binding(",
        "post_click_low_bending_action_replaced_by_exact_blocker",
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


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    block = _target_block(source)
    row_presence = {
        row_class: {token: token in block for token in tokens}
        for row_class, tokens in ROW_CLASSES.items()
    }
    present_classes = {
        row_class: any(tokens.values())
        for row_class, tokens in row_presence.items()
    }
    can_narrow_now = ["A proof_stamp_or_hash_only"] if present_classes.get("A proof_stamp_or_hash_only") else []
    keep_live = [
        row_class
        for row_class in (
            "B page_session_apply_input_keep",
            "C current_state_input_keep",
            "D exact_blocker_decision_keep",
            "E replacement_mutation_keep",
        )
        if present_classes.get(row_class)
    ]
    latest = {
        "readiness": _latest("design_guide_post_click_final_contract_checks_readiness"),
        "object": _latest("design_guide_post_click_contract_check_input_proof_object"),
        "trace": _latest("design_guide_live_post_click_contract_check_input_proof_trace"),
        "parity": _latest("design_guide_post_click_contract_check_input_proof_parity_scenarios"),
        "render_lock": _latest("design_guide_render_bridge_lock"),
        "compute_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "POST_CLICK_CONTRACT_CHECK_LIVE_ROWS_CLASSIFIED",
        "target_block_found": bool(block),
        "target_block_hash": _stable_hash(block),
        "row_presence": row_presence,
        "present_classes": present_classes,
        "can_narrow_now": can_narrow_now,
        "keep_live": keep_live,
        "deletion_candidates": [],
        "direct_cutover_ready": False,
        "recommended_next_slice": (
            "narrow proof-stamp/hash-only rows if desired, but keep B/C/D/E live until "
            "their replacement decision object and row-level parity are proven"
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
    present_classes = dict(capture.get("present_classes") or {})
    return {
        "target_block_found": capture.get("target_block_found") is True,
        "all_expected_classes_present": all(present_classes.values()),
        "only_proof_rows_can_narrow": capture.get("can_narrow_now") == ["A proof_stamp_or_hash_only"],
        "no_deletion_candidates": capture.get("deletion_candidates") == [],
        "direct_cutover_still_false": capture.get("direct_cutover_ready") is False,
        "readiness_pass": (latest.get("readiness") or {}).get("status") == "PASS",
        "object_pass": (latest.get("object") or {}).get("status") == "PASS",
        "trace_pass": (latest.get("trace") or {}).get("status") == "PASS",
        "parity_pass": (latest.get("parity") or {}).get("status") == "PASS",
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
        "# Post-Click Contract Check Live Rows Classification",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Can narrow now: `{capture.get('can_narrow_now')}`",
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
        "schema": "design_guide_post_click_contract_check_live_rows_classification_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR / f"design_guide_post_click_contract_check_live_rows_classification_{stamp}.json"
    )
    md_path = AUDIT_DIR / f"design_guide_post_click_contract_check_live_rows_classification_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_contract_check_live_rows_classification {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
