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
TARGET = "_overlay_inputs_reo_widget_mirrors_for_model"


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
        "# Inputs Session Model Reo Widget Mirror Overlay Boundary Audit",
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
    lines.extend(["", "## First Safe Implementation Slice", "", payload["first_safe_slice"], ""])
    lines.extend(["## Stop Conditions", ""])
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
        "has_inputs_page_gate": 'st.session_state.get("page_slug")' in window and '"not_inputs_page"' in window,
        "has_summary_shared_only_gate": "summary_shared_only_mode" in window and "post_force_refresh_this_run" in window,
        "has_row_widget_overlay_loop": 'for section in ("bot", "top"):' in window and 'f"inputs_{section}_row_count"' in window,
        "has_coord_stale_detection": "def _coords_stale_for" in window
        and "bot_bar_coords_stale" in window
        and "top_bar_coords_stale" in window,
        "calls_canonical_pack_when_overlay_changes": "_build_canonical_design_state_pack(" in window,
        "uses_legacy_longitudinal_mirror_builder": "build_legacy_longitudinal_mirrors_from_rows(" in window,
        "does_not_touch_design_guide_or_apply": "DesignGuide" not in window and "apply" not in window.lower(),
        "no_live_change_in_this_audit": True,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "READY_FOR_SESSION_MODEL_REO_WIDGET_MIRROR_OVERLAY_TRACE_PARITY_WITH_PAGE_PACK_CALLBACK"
        if not failures
        else "SESSION_MODEL_REO_WIDGET_MIRROR_OVERLAY_BOUNDARY_GAPS_REMAIN"
    )
    payload: dict[str, Any] = {
        "audit": "inputs_session_model_reo_widget_mirror_overlay_boundary_audit",
        "timestamp": timestamp,
        "decision": decision,
        "line_range": _line_range(source, TARGET),
        "checks": checks,
        "failures": failures,
        "calls": calls,
        "classification": {
            "current_owner": "inputs_page.py",
            "target_owner": "split boundary: inputs_page_modules.session can own pure model mirror planning after parity; page/shared keeps canonical pack callback execution initially",
            "page_shell_inputs": [
                "page_slug",
                "summary_debug",
                "current row widget values",
                "current model state",
            ],
            "module_candidate_logic": [
                "inputs-page eligibility from explicit slug",
                "summary shared-only suppression from explicit summary_debug",
                "row widget scalar overlay plan",
                "coordinate stale detection",
                "debug payload shape",
            ],
            "must_remain_page_owned_now": [
                "st.session_state reads",
                "_build_canonical_design_state_pack execution",
                "build_legacy_longitudinal_mirrors_from_rows execution unless separately proven service-owned",
                "visual model call orchestration",
            ],
            "engineering_behavior_changed": False,
            "visible_behavior_changed": False,
            "session_behavior_changed": False,
        },
        "first_safe_slice": (
            "Create a trace-only planner in `inputs_page_modules.session` that accepts explicit page slug, summary debug, widget values, and state. "
            "The planner should return scalar overlay keys, coordinate-stale keys, and debug intent. "
            "Keep `_build_canonical_design_state_pack(...)` and `build_legacy_longitudinal_mirrors_from_rows(...)` execution in `inputs_page.py` until a separate parity proof exists."
        ),
        "required_next_verifier": "inputs_session_model_reo_widget_mirror_overlay_trace_parity.py",
        "stop_conditions": [
            "model state output differs",
            "debug payload differs",
            "canonical pack execution moves into session module",
            "session reads move into inputs_page_modules.session",
            "summary shared-only suppression changes",
            "row widget coercion changes",
            "coordinate stale detection changes",
        ],
        "product_behavior_changed": False,
        "session_behavior_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_model_reo_widget_mirror_overlay_boundary_audit_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_model_reo_widget_mirror_overlay_boundary_audit_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_model_reo_widget_mirror_overlay_boundary_audit", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
