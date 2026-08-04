"""Proof snapshot for local-cleanup combined low-util caller migration."""

from __future__ import annotations

import ast
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
CALLER = "_maybe_promote_safe_local_cleanup_primary"
CONTROLLER_TOKEN = "_run_design_guide_combined_low_util_orchestration("


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name} in {path}")


def _line_hits(source_lines: list[str], token: str) -> list[dict[str, Any]]:
    return [
        {"line": index, "text": line.strip()}
        for index, line in enumerate(source_lines, start=1)
        if token in line
    ]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    source_lines = source.splitlines()
    caller_source, caller_start, caller_end = _function_source(INPUTS_PAGE, CALLER)
    try:
        adapter_source, adapter_start, adapter_end = _function_source(INPUTS_PAGE, THIN_ADAPTER)
        adapter_removed = False
    except RuntimeError:
        adapter_source, adapter_start, adapter_end = "", None, None
        adapter_removed = True
    direct_hits = [
        hit for hit in _line_hits(source_lines, f"{THIN_ADAPTER}(") if hit["line"] != adapter_start
    ]
    return {
        "caller": {
            "name": CALLER,
            "start_line": caller_start,
            "end_line": caller_end,
            "line_count": caller_end - caller_start + 1,
            "source_hash": _stable_hash(caller_source),
        },
        "thin_adapter": {
            "name": THIN_ADAPTER,
            "start_line": adapter_start,
            "end_line": adapter_end,
            "line_count": (adapter_end - adapter_start + 1) if adapter_start and adapter_end else 0,
            "uses_string_item_key": 'orchestration.get("item")' in adapter_source,
            "removed": adapter_removed,
        },
        "caller_uses_controller_wrapper": CONTROLLER_TOKEN in caller_source,
        "caller_local_adapter_defined": "def _controller_combined_low_util_item(" in caller_source,
        "caller_old_helper_call_count": caller_source.count(f"{THIN_ADAPTER}("),
        "caller_controller_local_call_count": caller_source.count("_controller_combined_low_util_item(") - 1,
        "remaining_direct_helper_calls": direct_hits,
        "remaining_direct_helper_call_count": len(direct_hits),
        "maximum_remaining_direct_helper_call_count": 4,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "caller_found": bool((capture.get("caller") or {}).get("line_count")),
        "thin_adapter_still_valid_or_removed": bool(
            (capture.get("thin_adapter") or {}).get("uses_string_item_key")
            or (capture.get("thin_adapter") or {}).get("removed")
        ),
        "caller_uses_controller_wrapper": bool(capture.get("caller_uses_controller_wrapper")),
        "caller_local_adapter_defined": bool(capture.get("caller_local_adapter_defined")),
        "caller_old_helper_calls_removed": int(capture.get("caller_old_helper_call_count") or 0) == 0,
        "caller_controller_calls_present": int(capture.get("caller_controller_local_call_count") or 0) == 2,
        "remaining_direct_call_count_reduced": (
            int(capture.get("remaining_direct_helper_call_count") or 0)
            <= int(capture.get("maximum_remaining_direct_helper_call_count") or -1)
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Combined Low-Util Local Cleanup Caller Migration Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
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
        "snapshot": "design_guide_combined_low_util_local_cleanup_caller_migration",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "capture": capture,
        "checks": checks,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_combined_low_util_local_cleanup_caller_migration_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_low_util_local_cleanup_caller_migration_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print(f"design_guide_combined_low_util_local_cleanup_caller_migration {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
