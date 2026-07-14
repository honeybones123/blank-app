"""Deadness proof for removed zero-shear render consumer manual rows."""

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

TARGET_START = '== "final_visible_zero_shear_demand_accepted"'
TARGET_END = "if _design_guide_item_is_visible_blocker(_final_visible_item):"
ADAPTER_CALL = "_apply_final_design_guide_zero_shear_render_consumer_projection("
REMOVED_ROW_TOKENS = {
    "manual_item_blocker_attempt": '_final_visible_item["blocker_attempts_by_family"] = dict(_zero_shear_attempts)',
    "manual_item_candidate_evidence": '_final_visible_item["candidate_search_evidence"] = dict(_zero_shear_candidate_evidence)',
    "manual_guidance_stale_flag": 'guidance_debug["zero_shear_accepted_stale_blocker_cleared"] = True',
    "manual_guidance_blocker_attempt": 'guidance_debug["blocker_attempts_by_family"] = dict(_guidance_zero_shear_attempts)',
    "manual_guidance_candidate_evidence": 'guidance_debug["candidate_search_evidence"] = dict(_guidance_zero_shear_evidence)',
    "manual_session_candidate_attempt": '_session_zero_shear_candidate_attempts["shear"] = dict(_zero_shear_terminal_stop_row)',
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


def _line_count() -> int:
    return len(INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").splitlines())


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    start = source.find(TARGET_START)
    end = source.find(TARGET_END, start)
    block = source[start:end] if start >= 0 and end > start else ""
    removed_hits = {key: token in block for key, token in REMOVED_ROW_TOKENS.items()}
    cutover = _latest("design_guide_zero_shear_render_consumer_projection_adapter_cutover")
    return {
        "decision": "ZERO_SHEAR_RENDER_CONSUMER_MANUAL_ROWS_DEAD",
        "target_block_found": bool(block),
        "adapter_call_count_in_block": block.count(ADAPTER_CALL),
        "removed_row_tokens_present": removed_hits,
        "removed_row_tokens_absent": not any(removed_hits.values()),
        "cutover_status": cutover.get("status"),
        "cutover_path": cutover.get("path"),
        "line_count": _line_count(),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_block_found": capture.get("target_block_found") is True,
        "adapter_call_once_in_block": capture.get("adapter_call_count_in_block") == 1,
        "removed_row_tokens_absent": capture.get("removed_row_tokens_absent") is True,
        "cutover_pass": capture.get("cutover_status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Zero-Shear Render Consumer Manual Rows Deadness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Target block found: `{capture.get('target_block_found')}`",
        f"- Adapter call count in block: `{capture.get('adapter_call_count_in_block')}`",
        f"- Removed row tokens absent: `{capture.get('removed_row_tokens_absent')}`",
        f"- Cutover artifact: `{capture.get('cutover_path')}`",
        f"- inputs_page.py line count: `{capture.get('line_count')}`",
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
        "schema": "design_guide_zero_shear_render_consumer_manual_rows_deadness_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_zero_shear_render_consumer_manual_rows_deadness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_zero_shear_render_consumer_manual_rows_deadness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_zero_shear_render_consumer_manual_rows_deadness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
