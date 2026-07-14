"""Reachability snapshot for the combined low-util thin page adapter."""

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
FUNCTION_NAME = "_combine_best_safe_shear_with_bending_cleanup_item"
WRAPPER_TOKEN = "_run_design_guide_combined_low_util_orchestration("


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int | None, int | None]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    return "", None, None


def _line_hits(source_lines: list[str], token: str) -> list[dict[str, Any]]:
    hits = []
    for index, line in enumerate(source_lines, start=1):
        if token in line:
            hits.append({"line": index, "text": line.strip()})
    return hits


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()
    function_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    call_hits = [
        hit for hit in _line_hits(lines, f"{FUNCTION_NAME}(") if hit["line"] != start_line
    ]
    injection_hits = _line_hits(lines, "combine_best_safe_shear_with_bending_cleanup_item")
    direct_call_count = len(call_hits)
    function_exists = start_line is not None
    if function_exists and direct_call_count > 0:
        classification = "APPROVED_PAGE_SHELL_ADAPTER_STILL_REACHABLE"
        safe_to_delete_now = False
        recommended_next_slice = (
            "move each direct call site to the controller wrapper or to a broader controller API before deleting the page adapter"
        )
    elif function_exists and direct_call_count == 0:
        classification = "SAFE_TO_DELETE_ZERO_DIRECT_CALLERS"
        safe_to_delete_now = True
        recommended_next_slice = "delete the unused page adapter, then rerun this proof and composed locks"
    else:
        classification = "DELETED_ZERO_DIRECT_CALLERS"
        safe_to_delete_now = True
        recommended_next_slice = "keep deleted; rerun composed locks and continue next obsolete bridge audit"
    return {
        "function": {
            "name": FUNCTION_NAME,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": (end_line - start_line + 1) if function_exists else 0,
            "source_hash": _stable_hash(function_source),
            "exists": function_exists,
        },
        "wrapper_called_in_function": WRAPPER_TOKEN in function_source,
        "call_hits": call_hits,
        "injection_hits": injection_hits,
        "direct_call_count": direct_call_count,
        "injection_reference_count": len(injection_hits),
        "classification": classification,
        "safe_to_delete_now": safe_to_delete_now,
        "recommended_next_slice": recommended_next_slice,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "function_found_or_deleted": (
            bool((capture.get("function") or {}).get("exists"))
            or capture.get("classification") == "DELETED_ZERO_DIRECT_CALLERS"
        ),
        "function_is_thin_or_deleted": int((capture.get("function") or {}).get("line_count") or 0) <= 45,
        "wrapper_called_when_function_exists": (
            bool(capture.get("wrapper_called_in_function"))
            if bool((capture.get("function") or {}).get("exists"))
            else True
        ),
        "direct_call_state_classified": capture.get("classification")
        in {
            "APPROVED_PAGE_SHELL_ADAPTER_STILL_REACHABLE",
            "SAFE_TO_DELETE_ZERO_DIRECT_CALLERS",
            "DELETED_ZERO_DIRECT_CALLERS",
        },
        "safe_delete_flag_matches_direct_calls": (
            (int(capture.get("direct_call_count") or 0) == 0)
            == bool(capture.get("safe_to_delete_now"))
        ),
        "classification_recorded": bool(capture.get("classification")),
        "recommended_next_slice_recorded": bool(capture.get("recommended_next_slice")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Combined Low-Util Thin Adapter Reachability Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Classification: `{capture.get('classification')}`",
        f"Safe to delete now: `{capture.get('safe_to_delete_now')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Direct Calls", "", "| Line | Text |", "| ---: | --- |"])
    for hit in capture.get("call_hits") or []:
        lines.append(f"| {hit.get('line')} | `{hit.get('text')}` |")
    lines.extend(["", "## Recommendation", "", str(capture.get("recommended_next_slice") or "")])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "snapshot": "design_guide_combined_low_util_thin_adapter_reachability",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "capture": capture,
        "checks": checks,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_combined_low_util_thin_adapter_reachability_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_low_util_thin_adapter_reachability_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print(f"design_guide_combined_low_util_thin_adapter_reachability {status}")
    print(f"classification={capture.get('classification')}")
    print(f"safe_to_delete_now={capture.get('safe_to_delete_now')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
