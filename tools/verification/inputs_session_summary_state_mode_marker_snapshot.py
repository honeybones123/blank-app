from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
SESSION_ROOT = ROOT / "inputs_page_modules" / "session"
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


def _legacy_marker(
    *,
    base: dict[str, Any],
    widget_shear: dict[str, Any],
    shared_only_mode: bool,
    shared_only_reason: str,
    overlay_count: int,
) -> dict[str, Any]:
    return {
        "shared_only_mode": bool(shared_only_mode),
        "reason": shared_only_reason,
        "overlay_count": overlay_count,
        "shared_shear": {
            "s_lig": base.get("s_lig"),
            "lig_d": base.get("lig_d"),
            "lig_legs": base.get("lig_legs"),
        },
        "widget_shear": {
            "inputs_s_lig": widget_shear.get("inputs_s_lig"),
            "inputs_lig_d": widget_shear.get("inputs_lig_d"),
            "inputs_lig_legs": widget_shear.get("inputs_lig_legs"),
        },
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Summary State Mode Marker Snapshot",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This snapshot compares module-owned `_inputs_summary_state_mode` marker assembly with legacy semantics and verifies live delegation.",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- The live page delegates `_inputs_summary_state_mode` marker assembly to `inputs_page_modules.session`.",
            "- The actual `st.session_state` write and widget shear reads remain page-owned.",
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _module_inputs_page_free(module_source: str) -> bool:
    return not re.search(r"^\s*(from\s+inputs_page\b|import\s+inputs_page\b)", module_source, re.MULTILINE)


def _module_apply_routing_free(module_source: str) -> bool:
    return not re.search(r"\b(route_apply|apply_payload)\s*[=(]", module_source)


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    page = _read(INPUTS_PAGE)
    summary_window = _function_window(page, "_resolved_inputs_summary_state")
    module_sources = {
        path.name: _read(path)
        for path in SESSION_ROOT.glob("*.py")
    }
    module_combined = "\n".join(module_sources.values())
    executable_module = "\n".join(
        source for name, source in module_sources.items() if name != "contracts.py"
    )

    from inputs_page_modules.session import build_inputs_summary_state_mode_marker_snapshot

    scenarios = [
        {
            "name": "normal_overlay_marker",
            "base": {"s_lig": 200.0, "lig_d": 10.0, "lig_legs": 2},
            "widget_shear": {"inputs_s_lig": 150.0, "inputs_lig_d": 12.0, "inputs_lig_legs": 4},
            "shared_only": False,
            "reason": "normal",
            "overlay_count": 3,
        },
        {
            "name": "shared_only_marker",
            "base": {"s_lig": 200.0, "lig_d": 10.0, "lig_legs": 2},
            "widget_shear": {"inputs_s_lig": None, "inputs_lig_d": None, "inputs_lig_legs": None},
            "shared_only": True,
            "reason": "pending_inputs_apply_refresh",
            "overlay_count": 0,
        },
    ]
    scenario_results: list[dict[str, Any]] = []
    for scenario in scenarios:
        legacy = _legacy_marker(
            base=scenario["base"],
            widget_shear=scenario["widget_shear"],
            shared_only_mode=scenario["shared_only"],
            shared_only_reason=scenario["reason"],
            overlay_count=scenario["overlay_count"],
        )
        module_snapshot = build_inputs_summary_state_mode_marker_snapshot(
            base_state=scenario["base"],
            widget_shear_state=scenario["widget_shear"],
            shared_only_mode=scenario["shared_only"],
            shared_only_reason=scenario["reason"],
            overlay_count=scenario["overlay_count"],
        )
        scenario_results.append(
            {
                "name": scenario["name"],
                "marker_matches": module_snapshot.marker_payload == legacy,
                "module_display_hash": module_snapshot.display_hash,
            }
        )

    checks = {
        "builder_exported": "build_inputs_summary_state_mode_marker_snapshot" in module_sources.get("__init__.py", ""),
        "model_exported": "InputsSummaryStateModeMarkerSnapshot" in module_sources.get("__init__.py", ""),
        "builder_present": "def build_inputs_summary_state_mode_marker_snapshot(" in module_sources.get("builders.py", ""),
        "live_page_cut_over": "build_inputs_summary_state_mode_marker_snapshot(" in summary_window
        and 'st.session_state["_inputs_summary_state_mode"] = dict(_summary_state_mode_marker.marker_payload)' in summary_window
        and "inputs_summary_state_mode_marker_delegated" in summary_window,
        "inline_page_marker_payload_deleted": 'st.session_state["_inputs_summary_state_mode"] = {' not in summary_window
        and '"shared_shear": {' not in summary_window
        and '"widget_shear": {' not in summary_window,
        "all_scenarios_match": all(row["marker_matches"] for row in scenario_results),
        "module_streamlit_free": "import streamlit" not in module_combined
        and "from streamlit" not in module_combined,
        "module_inputs_page_free": _module_inputs_page_free(module_combined),
        "module_session_mutation_free": "st.session_state" not in executable_module
        and ".session_state" not in executable_module,
        "module_apply_routing_free": _module_apply_routing_free(executable_module),
        "module_callback_execution_free": "on_change" not in executable_module
        and "sync_callback" not in executable_module,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "SESSION_SUMMARY_STATE_MODE_MARKER_DELEGATED" if not failures else "SESSION_SUMMARY_STATE_MODE_MARKER_GAPS_REMAIN"
    payload = {
        "audit": "inputs_session_summary_state_mode_marker_snapshot",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "scenarios": scenario_results,
        "live_page_cutover": True,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "next_safe_slice": "add/refresh boundary lock, then audit the next Session State sub-boundary",
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_summary_state_mode_marker_snapshot_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_summary_state_mode_marker_snapshot_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_summary_state_mode_marker_snapshot", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
