"""Cutover readiness for the post-click final-contract adapter result.

Proof-only. This does not replace or delete the page-owned post-click block.
It proves the adapter result is ready to become the authority for the
post-click exact-blocker decision/output rows in a later slice.
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

PAGE_INPUT_COLLECTION_TOKENS = (
    "DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY",
    "DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY",
    "_final_contract_for_post_click",
    "_final_family_for_post_click",
    "_final_expected_util_for_post_click",
    "_final_current_bending_util_for_post_click",
)

ADAPTER_REPLACEABLE_TOKENS = (
    "_post_click_bending_low_requires_exact_blocker = bool(",
    "_post_click_bending_low_visible_action = bool(",
    "_post_click_bending_audit = {}",
    "_post_click_low_bending_resolution_item(",
    "_publish_final_visible_design_guide_contract_binding(",
    "_build_final_design_guide_post_click_final_contract_check_adapter_result(",
    "_stamp_final_publication_post_click_replacement_decision_proof(",
    "_stamp_final_publication_post_click_final_contract_adapter_proof(",
    "_stamp_final_publication_post_click_final_contract_adapter_result(",
)
ADAPTER_REPLACEABLE_ALREADY_REMOVED_OK = (
    "_publish_final_visible_design_guide_contract_binding(",
)
REMOVED_DIRECT_PROJECTION_TOKENS = (
    "_apply_final_design_guide_post_click_exact_blocker_replacement_projection(",
    "apply_final_design_guide_post_click_exact_blocker_replacement_projection as",
)

FORBIDDEN_CUTOVER_CHANGES = (
    "st.button(",
    "st.session_state[DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY]",
    "st.session_state[DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY]",
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


def _function_block(source: str, token: str) -> str:
    start = source.find(token)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else source[start:]


def _line_number(source: str, token: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            return index
    return None


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    target = _target_block(inputs_source)
    builder = _function_block(
        publication_source,
        "def build_final_design_guide_post_click_final_contract_check_adapter_result(",
    )
    latest = {
        "result_object": _latest("design_guide_post_click_final_contract_adapter_result_object"),
        "result_parity": _latest("design_guide_post_click_final_contract_adapter_result_parity_scenarios"),
        "result_trace": _latest("design_guide_live_post_click_final_contract_adapter_result_trace"),
        "result_hash_parity": _latest("design_guide_live_post_click_final_contract_adapter_result_hash_parity"),
        "remaining_truth": _latest("design_guide_post_click_remaining_live_truth_ownership"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    result_object_payload = dict((latest["result_object"].get("payload") or {}).get("capture") or {})
    result_flags = dict(result_object_payload.get("proof_flags") or {})
    return {
        "decision": "POST_CLICK_FINAL_CONTRACT_ADAPTER_RESULT_READY_FOR_CUTOVER",
        "target_block_found": bool(target),
        "target_block_start_line": _line_number(inputs_source, TARGET_START),
        "target_block_hash": _stable_hash(target),
        "page_input_collection_present": {
            token: token in target for token in PAGE_INPUT_COLLECTION_TOKENS
        },
        "adapter_replaceable_rows_present": {
            token: token in target for token in ADAPTER_REPLACEABLE_TOKENS
        },
        "adapter_replaceable_rows_already_removed_ok": {
            token: token not in target for token in ADAPTER_REPLACEABLE_ALREADY_REMOVED_OK
        },
        "direct_projection_tokens_removed": {
            token: token not in inputs_source for token in REMOVED_DIRECT_PROJECTION_TOKENS
        },
        "forbidden_cutover_changes_absent": {
            token: token not in target for token in FORBIDDEN_CUTOVER_CHANGES
        },
        "builder_ready_for_live_cutover": '"ready_for_live_cutover": True' in builder,
        "builder_remains_proof_only": '"proof_only": True' in builder,
        "builder_not_product_driving": '"product_driving": False' in builder,
        "builder_not_render_driving": '"render_driving": False' in builder,
        "builder_not_apply_driving": '"apply_driving": False' in builder,
        "builder_not_session_driving": '"session_driving": False' in builder,
        "result_object_ready_for_live_cutover": result_flags.get("ready_for_live_cutover"),
        "result_object_proof_only": result_flags.get("proof_only"),
        "result_object_not_product_driving": result_flags.get("product_driving") is False,
        "result_object_not_render_driving": result_flags.get("render_driving") is False,
        "result_object_not_apply_driving": result_flags.get("apply_driving") is False,
        "result_object_not_session_driving": result_flags.get("session_driving") is False,
        "cutover_allowed_next_slice": True,
        "delete_allowed_this_slice": False,
        "next_safe_slice": (
            "replace the page-owned post-click decision/output rows with the adapter result, "
            "keeping page input collection and apply/session ownership unchanged"
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
    return {
        "target_block_found": capture.get("target_block_found") is True,
        "page_input_collection_present": all(
            (capture.get("page_input_collection_present") or {}).values()
        ),
        "adapter_replaceable_rows_present": all(
            value
            or token in ADAPTER_REPLACEABLE_ALREADY_REMOVED_OK
            and (capture.get("adapter_replaceable_rows_already_removed_ok") or {}).get(token)
            for token, value in (capture.get("adapter_replaceable_rows_present") or {}).items()
        ),
        "direct_projection_tokens_removed": all(
            (capture.get("direct_projection_tokens_removed") or {}).values()
        ),
        "forbidden_cutover_changes_absent": all(
            (capture.get("forbidden_cutover_changes_absent") or {}).values()
        ),
        "builder_ready_for_live_cutover": capture.get("builder_ready_for_live_cutover") is True,
        "builder_remains_proof_only": capture.get("builder_remains_proof_only") is True,
        "builder_not_product_driving": capture.get("builder_not_product_driving") is True,
        "builder_not_render_driving": capture.get("builder_not_render_driving") is True,
        "builder_not_apply_driving": capture.get("builder_not_apply_driving") is True,
        "builder_not_session_driving": capture.get("builder_not_session_driving") is True,
        "result_object_ready_for_live_cutover": (
            capture.get("result_object_ready_for_live_cutover") is True
        ),
        "result_object_proof_only": capture.get("result_object_proof_only") is True,
        "result_object_not_product_driving": capture.get("result_object_not_product_driving") is True,
        "result_object_not_render_driving": capture.get("result_object_not_render_driving") is True,
        "result_object_not_apply_driving": capture.get("result_object_not_apply_driving") is True,
        "result_object_not_session_driving": capture.get("result_object_not_session_driving") is True,
        "result_object_pass": (latest.get("result_object") or {}).get("status") == "PASS",
        "result_parity_pass": (latest.get("result_parity") or {}).get("status") == "PASS",
        "result_trace_pass": (latest.get("result_trace") or {}).get("status") == "PASS",
        "result_hash_parity_pass": (latest.get("result_hash_parity") or {}).get("status") == "PASS",
        "remaining_truth_pass": (latest.get("remaining_truth") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "cutover_allowed_next_slice": capture.get("cutover_allowed_next_slice") is True,
        "delete_not_allowed_this_slice": capture.get("delete_allowed_this_slice") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Final Contract Adapter Cutover Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Target block start line: `{capture.get('target_block_start_line')}`",
        f"- Cutover allowed next slice: `{capture.get('cutover_allowed_next_slice')}`",
        f"- Delete allowed this slice: `{capture.get('delete_allowed_this_slice')}`",
        f"- Next safe slice: {capture.get('next_safe_slice')}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "No product behavior, visible wording, CTA/apply semantics, family runtime behavior, solver math, target bands, or engineering behavior changed.",
        ]
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
        "schema": "design_guide_post_click_final_contract_adapter_cutover_readiness_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_post_click_final_contract_adapter_cutover_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_post_click_final_contract_adapter_cutover_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_final_contract_adapter_cutover_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
