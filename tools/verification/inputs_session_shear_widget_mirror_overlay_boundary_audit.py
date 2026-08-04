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
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_apply_active_page_shear_widget_mirror_overlay"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_window(source: str, name: str) -> str:
    marker = f"def {name}("
    if marker not in source:
        return ""
    window = source.split(marker, 1)[1].split("\ndef ", 1)[0]
    return window.split("\n", 1)[1] if "\n" in window else window


def _line_range(source: str, name: str) -> tuple[int | None, int | None]:
    lines = source.splitlines()
    start = None
    for idx, line in enumerate(lines, start=1):
        if line.startswith(f"def {name}("):
            start = idx
            break
    if start is None:
        return None, None
    end = len(lines)
    for idx in range(start + 1, len(lines) + 1):
        line = lines[idx - 1]
        if line.startswith("def ") and idx > start:
            end = idx - 1
            break
    return start, end


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Shear Widget Mirror Overlay Boundary Audit",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "## Surface Targeted",
        "",
        f"- function: `{TARGET}`",
        f"- lines: `{payload['line_range']}`",
        "",
        "## Ownership Classification",
        "",
    ]
    for key, value in payload["classification"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Checks", ""])
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            "",
            payload["first_safe_slice"],
            "",
            "## Stop Conditions",
            "",
        ]
    )
    for item in payload["stop_conditions"]:
        lines.append(f"- {item}")
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = _read(INPUTS_PAGE)
    window = _function_window(source, TARGET)
    calls = sorted(set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\(", window)))
    checks = {
        "target_helper_present": bool(window),
        "reads_page_session_state": "st.session_state" in window,
        "does_not_write_session_state": "st.session_state[" not in window and ".session_state[" not in window,
        "mutates_only_passed_working_state": "working[" in window and "overlay_applied[" in window,
        "has_inputs_page_source_lane": '"inputs_s_lig"' in window and '"inputs_lig_d"' in window and '"inputs_lig_legs"' in window,
        "has_shear_page_source_lane": '"shear_s_lig"' in window and '"shear_lig_d"' in window and '"shear_lig_legs"' in window,
        "has_shared_only_fallback_lane": '"shared_only"' in window and "base.get(sk)" in window,
        "has_stale_no_links_suppression": "inputs_stale_shear_overlay_suppressed_shared_no_links" in window,
        "uses_page_numeric_read_helpers": "_int_from_state" in window and "_float_from_state" in window,
        "does_not_call_design_guide_or_apply": "DesignGuide" not in window and "apply" not in window.lower(),
        "no_live_change_in_this_audit": True,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "READY_FOR_SESSION_SHEAR_WIDGET_MIRROR_OVERLAY_TRACE_PARITY"
        if not failures
        else "SESSION_SHEAR_WIDGET_MIRROR_OVERLAY_BOUNDARY_GAPS_REMAIN"
    )
    payload: dict[str, Any] = {
        "audit": "inputs_session_shear_widget_mirror_overlay_boundary_audit",
        "timestamp": timestamp,
        "decision": decision,
        "line_range": _line_range(source, TARGET),
        "checks": checks,
        "failures": failures,
        "classification": {
            "current_owner": "inputs_page.py",
            "target_owner": "split boundary: page keeps session/current-page reads; inputs_page_modules.session can own pure overlay planning after parity",
            "page_shell_inputs": [
                "page_slug",
                "base summary state",
                "current widget scalar values",
                "working state dict",
                "overlay_applied dict",
            ],
            "module_candidate_logic": [
                "source lane selection result",
                "working-state overlay plan",
                "overlay_applied delta plan",
                "stale no-link suppression decision",
                "debug payload shape",
            ],
            "must_remain_page_owned_now": [
                "st.session_state reads",
                "current page / active tab source selection input",
                "mutation of live working and overlay_applied objects until parity cutover",
            ],
            "engineering_behavior_changed": False,
            "visible_behavior_changed": False,
            "session_behavior_changed": False,
        },
        "calls": calls,
        "first_safe_slice": (
            "Add typed trace-only source/plan models for shear widget mirror overlay planning in `inputs_page_modules.session`; "
            "run the module planner beside `_apply_active_page_shear_widget_mirror_overlay(...)` for inputs, shear, other-page, stale-no-link, and missing-widget cases. "
            "Do not cut over until the planner output exactly matches working-state mutations, overlay-applied mutations, and debug payload."
        ),
        "required_next_verifier": "inputs_session_shear_widget_mirror_overlay_trace_parity.py",
        "stop_conditions": [
            "working-state overlay differs",
            "overlay_applied delta differs",
            "debug payload differs",
            "stale no-link suppression differs",
            "session reads move into inputs_page_modules.session",
            "derived recompute or normalized shear truth overlay is touched",
        ],
        "product_behavior_changed": False,
        "session_behavior_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_shear_widget_mirror_overlay_boundary_audit_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_shear_widget_mirror_overlay_boundary_audit_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_shear_widget_mirror_overlay_boundary_audit", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
