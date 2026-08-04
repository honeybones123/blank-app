"""Audit callsite overview sources for shear low-util cleanup target."""

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
FUNCTION_NAME = "_shear_low_util_target_cleanup_item"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _line_offsets(source: str) -> list[int]:
    offsets = [0]
    total = 0
    for line in source.splitlines(keepends=True):
        total += len(line)
        offsets.append(total)
    return offsets


def _line_for_offset(offsets: list[int], offset: int) -> int:
    lo = 0
    hi = len(offsets) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if offsets[mid] <= offset:
            lo = mid + 1
        else:
            hi = mid - 1
    return max(1, hi + 1)


def _extract_call_text(source: str, start: int) -> tuple[str, int]:
    depth = 0
    in_string: str | None = None
    escape = False
    for idx in range(start, len(source)):
        ch = source[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_string:
                in_string = None
            continue
        if ch in {"'", '"'}:
            in_string = ch
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return source[start : idx + 1], idx + 1
    return source[start:], len(source)


def _classify_call(call_text: str, context_before: str) -> dict[str, Any]:
    lines = [line.strip() for line in call_text.splitlines()]
    second_argument = ""
    if len(lines) >= 3:
        second_argument = lines[2].rstrip(",")
    context = context_before[-2500:]
    source_class = "unknown_or_unverified"
    evidence: list[str] = []
    if "_collect_design_overview(" in context and second_argument in context:
        source_class = "recent_recomputed_current_overview"
        evidence.append("context contains _collect_design_overview before call and passes that variable")
    if "dict(guidance_debug.get(\"overview\")" in second_argument or "guidance_debug.get(\"overview\")" in second_argument:
        source_class = "guidance_debug_or_fallback_overview"
        evidence.append("argument is sourced from guidance_debug overview fallback")
    if "_dg_overview" in second_argument:
        source_class = "render_cached_overview"
        evidence.append("argument uses _dg_overview")
    if second_argument in {"overview", "current_overview", "fold_overview", "_current_overview_for_low_shear"}:
        if source_class == "unknown_or_unverified":
            source_class = "named_overview_variable_needs_context_proof"
        evidence.append(f"passes named overview variable {second_argument!r}")
    if second_argument in {"{}", "None"}:
        source_class = "missing_or_empty_overview"
        evidence.append("call passes empty/missing overview")
    return {
        "second_argument": second_argument,
        "source_class": source_class,
        "evidence": evidence,
        "verified_current_status_authority": source_class == "recent_recomputed_current_overview",
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    offsets = _line_offsets(source)
    callsites: list[dict[str, Any]] = []
    search = f"{FUNCTION_NAME}("
    start = 0
    while True:
        idx = source.find(search, start)
        if idx < 0:
            break
        line = _line_for_offset(offsets, idx)
        line_start = source.rfind("\n", 0, idx) + 1
        if source[line_start:idx].strip().startswith("def"):
            start = idx + len(search)
            continue
        call_text, end_idx = _extract_call_text(source, idx)
        context_before = source[max(0, idx - 2500) : idx]
        classification = _classify_call(call_text, context_before)
        callsites.append(
            {
                "line": line,
                "call_text_hash": _stable_hash(call_text),
                "context_hash": _stable_hash(context_before),
                **classification,
            }
        )
        start = end_idx
    class_counts: dict[str, int] = {}
    for call in callsites:
        class_counts[str(call.get("source_class"))] = class_counts.get(str(call.get("source_class")), 0) + 1
    unverified = [call for call in callsites if not bool(call.get("verified_current_status_authority"))]
    return {
        "decision": "SHEAR_LOW_UTIL_OVERVIEW_CALLSITES_NOT_READY_FOR_GLOBAL_RECOMPUTE_DELETION",
        "callsite_count": len(callsites),
        "class_counts": class_counts,
        "callsites": callsites,
        "unverified_callsite_count": len(unverified),
        "safe_to_delete_internal_recompute_globally": False,
        "required_next_step": (
            "Introduce a verified current-overview/status-authority boundary or prove each callsite passes "
            "a recomputed current overview before replacing the internal recompute."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "callsites_found": int(capture.get("callsite_count") or 0) > 0,
        "classifications_recorded": bool(capture.get("class_counts")),
        "unverified_callsites_recorded": int(capture.get("unverified_callsite_count") or 0) > 0,
        "not_safe_to_delete_global_recompute": capture.get("safe_to_delete_internal_recompute_globally") is False,
        "required_next_step_recorded": bool(capture.get("required_next_step")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Current Overview Callsite Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Class Counts", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (capture.get("class_counts") or {}).items())
    lines.extend(
        [
            "",
            "## Callsites",
            "",
            "| Line | Source class | Verified current status authority | Overview argument |",
            "| ---: | --- | --- | --- |",
        ]
    )
    for call in capture.get("callsites") or []:
        lines.append(
            f"| {call.get('line')} | {call.get('source_class')} | {call.get('verified_current_status_authority')} | `{call.get('second_argument')}` |"
        )
    lines.extend(["", "## Required Next Step", "", str(capture.get("required_next_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_current_overview_callsite_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_current_overview_callsite_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_current_overview_callsite_audit {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
