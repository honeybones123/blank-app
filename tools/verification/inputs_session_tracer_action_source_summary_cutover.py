from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_tracer_one_click_action_source_summary


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


def _old_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "trigger_fingerprint": None if row["trigger_fingerprint"] is None else str(row["trigger_fingerprint"]),
        "force_auto_redesign": None if row["force_auto_redesign"] is None else bool(row["force_auto_redesign"]),
        "auto_design_auto_invoke": None
        if row["auto_design_auto_invoke"] is None
        else bool(row["auto_design_auto_invoke"]),
        "auto_design_request_source": row["auto_design_request_source"],
        "auto_design_requested_at_ts": row["auto_design_requested_at_ts"],
        "auto_design_invoke_pending": None
        if row["auto_design_invoke_pending"] is None
        else bool(row["auto_design_invoke_pending"]),
    }


def _scenarios() -> list[dict[str, Any]]:
    return [
        {
            "name": "no_trigger_defaults_false",
            "trigger_fingerprint": None,
            "force_auto_redesign": False,
            "auto_design_auto_invoke": False,
            "auto_design_request_source": None,
            "auto_design_requested_at_ts": None,
            "auto_design_invoke_pending": False,
        },
        {
            "name": "tuple_trigger_active",
            "trigger_fingerprint": ("beam_1", 123, "apply"),
            "force_auto_redesign": True,
            "auto_design_auto_invoke": True,
            "auto_design_request_source": "browser_recipe",
            "auto_design_requested_at_ts": 456.0,
            "auto_design_invoke_pending": True,
        },
        {
            "name": "string_truthy",
            "trigger_fingerprint": "abc",
            "force_auto_redesign": "1",
            "auto_design_auto_invoke": "yes",
            "auto_design_request_source": "manual",
            "auto_design_requested_at_ts": "ts",
            "auto_design_invoke_pending": "pending",
        },
        {
            "name": "exception_fallback_none_shape",
            "trigger_fingerprint": ("fallback",),
            "force_auto_redesign": None,
            "auto_design_auto_invoke": None,
            "auto_design_request_source": None,
            "auto_design_requested_at_ts": None,
            "auto_design_invoke_pending": None,
        },
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Tracer Action Source Summary Cutover",
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
    helper = _function_window(source, "_tracer_one_click_action_source_summary")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    scenario_results = []
    mismatches = []
    for row in _scenarios():
        old = _old_payload(row)
        new = build_inputs_tracer_one_click_action_source_summary(
            trigger_fingerprint=row["trigger_fingerprint"],
            force_auto_redesign=row["force_auto_redesign"],
            auto_design_auto_invoke=row["auto_design_auto_invoke"],
            auto_design_request_source=row["auto_design_request_source"],
            auto_design_requested_at_ts=row["auto_design_requested_at_ts"],
            auto_design_invoke_pending=row["auto_design_invoke_pending"],
        )
        match = old == dict(new.summary_payload) and bool(new.display_hash)
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old": old,
                "new": dict(new.summary_payload),
                "display_hash": new.display_hash,
            }
        )
        if not match:
            mismatches.append({"scenario": row["name"], "old": old, "new": dict(new.summary_payload)})

    checks = {
        "page_helper_delegates_to_session_builder": "build_inputs_tracer_one_click_action_source_summary(" in helper,
        "page_helper_keeps_session_reads": helper.count("st.session_state.get") >= 5,
        "page_helper_keeps_exception_guard": "except Exception" in helper,
        "old_inline_out_payload_removed": "out: dict" not in helper and "out[" not in helper,
        "session_builder_exists": "def build_inputs_tracer_one_click_action_source_summary(" in builders,
        "session_model_exists": "class InputsTracerOneClickActionSourceSummary" in models,
        "session_init_exports_builder": "build_inputs_tracer_one_click_action_source_summary" in init_source,
        "session_init_exports_model": "InputsTracerOneClickActionSourceSummary" in init_source,
        "session_builder_reuses_auto_design_debug_builder": "build_inputs_auto_design_invoke_debug_snapshot(" in _function_window(
            builders, "build_inputs_tracer_one_click_action_source_summary"
        ),
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_TRACER_ACTION_SOURCE_SUMMARY_LOCKED"
        if not failures
        else "INPUTS_SESSION_TRACER_ACTION_SOURCE_SUMMARY_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_tracer_action_source_summary_cutover",
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
    json_path = VERIFICATION_DIR / f"inputs_session_tracer_action_source_summary_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_tracer_action_source_summary_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_tracer_action_source_summary_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
