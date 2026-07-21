from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_runtime_trace_session_diff


INPUTS_PAGE = ROOT / "inputs_page.py"
SESSION_BUILDERS = ROOT / "inputs_page_modules" / "session" / "builders.py"
SESSION_MODELS = ROOT / "inputs_page_modules" / "session" / "models.py"
SESSION_INIT = ROOT / "inputs_page_modules" / "session" / "__init__.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_window(source: str, name: str) -> str:
    marker = f"def {name}("
    if marker not in source:
        return ""
    window = source.split(marker, 1)[1].split("\ndef ", 1)[0]
    return window.split("\n", 1)[1] if "\n" in window else window


def _old_hash(value: object) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _old_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_keys = set(before)
    after_keys = set(after)
    changed = []
    for key in sorted(before_keys & after_keys):
        if _old_hash(before[key]) != _old_hash(after[key]):
            changed.append({"key": key, "before": before[key], "after": after[key]})
    return {
        "added": {key: after[key] for key in sorted(after_keys - before_keys)},
        "removed": {key: before[key] for key in sorted(before_keys - after_keys)},
        "changed": changed,
    }


def _scenarios() -> list[dict[str, Any]]:
    return [
        {"name": "no_change", "before": {"a": 1}, "after": {"a": 1}},
        {"name": "added_removed_changed", "before": {"a": 1, "b": 2}, "after": {"b": 3, "c": 4}},
        {
            "name": "nested_hash_change",
            "before": {"item": {"x": 1, "y": [1, 2]}},
            "after": {"item": {"x": 1, "y": [1, 3]}},
        },
        {"name": "stable_different_key_order", "before": {"a": {"x": 1, "y": 2}}, "after": {"a": {"y": 2, "x": 1}}},
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Runtime Trace Session Diff Cutover",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        f"- scenarios checked: `{len(payload['scenarios'])}`",
        f"- mismatches: `{len(payload['mismatches'])}`",
        f"- product behavior changed: `{payload['product_behavior_changed']}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = _read(INPUTS_PAGE)
    helper = _function_window(source, "_dg_runtime_trace_session_diff")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    scenario_results = []
    mismatches = []
    for row in _scenarios():
        old = _old_diff(row["before"], row["after"])
        new = build_inputs_design_guide_runtime_trace_session_diff(before=row["before"], after=row["after"])
        match = old == dict(new.diff) and bool(new.display_hash)
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old": old,
                "new": dict(new.diff),
                "display_hash": new.display_hash,
            }
        )
        if not match:
            mismatches.append({"scenario": row["name"], "old": old, "new": dict(new.diff)})

    checks = {
        "page_helper_delegates_to_session_builder": "build_inputs_design_guide_runtime_trace_session_diff(" in helper,
        "old_diff_loop_removed_from_page_helper": "for key in sorted" not in helper and "_dg_runtime_trace_hash(" not in helper,
        "session_builder_exists": "def build_inputs_design_guide_runtime_trace_session_diff(" in builders,
        "session_model_exists": "class InputsDesignGuideRuntimeTraceSessionDiff" in models,
        "session_init_exports_builder": "build_inputs_design_guide_runtime_trace_session_diff" in init_source,
        "session_init_exports_model": "InputsDesignGuideRuntimeTraceSessionDiff" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_RUNTIME_TRACE_SESSION_DIFF_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_RUNTIME_TRACE_SESSION_DIFF_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_runtime_trace_session_diff_cutover",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "scenarios": scenario_results,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "streamlit_reads_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_runtime_trace_session_diff_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_runtime_trace_session_diff_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_guide_runtime_trace_session_diff_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
