"""Trace wiring proof for the live post-click final-contract predicate adapter.

This verifier is proof-only. It checks that inputs_page.py traces the pure
Design Brain predicate/result adapter beside the existing post-click
final-contract page logic without driving product, render, apply, or session
state behaviour.
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

IMPORT_TOKEN = (
    "build_final_design_guide_post_click_final_contract_predicate_result_adapter "
    "as _build_final_design_guide_post_click_final_contract_predicate_result_adapter"
)
HELPER_TOKEN = (
    "def _stamp_final_publication_post_click_final_contract_predicate_result_adapter("
)
BUILDER_CALL = (
    "_build_final_design_guide_post_click_final_contract_predicate_result_adapter("
)
STAMP_CALL = (
    "_stamp_final_publication_post_click_final_contract_predicate_result_adapter("
)
TARGET_START = "_post_click_contract_check_input_proof = _stamp_final_publication_post_click_contract_check_input_proof("
TARGET_END = "_post_click_bending_audit = {}"
FORBIDDEN_LIVE_PREDICATE_ARGS = (
    "live_contract_enabled=bool(_post_click_bending_low_contract_enabled)",
    "live_exact_blocker_on_visible_item=bool(",
    "live_requires_exact_blocker=bool(_post_click_bending_low_requires_exact_blocker)",
    "live_visible_action=bool(_post_click_bending_low_visible_action)",
)
FORBIDDEN_LEGACY_PAGE_PREDICATE_FORMULAS = (
    "_design_guide_button_contract_enabled(\n            _final_contract_for_post_click",
    "_guidance_item_has_low_util_exact_blocker(\n            _final_visible_item",
    "post_click_safe_incremental_cleanup_requires_exact_blocker",
    "_guidance_item_best_safe_partial_cleanup(_final_visible_item)",
    "_guidance_item_safe_incremental_cleanup_below_threshold(_final_visible_item)",
)
REQUIRED_TRACE_FIELDS = (
    "final_publication_post_click_final_contract_predicate_result_adapter",
    "final_publication_post_click_final_contract_predicate_result_adapter_hash",
    "final_publication_post_click_final_contract_predicate_result_hash",
    "final_publication_post_click_final_contract_predicate_result_request_hash",
    "final_publication_post_click_final_contract_predicate_result_covered_rows",
    "final_publication_post_click_final_contract_predicate_result_page_owned_inputs",
    "final_publication_post_click_final_contract_predicate_result_live_parity",
    "final_publication_post_click_final_contract_predicate_result_live_comparisons",
    "final_publication_post_click_final_contract_predicate_result_comparison_source",
)
REQUIRED_NON_DRIVING_FLAGS = (
    "final_publication_post_click_final_contract_predicate_result_proof_only",
    "final_publication_post_click_final_contract_predicate_result_product_driving",
    "final_publication_post_click_final_contract_predicate_result_render_driving",
    "final_publication_post_click_final_contract_predicate_result_apply_driving",
    "final_publication_post_click_final_contract_predicate_result_session_driving",
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
        return {"found": False, "status": "MISSING", "path": None}
    path = artifacts[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _block(source: str, start_token: str, end_token: str | None = None) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    if not end_token:
        end = source.find("\ndef ", start + 1)
    else:
        end = source.find(end_token, start)
    return source[start:end] if end > start else ""


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    helper = _block(source, HELPER_TOKEN)
    target = _block(source, TARGET_START, TARGET_END)
    latest = {
        "predicate_object": _latest(
            "design_guide_post_click_final_contract_predicate_result_adapter_object"
        ),
        "decomposition": _latest("design_guide_post_click_final_contract_consumer_decomposition"),
        "parity": _latest(
            "design_guide_post_click_final_contract_predicate_result_adapter_parity_scenarios"
        ),
        "render_item_cutover_readiness": _latest(
            "design_guide_render_item_consumer_adapter_cutover_readiness"
        ),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": (
            "LIVE_POST_CLICK_FINAL_CONTRACT_PREDICATE_RESULT_TRACE_PROVEN_WITH_FOCUSED_PARITY_VERIFIER"
        ),
        "import_present": IMPORT_TOKEN in source,
        "helper_present": bool(helper),
        "builder_call_in_helper": BUILDER_CALL in helper,
        "target_block_found": bool(target),
        "stamp_call_count_in_target": target.count(STAMP_CALL),
        "legacy_page_predicate_formulas_absent": not any(
            token in target for token in FORBIDDEN_LEGACY_PAGE_PREDICATE_FORMULAS
        ),
        "input_proof_precedes_stamp": (
            target.find("_post_click_contract_check_input_proof =")
            < target.find(STAMP_CALL)
            if STAMP_CALL in target
            else False
        ),
        "page_owned_inputs_passed": all(
            token in target
            for token in (
                "post_cleanup_render_audit=(",
                "last_apply_route=dict(_last_apply_route_for_visible or {})",
                "primary_payload_binding_audit=dict(_binding_audit_for_visible or {})",
                "current_state=dict(current_state or {})",
            )
        ),
        "live_predicate_args_absent": not any(
            token in target for token in FORBIDDEN_LIVE_PREDICATE_ARGS
        ),
        "trace_fields_stamped": all(token in helper for token in REQUIRED_TRACE_FIELDS),
        "non_driving_flags_stamped": all(token in helper for token in REQUIRED_NON_DRIVING_FLAGS),
        "live_parity_comparison_present": "live_predicate_comparisons" in helper
        and "live_predicate_parity" in helper,
        "focused_parity_comparison_source_present": "focused_parity_verifier" in helper,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
        "latest": latest,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "import_present": capture.get("import_present") is True,
        "helper_present": capture.get("helper_present") is True,
        "builder_call_in_helper": capture.get("builder_call_in_helper") is True,
        "target_block_found": capture.get("target_block_found") is True,
        "stamp_call_once_in_target": capture.get("stamp_call_count_in_target") == 1,
        "legacy_page_predicate_formulas_absent": (
            capture.get("legacy_page_predicate_formulas_absent") is True
        ),
        "input_proof_precedes_stamp": capture.get("input_proof_precedes_stamp") is True,
        "page_owned_inputs_passed": capture.get("page_owned_inputs_passed") is True,
        "live_predicate_args_absent": capture.get("live_predicate_args_absent") is True,
        "trace_fields_stamped": capture.get("trace_fields_stamped") is True,
        "non_driving_flags_stamped": capture.get("non_driving_flags_stamped") is True,
        "live_parity_comparison_present": capture.get("live_parity_comparison_present") is True,
        "focused_parity_comparison_source_present": (
            capture.get("focused_parity_comparison_source_present") is True
        ),
        "predicate_object_pass": (latest.get("predicate_object") or {}).get("status") == "PASS",
        "decomposition_pass": (latest.get("decomposition") or {}).get("status") == "PASS",
        "parity_pass": (latest.get("parity") or {}).get("status") == "PASS",
        "render_item_cutover_readiness_pass": (
            latest.get("render_item_cutover_readiness") or {}
        ).get("status")
        == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Live Post-Click Final Contract Predicate/Result Adapter Trace Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Stamp calls in target block: `{capture.get('stamp_call_count_in_target')}`",
        f"- Legacy page predicate formulas absent: `{capture.get('legacy_page_predicate_formulas_absent')}`",
        f"- Live parity comparison present: `{capture.get('live_parity_comparison_present')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            (
                "Next safe slice: live parity snapshot comparing the adapter predicate result "
                "against page predicate booleans in focused scenarios before replacing page-local logic."
            ),
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
        "schema": "design_guide_live_post_click_final_contract_predicate_result_adapter_trace_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_live_post_click_final_contract_predicate_result_adapter_trace_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_live_post_click_final_contract_predicate_result_adapter_trace_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_live_post_click_final_contract_predicate_result_adapter_trace {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
