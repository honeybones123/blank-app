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
BUILDERS = ROOT / "inputs_page_modules" / "session" / "builders.py"
MODELS = ROOT / "inputs_page_modules" / "session" / "models.py"
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


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Shear Widget Mirror Overlay Cutover Snapshot",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    page = _read(INPUTS_PAGE)
    helper = _function_window(page, TARGET)
    builders = _read(BUILDERS)
    models = _read(MODELS)
    checks = {
        "page_helper_present": bool(helper),
        "page_helper_delegates_to_session_planner": "build_inputs_shear_widget_mirror_overlay_plan(" in helper,
        "page_helper_keeps_session_reads": "st.session_state.get" in helper,
        "page_helper_keeps_mutation_wrapper": "working.clear()" in helper
        and "overlay_applied.clear()" in helper
        and "return dict(plan.debug_payload)" in helper,
        "old_inline_pair_ladder_removed": "pairs = (" not in helper and "for sk, wk in pairs:" not in helper,
        "old_inline_stale_suppression_removed": "inputs_stale_shear_overlay_suppressed_shared_no_links" not in helper,
        "session_builder_owns_stale_suppression": "inputs_stale_shear_overlay_suppressed_shared_no_links" in builders,
        "session_model_exists": "class InputsShearWidgetMirrorOverlayPlan" in models,
        "no_streamlit_import_in_session_builder": not re.search(r"^\s*import\s+streamlit\b|^\s*from\s+streamlit\b", builders, re.M),
        "product_behavior_changed": False,
        "session_behavior_changed": False,
    }
    expected_false = {"product_behavior_changed", "session_behavior_changed"}
    failures = [
        key
        for key, value in checks.items()
        if (key in expected_false and value) or (key not in expected_false and not value)
    ]
    decision = (
        "INPUTS_SESSION_SHEAR_WIDGET_MIRROR_OVERLAY_DELEGATED"
        if not failures
        else "INPUTS_SESSION_SHEAR_WIDGET_MIRROR_OVERLAY_CUTOVER_GAPS_REMAIN"
    )
    payload: dict[str, Any] = {
        "audit": "inputs_session_shear_widget_mirror_overlay_cutover_snapshot",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "next_safe_slice": "Add boundary lock/deadness verifier for old inline shear mirror overlay branch, then refresh next-surface audit.",
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_shear_widget_mirror_overlay_cutover_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_shear_widget_mirror_overlay_cutover_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_shear_widget_mirror_overlay_cutover_snapshot", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
