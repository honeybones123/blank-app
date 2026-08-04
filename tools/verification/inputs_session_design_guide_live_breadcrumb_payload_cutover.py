from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_live_breadcrumb_payload


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


def _old_payload(label: Any, extra: dict[str, Any] | None, timestamp_iso: Any) -> dict[str, Any]:
    return {"label": str(label), "extra": dict(extra or {}), "ts": timestamp_iso}


def _scenarios() -> list[dict[str, Any]]:
    return [
        {"name": "plain_label", "label": "DG TRACE ENTRY", "extra": None, "timestamp_iso": "2026-07-15T20:00:00"},
        {
            "name": "extra_payload",
            "label": "DG CALLING CANONICAL ONE CLICK",
            "extra": {"function": "handle_apply_buttons", "count": 2},
            "timestamp_iso": "2026-07-15T20:01:00",
        },
        {"name": "non_string_label", "label": 123, "extra": {}, "timestamp_iso": "2026-07-15T20:02:00"},
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Live Breadcrumb Payload Cutover",
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
    helper = _function_window(source, "_set_design_guide_live_breadcrumb")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    scenario_results = []
    mismatches = []
    for row in _scenarios():
        old = _old_payload(row["label"], row["extra"], row["timestamp_iso"])
        new = build_inputs_design_guide_live_breadcrumb_payload(
            label=row["label"],
            extra=row["extra"],
            timestamp_iso=row["timestamp_iso"],
        )
        match = old == dict(new.payload) and bool(new.display_hash)
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old": old,
                "new": dict(new.payload),
                "display_hash": new.display_hash,
            }
        )
        if not match:
            mismatches.append({"scenario": row["name"], "old": old, "new": dict(new.payload)})

    checks = {
        "page_helper_delegates_to_session_builder": "build_inputs_design_guide_live_breadcrumb_payload(" in helper,
        "page_helper_keeps_session_write": 'st.session_state["_dg_live_breadcrumb"]' in helper,
        "page_helper_keeps_timestamp_source": "datetime.now().isoformat" in helper,
        "old_inline_payload_removed_from_page_helper": '"label": str(label)' not in helper and '"extra": dict(extra or {})' not in helper,
        "session_builder_exists": "def build_inputs_design_guide_live_breadcrumb_payload(" in builders,
        "session_model_exists": "class InputsDesignGuideLiveBreadcrumbPayload" in models,
        "session_init_exports_builder": "build_inputs_design_guide_live_breadcrumb_payload" in init_source,
        "session_init_exports_model": "InputsDesignGuideLiveBreadcrumbPayload" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_LIVE_BREADCRUMB_PAYLOAD_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_LIVE_BREADCRUMB_PAYLOAD_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_live_breadcrumb_payload_cutover",
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
        "session_write_remains_page_owned": True,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_live_breadcrumb_payload_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_live_breadcrumb_payload_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_guide_live_breadcrumb_payload_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
