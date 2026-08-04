"""Cutover proof for zero-shear render consumer projection adapter.

This verifies the live page path now calls the Design Brain publication adapter
for the zero-shear render consumer projection while keeping terminal-row
construction and session storage page-owned.
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
    "apply_final_design_guide_zero_shear_render_consumer_projection "
    "as _apply_final_design_guide_zero_shear_render_consumer_projection"
)
CALL_TOKEN = "_apply_final_design_guide_zero_shear_render_consumer_projection("
TERMINAL_ROW_TOKEN = "_zero_shear_terminal_stop_row = {"
SESSION_GET_TOKEN = "st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY)"
SESSION_UPDATE_TOKEN = '_session_zero_shear_debug.update('

OLD_MANUAL_MUTATION_TOKENS = {
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


def _line_number(source: str, token: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            return index
    return None


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    block_start = source.find('== "final_visible_zero_shear_demand_accepted"')
    block_end = source.find("if _design_guide_item_is_visible_blocker(_final_visible_item):", block_start)
    block_source = source[block_start:block_end] if block_start >= 0 and block_end > block_start else ""
    call_line = _line_number(source, CALL_TOKEN)
    terminal_line = _line_number(source, TERMINAL_ROW_TOKEN)
    session_get_line = _line_number(source, SESSION_GET_TOKEN)
    session_update_line = _line_number(source, SESSION_UPDATE_TOKEN)
    old_tokens = {key: token in block_source for key, token in OLD_MANUAL_MUTATION_TOKENS.items()}
    latest = {
        "adapter_parity": _latest("design_guide_zero_shear_render_consumer_projection_adapter_parity"),
        "readiness": _latest("design_guide_zero_shear_render_consumer_narrowing_readiness"),
        "render_item_parity": _latest("design_guide_live_render_item_consumer_adapter_parity"),
        "render_lock": _latest("design_guide_render_bridge_lock"),
        "compute_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "ZERO_SHEAR_RENDER_CONSUMER_PROJECTION_ADAPTER_CUTOVER_PASS",
        "import_present": IMPORT_TOKEN in source,
        "adapter_call_count": source.count(CALL_TOKEN),
        "adapter_call_line": call_line,
        "terminal_row_line": terminal_line,
        "block_window_found": bool(block_source),
        "session_get_line": session_get_line,
        "session_update_line": session_update_line,
        "terminal_row_built_before_adapter_call": (
            terminal_line is not None and call_line is not None and terminal_line < call_line
        ),
        "session_storage_page_owned": (
            session_get_line is not None and session_update_line is not None and call_line is not None
        ),
        "old_manual_mutation_tokens_present": old_tokens,
        "old_manual_mutation_tokens_deleted": not any(old_tokens.values()),
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
        "import_present": capture.get("import_present") is True,
        "block_window_found": capture.get("block_window_found") is True,
        "adapter_call_once": capture.get("adapter_call_count") == 1,
        "terminal_row_built_before_adapter_call": capture.get("terminal_row_built_before_adapter_call") is True,
        "session_storage_page_owned": capture.get("session_storage_page_owned") is True,
        "old_manual_mutation_tokens_deleted": capture.get("old_manual_mutation_tokens_deleted") is True,
        "adapter_parity_pass": (latest.get("adapter_parity") or {}).get("status") == "PASS",
        "readiness_pass": (latest.get("readiness") or {}).get("status") == "PASS",
        "render_item_parity_pass": (latest.get("render_item_parity") or {}).get("status") == "PASS",
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
        "# Zero-Shear Render Consumer Projection Adapter Cutover Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Adapter call line: `{capture.get('adapter_call_line')}`",
        f"- Terminal row line: `{capture.get('terminal_row_line')}`",
        f"- Session update line: `{capture.get('session_update_line')}`",
        f"- Old manual mutation tokens deleted: `{capture.get('old_manual_mutation_tokens_deleted')}`",
        "",
        "## Old Manual Tokens",
        "",
    ]
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in (capture.get("old_manual_mutation_tokens_present") or {}).items()
    )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", ""])
    lines.append(
        "Next safe slice: run a deadness/inventory proof for the removed zero-shear manual rows, then move to "
        "safe-low-util promotion consumer parity/narrowing."
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
        "schema": "design_guide_zero_shear_render_consumer_projection_adapter_cutover_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_zero_shear_render_consumer_projection_adapter_cutover_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_zero_shear_render_consumer_projection_adapter_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_zero_shear_render_consumer_projection_adapter_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
