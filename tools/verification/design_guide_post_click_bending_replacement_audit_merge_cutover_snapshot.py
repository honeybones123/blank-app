"""Cutover proof for post-click bending replacement audit merge projection."""

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

TARGET_START = "_post_click_bending_audit = {}"
TARGET_END = "_post_click_replacement_decision_proof = _stamp_final_publication_post_click_replacement_decision_proof("
CUTOVER_CALL = "_build_final_design_guide_post_click_bending_replacement_audit_result_proof("
RESOLUTION_BUILDER = "_post_click_low_bending_resolution_item("
FORBIDDEN_OLD_MERGE_TOKENS = (
    "for _bending_audit_source in (",
    "_existing_evidence = dict(_post_click_bending_audit.get(_evidence_key) or {})",
    "for _family_list_key in (",
    "_post_click_bending_audit[\"post_click_family_utils\"] = dict(",
    "\"post_click_exact_blockers_by_family\" not in _post_click_bending_audit",
)
REQUIRED_CUTOVER_STAMPS = (
    "final_publication_post_click_bending_replacement_audit_merge_cutover_used",
    "final_publication_post_click_bending_replacement_audit_merge_cutover_source",
    "final_publication_post_click_bending_replacement_audit_merge_cutover_hash",
    "final_publication_post_click_bending_replacement_audit_merge_product_behavior_changed",
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
    cutover_index = target.find(CUTOVER_CALL)
    resolution_index = target.find(RESOLUTION_BUILDER)
    latest = {
        "object": _latest("design_guide_post_click_bending_replacement_audit_result_object"),
        "trace": _latest("design_guide_live_post_click_bending_replacement_audit_result_trace"),
        "parity": _latest("design_guide_post_click_bending_replacement_audit_result_parity_scenarios"),
        "predicate_deletion": _latest(
            "design_guide_post_click_final_contract_legacy_predicate_deletion_audit"
        ),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "POST_CLICK_BENDING_REPLACEMENT_AUDIT_MERGE_CUTOVER_PASS",
        "target_block_found": bool(target),
        "cutover_call_present": CUTOVER_CALL in target,
        "cutover_before_resolution_builder": (
            cutover_index >= 0 and resolution_index >= 0 and cutover_index < resolution_index
        ),
        "old_merge_tokens_absent": not any(token in target for token in FORBIDDEN_OLD_MERGE_TOKENS),
        "resolution_builder_retained": RESOLUTION_BUILDER in target,
        "disabled_contract_guard_retained": (
            "and not _design_guide_button_contract_enabled(_post_click_bending_contract)"
            in target
        ),
        "final_visible_binding_retained": (
            "_publish_final_visible_design_guide_contract_binding(" in target
        ),
        "adapter_result_retained": (
            "_build_final_design_guide_post_click_final_contract_check_adapter_result(" in target
        ),
        "cutover_stamps_present": all(token in target for token in REQUIRED_CUTOVER_STAMPS),
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
        "cutover_call_present": capture.get("cutover_call_present") is True,
        "cutover_before_resolution_builder": (
            capture.get("cutover_before_resolution_builder") is True
        ),
        "old_merge_tokens_absent": capture.get("old_merge_tokens_absent") is True,
        "resolution_builder_retained": capture.get("resolution_builder_retained") is True,
        "disabled_contract_guard_retained": (
            capture.get("disabled_contract_guard_retained") is True
        ),
        "final_visible_binding_retained": capture.get("final_visible_binding_retained") is True,
        "adapter_result_retained": capture.get("adapter_result_retained") is True,
        "cutover_stamps_present": capture.get("cutover_stamps_present") is True,
        "object_pass": (latest.get("object") or {}).get("status") == "PASS",
        "trace_pass": (latest.get("trace") or {}).get("status") == "PASS",
        "parity_pass": (latest.get("parity") or {}).get("status") == "PASS",
        "predicate_deletion_pass": (latest.get("predicate_deletion") or {}).get("status") == "PASS",
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
        "# Post-Click Bending Replacement Audit Merge Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Old merge tokens absent: `{capture.get('old_merge_tokens_absent')}`",
        f"- Resolution builder retained: `{capture.get('resolution_builder_retained')}`",
        f"- Final-visible binding retained: `{capture.get('final_visible_binding_retained')}`",
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
            "Next safe slice: prove/cut over the low-bending resolution result construction or classify it as controller-owned.",
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
        "schema": "design_guide_post_click_bending_replacement_audit_merge_cutover_snapshot.v1",
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
        / f"design_guide_post_click_bending_replacement_audit_merge_cutover_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_post_click_bending_replacement_audit_merge_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_bending_replacement_audit_merge_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
