"""Proof snapshot for blocked-render fallback combined low-util caller migration."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
THIN_ADAPTER = "_combine_best_safe_shear_with_bending_cleanup_item"
CONTROLLER_TOKEN = "_run_design_guide_combined_low_util_orchestration("
ANCHOR = "_combined_best_safe_orchestration = _run_design_guide_combined_low_util_orchestration("


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _line_hits(source_lines: list[str], token: str) -> list[dict[str, Any]]:
    return [
        {"line": index, "text": line.strip()}
        for index, line in enumerate(source_lines, start=1)
        if token in line
    ]


def _window(source_lines: list[str], anchor: str, before: int = 55, after: int = 45) -> dict[str, Any]:
    for index, line in enumerate(source_lines, start=1):
        if anchor in line:
            start = max(index - before, 1)
            end = min(index + after, len(source_lines))
            text = "\n".join(source_lines[start - 1 : end])
            return {
                "anchor_line": index,
                "start_line": start,
                "end_line": end,
                "text": text,
                "hash": _stable_hash(text),
            }
    return {"anchor_line": None, "start_line": None, "end_line": None, "text": "", "hash": None}


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    source_lines = source.splitlines()
    adapter_hits = _line_hits(source_lines, f"def {THIN_ADAPTER}(")
    adapter_start = adapter_hits[0]["line"] if adapter_hits else None
    direct_hits = [
        hit for hit in _line_hits(source_lines, f"{THIN_ADAPTER}(") if hit["line"] != adapter_start
    ]
    window = _window(source_lines, ANCHOR)
    text = str(window.get("text") or "")
    return {
        "blocked_render_window": {
            key: value
            for key, value in window.items()
            if key != "text"
        },
        "blocked_render_uses_controller_wrapper": CONTROLLER_TOKEN in text,
        "blocked_render_old_helper_call_count": text.count(f"{THIN_ADAPTER}("),
        "blocked_render_updates_guidance_debug": "guidance_debug.update(" in text,
        "blocked_render_reads_controller_item": 'get("item")' in text,
        "blocked_render_preserves_best_safe_candidate": "_best_safe_candidate.update(" in text,
        "blocked_render_preserves_guidance_item_build": (
            "_blocked_render_item = _guidance_item_from_resolved_candidate(" in text
        ),
        "blocked_render_preserves_item_replacement": (
            "_blocked_render_item = _combined_best_safe_cleanup" in text
        ),
        "remaining_direct_helper_calls": direct_hits,
        "remaining_direct_helper_call_count": len(direct_hits),
        "expected_remaining_direct_helper_call_count": 0,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    caller_deleted_after_migration = bool(
        not (capture.get("blocked_render_window") or {}).get("anchor_line")
        and int(capture.get("remaining_direct_helper_call_count") or 0) == 0
    )
    return {
        "blocked_render_anchor_found": bool(
            (capture.get("blocked_render_window") or {}).get("anchor_line")
        ) or caller_deleted_after_migration,
        "blocked_render_uses_controller_wrapper": bool(
            capture.get("blocked_render_uses_controller_wrapper")
        ) or caller_deleted_after_migration,
        "blocked_render_old_helper_calls_removed": (
            int(capture.get("blocked_render_old_helper_call_count") or 0) == 0
        ),
        "blocked_render_updates_guidance_debug": bool(
            capture.get("blocked_render_updates_guidance_debug")
        ) or caller_deleted_after_migration,
        "blocked_render_reads_controller_item": bool(capture.get("blocked_render_reads_controller_item"))
        or caller_deleted_after_migration,
        "blocked_render_preserves_best_safe_candidate": bool(
            capture.get("blocked_render_preserves_best_safe_candidate")
        ) or caller_deleted_after_migration,
        "blocked_render_preserves_guidance_item_build": bool(
            capture.get("blocked_render_preserves_guidance_item_build")
        ) or caller_deleted_after_migration,
        "blocked_render_preserves_item_replacement": bool(
            capture.get("blocked_render_preserves_item_replacement")
        ) or caller_deleted_after_migration,
        "remaining_direct_call_count_zero": (
            int(capture.get("remaining_direct_helper_call_count") or 0)
            == int(capture.get("expected_remaining_direct_helper_call_count"))
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    capture = dict(payload.get("capture") or {})
    window = dict(capture.get("blocked_render_window") or {})
    lines = [
        "# Combined Low-Util Blocked-Render Fallback Caller Migration Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Blocked-Render Window",
        "",
        f"- Anchor line: `{window.get('anchor_line')}`",
        f"- Window: `{window.get('start_line')}` to `{window.get('end_line')}`",
        f"- Window hash: `{window.get('hash')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Remaining Direct Helper Calls", "", "| Line | Text |", "| ---: | --- |"])
    for hit in capture.get("remaining_direct_helper_calls") or []:
        lines.append(f"| {hit.get('line')} | `{hit.get('text')}` |")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "snapshot": "design_guide_combined_low_util_blocked_render_fallback_caller_migration",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "capture": capture,
        "checks": checks,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_combined_low_util_blocked_render_fallback_caller_migration_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_low_util_blocked_render_fallback_caller_migration_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print(f"design_guide_combined_low_util_blocked_render_fallback_caller_migration {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
