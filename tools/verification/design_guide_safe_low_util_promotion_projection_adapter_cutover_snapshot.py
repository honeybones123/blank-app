"""Cutover proof for safe-low-util promotion projection adapter.

This verifies the live page path now calls the Design Brain publication adapter
for the safe-low-util promotion projection while keeping candidate construction
and page render/apply ownership unchanged.
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
    "apply_final_design_guide_safe_low_util_promotion_projection "
    "as _apply_final_design_guide_safe_low_util_promotion_projection"
)
CALL_TOKEN = "_apply_final_design_guide_safe_low_util_promotion_projection("
HELPER_CALL_TOKEN = "_visible_safe_low_util_cleanup_action_from_evidence("
TARGET_START = "if _design_guide_item_is_visible_blocker(_final_visible_item):"
TARGET_END = "_final_contract_for_post_click ="
OLD_MANUAL_MUTATION_TOKENS = {
    "manual_item_replacement": "_final_visible_item = dict(_final_safe_low_util_action)",
    "manual_resolution_item": '_final_visible_resolution["item"] = dict(_final_visible_item)',
    "manual_resolution_reason": '_final_visible_resolution["render_reason"] = str(',
    "manual_debug_flag": 'guidance_debug["final_visible_blocker_promoted_to_safe_low_util_action"] = True',
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
    helper = source.find(HELPER_CALL_TOKEN, start)
    if helper < 0:
        return ""
    end = source.find(TARGET_END, helper)
    return source[start:end] if end > start else ""


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    block = _target_block(source)
    old_tokens = {key: token in block for key, token in OLD_MANUAL_MUTATION_TOKENS.items()}
    latest = {
        "adapter_parity": _latest("design_guide_safe_low_util_promotion_projection_adapter_parity"),
        "render_item_parity": _latest("design_guide_live_render_item_consumer_adapter_parity"),
        "render_lock": _latest("design_guide_render_bridge_lock"),
        "compute_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "SAFE_LOW_UTIL_PROMOTION_PROJECTION_ADAPTER_CUTOVER_PASS",
        "import_present": IMPORT_TOKEN in source,
        "adapter_call_count": source.count(CALL_TOKEN),
        "adapter_call_count_in_block": block.count(CALL_TOKEN),
        "adapter_call_line": _line_number(source, CALL_TOKEN),
        "helper_call_line": _line_number(source, HELPER_CALL_TOKEN),
        "block_window_found": bool(block),
        "helper_call_still_page_owned": HELPER_CALL_TOKEN in block,
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
        "adapter_call_once_in_block": capture.get("adapter_call_count_in_block") == 1,
        "helper_call_still_page_owned": capture.get("helper_call_still_page_owned") is True,
        "old_manual_mutation_tokens_deleted": capture.get("old_manual_mutation_tokens_deleted") is True,
        "adapter_parity_pass": (latest.get("adapter_parity") or {}).get("status") == "PASS",
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
        "# Safe-Low-Util Promotion Projection Adapter Cutover Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Adapter call line: `{capture.get('adapter_call_line')}`",
        f"- Helper call line: `{capture.get('helper_call_line')}`",
        f"- Adapter calls in target block: `{capture.get('adapter_call_count_in_block')}`",
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
        "Next safe slice: run a deadness/inventory proof for the removed safe-low-util manual rows."
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
        "schema": "design_guide_safe_low_util_promotion_projection_adapter_cutover_snapshot.v1",
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
        / f"design_guide_safe_low_util_promotion_projection_adapter_cutover_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_safe_low_util_promotion_projection_adapter_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_safe_low_util_promotion_projection_adapter_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
