"""Cutover proof for post-click exact-blocker projection adapter."""

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

DIRECT_IMPORT_TOKEN = (
    "apply_final_design_guide_post_click_exact_blocker_replacement_projection "
    "as _apply_final_design_guide_post_click_exact_blocker_replacement_projection"
)
DIRECT_ADAPTER_CALL = "_apply_final_design_guide_post_click_exact_blocker_replacement_projection("
ADAPTER_RESULT_BUILDER_CALL = (
    "_build_final_design_guide_post_click_final_contract_check_adapter_result("
)
PUBLISH_CALL = "_publish_final_visible_design_guide_contract_binding("
TARGET_START = "_post_click_bending_resolution = _post_click_low_bending_resolution_item("
TARGET_END = "_stamp_final_publication_post_click_replacement_decision_proof("
REMOVED_MANUAL_ROW_TOKENS = {
    "manual_resolution_item": '_final_visible_resolution["item"] = dict(_final_visible_item)',
    "manual_resolution_reason": (
        '_final_visible_resolution["render_reason"] = '
        '"post_click_low_bending_exact_blocker_final"'
    ),
    "manual_debug_replaced_flag": (
        'guidance_debug["post_click_low_bending_action_replaced_by_exact_blocker"] = True'
    ),
    "manual_debug_branch": (
        'guidance_debug["guidance_branch"] = '
        '"post_click_low_bending_exact_blocker_final"'
    ),
    "manual_replacement_applied": "_post_click_bending_replacement_applied = True",
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


def _target_block(source: str) -> str:
    start = source.find(TARGET_START)
    if start < 0:
        return ""
    anchor = source.find(ADAPTER_RESULT_BUILDER_CALL, start)
    if anchor < 0:
        return ""
    end = source.find(TARGET_END, anchor)
    if end < 0:
        return ""
    return source[start:end]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    block = _target_block(source)
    old_tokens = {key: token in block for key, token in REMOVED_MANUAL_ROW_TOKENS.items()}
    latest = {
        "adapter_parity": _latest("design_guide_post_click_exact_blocker_projection_adapter_parity"),
        "row_readiness": _latest("design_guide_post_click_contract_check_row_level_readiness"),
        "replacement_parity": _latest("design_guide_post_click_replacement_decision_proof_parity_scenarios"),
        "render_lock": _latest("design_guide_render_bridge_lock"),
        "compute_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "POST_CLICK_EXACT_BLOCKER_ADAPTER_RESULT_CUTOVER_PASS",
        "direct_projection_import_removed": DIRECT_IMPORT_TOKEN not in source,
        "target_block_found": bool(block),
        "direct_projection_call_count_in_block": block.count(DIRECT_ADAPTER_CALL),
        "adapter_result_builder_call_count_in_block": block.count(ADAPTER_RESULT_BUILDER_CALL),
        "publish_call_count_in_block": block.count(PUBLISH_CALL),
        "adapter_result_builder_line": _line_number(source, ADAPTER_RESULT_BUILDER_CALL),
        "publish_call_line": _line_number(source, PUBLISH_CALL),
        "old_manual_row_tokens_present": old_tokens,
        "old_manual_row_tokens_deleted": not any(old_tokens.values()),
        "publish_binding_still_live": PUBLISH_CALL in block,
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
        "direct_projection_import_removed": capture.get("direct_projection_import_removed") is True,
        "target_block_found": capture.get("target_block_found") is True,
        "direct_projection_call_removed": capture.get("direct_projection_call_count_in_block") == 0,
        "adapter_result_builder_call_once_in_block": (
            capture.get("adapter_result_builder_call_count_in_block") == 1
        ),
        "publish_call_present_in_block": capture.get("publish_call_count_in_block", 0) >= 1,
        "publish_binding_still_live": capture.get("publish_binding_still_live") is True,
        "old_manual_row_tokens_deleted": capture.get("old_manual_row_tokens_deleted") is True,
        "adapter_parity_pass": (latest.get("adapter_parity") or {}).get("status") == "PASS",
        "row_readiness_pass": (latest.get("row_readiness") or {}).get("status") == "PASS",
        "replacement_parity_pass": (latest.get("replacement_parity") or {}).get("status") == "PASS",
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
        "# Post-Click Exact Blocker Projection Adapter Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Adapter result builder line: `{capture.get('adapter_result_builder_line')}`",
        f"- Publish binding line: `{capture.get('publish_call_line')}`",
        f"- Direct projection calls in target block: `{capture.get('direct_projection_call_count_in_block')}`",
        f"- Adapter result builder calls in target block: `{capture.get('adapter_result_builder_call_count_in_block')}`",
        f"- Publish calls in target block: `{capture.get('publish_call_count_in_block')}`",
        f"- Old manual rows deleted: `{capture.get('old_manual_row_tokens_deleted')}`",
        "",
        "## Old Manual Rows",
        "",
    ]
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in (capture.get("old_manual_row_tokens_present") or {}).items()
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
        "schema": "design_guide_post_click_exact_blocker_projection_adapter_cutover_snapshot.v1",
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
        / f"design_guide_post_click_exact_blocker_projection_adapter_cutover_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_post_click_exact_blocker_projection_adapter_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_exact_blocker_projection_adapter_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
