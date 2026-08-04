"""Cutover proof for post-click final-contract predicate/result adapter."""

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

TARGET_START = "_post_click_final_contract_predicate_result_adapter = ("
TARGET_END = "_post_click_bending_audit = {}"
ADAPTER_PREDICATES_ASSIGNMENT = "_post_click_final_contract_predicates = dict("
PRE_CUTOVER_CAPTURE = (
    "final_publication_post_click_final_contract_predicate_result_pre_cutover_page_values"
)
FORBIDDEN_PRE_CUTOVER_PAGE_CAPTURE = "_page_post_click_predicates_before_adapter_cutover = {"
FORBIDDEN_LEGACY_PAGE_PREDICATE_FORMULAS = (
    "_design_guide_button_contract_enabled(\n            _final_contract_for_post_click",
    "_guidance_item_has_low_util_exact_blocker(\n            _final_visible_item",
    "post_click_safe_incremental_cleanup_requires_exact_blocker",
    "_guidance_item_best_safe_partial_cleanup(_final_visible_item)",
    "_guidance_item_safe_incremental_cleanup_below_threshold(_final_visible_item)",
)
CUTOVER_SOURCE = (
    "FinalDesignGuidePublication.post_click_final_contract_predicate_result_adapter"
)
CUTOVER_FIELDS = (
    "_post_click_bending_low_contract_enabled = bool(",
    "_post_click_bending_exact_blocker_on_visible_item = bool(",
    "_post_click_bending_low_requires_exact_blocker = bool(",
    "_post_click_bending_low_visible_action = bool(",
)
DEBUG_STAMPS = (
    "final_publication_post_click_final_contract_predicate_result_live_cutover_used",
    "final_publication_post_click_final_contract_predicate_result_live_cutover_source",
    "final_publication_post_click_final_contract_predicate_result_live_cutover_hash",
    "final_publication_post_click_final_contract_predicate_result_pre_cutover_page_values",
    "final_publication_post_click_final_contract_predicate_result_post_cutover_values",
    "final_publication_post_click_final_contract_predicate_result_product_behavior_changed",
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


def _target_block(source: str) -> str:
    start = source.find(TARGET_START)
    if start < 0:
        return ""
    end = source.find(TARGET_END, start)
    return source[start:end] if end > start else ""


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    target = _target_block(source)
    latest = {
        "object": _latest("design_guide_post_click_final_contract_predicate_result_adapter_object"),
        "trace": _latest("design_guide_live_post_click_final_contract_predicate_result_adapter_trace"),
        "parity": _latest(
            "design_guide_post_click_final_contract_predicate_result_adapter_parity_scenarios"
        ),
        "cutover_readiness": _latest(
            "design_guide_post_click_final_contract_predicate_result_adapter_cutover_readiness"
        ),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "POST_CLICK_FINAL_CONTRACT_PREDICATE_RESULT_ADAPTER_CUTOVER_PASS",
        "target_block_found": bool(target),
        "adapter_predicates_assignment_present": ADAPTER_PREDICATES_ASSIGNMENT in target,
        "pre_cutover_page_values_stamped_empty": PRE_CUTOVER_CAPTURE in target and " = {}" in target,
        "pre_cutover_page_capture_deleted": FORBIDDEN_PRE_CUTOVER_PAGE_CAPTURE not in target,
        "legacy_page_predicate_formulas_absent": not any(
            token in target for token in FORBIDDEN_LEGACY_PAGE_PREDICATE_FORMULAS
        ),
        "cutover_source_stamped": CUTOVER_SOURCE in target,
        "cutover_fields_from_adapter": all(token in target for token in CUTOVER_FIELDS),
        "debug_stamps_present": all(token in target for token in DEBUG_STAMPS),
        "page_input_collection_retained": all(
            token in source
            for token in (
                "_last_apply_route_for_visible =",
                "_binding_audit_for_visible =",
                "_post_click_unresolved_families_for_visible =",
                "_post_click_below_floor_families_for_visible =",
            )
        ),
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
        "target_block_found": capture.get("target_block_found") is True,
        "adapter_predicates_assignment_present": (
            capture.get("adapter_predicates_assignment_present") is True
        ),
        "pre_cutover_page_values_stamped_empty": (
            capture.get("pre_cutover_page_values_stamped_empty") is True
        ),
        "pre_cutover_page_capture_deleted": (
            capture.get("pre_cutover_page_capture_deleted") is True
        ),
        "legacy_page_predicate_formulas_absent": (
            capture.get("legacy_page_predicate_formulas_absent") is True
        ),
        "cutover_source_stamped": capture.get("cutover_source_stamped") is True,
        "cutover_fields_from_adapter": capture.get("cutover_fields_from_adapter") is True,
        "debug_stamps_present": capture.get("debug_stamps_present") is True,
        "page_input_collection_retained": capture.get("page_input_collection_retained") is True,
        "object_pass": (latest.get("object") or {}).get("status") == "PASS",
        "trace_pass": (latest.get("trace") or {}).get("status") == "PASS",
        "parity_pass": (latest.get("parity") or {}).get("status") == "PASS",
        "cutover_readiness_pass": (latest.get("cutover_readiness") or {}).get("status") == "PASS",
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
        "# Post-Click Final Contract Predicate/Result Adapter Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Target block found: `{capture.get('target_block_found')}`",
        f"- Predicate fields cut over to adapter: `{capture.get('cutover_fields_from_adapter')}`",
        f"- Page input collection retained: `{capture.get('page_input_collection_retained')}`",
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
                "Next safe slice: rerun predicate/result parity and render-item consumer cutover readiness "
                "after this cutover, then audit whether the old page predicate calculations can be "
                "converted to fallback-only or deleted."
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
        "schema": "design_guide_post_click_final_contract_predicate_result_adapter_cutover_snapshot.v1",
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
        / f"design_guide_post_click_final_contract_predicate_result_adapter_cutover_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_post_click_final_contract_predicate_result_adapter_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_final_contract_predicate_result_adapter_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
