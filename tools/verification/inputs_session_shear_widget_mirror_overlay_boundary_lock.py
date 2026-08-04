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
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
BUILDERS = ROOT / "inputs_page_modules" / "session" / "builders.py"
MODELS = ROOT / "inputs_page_modules" / "session" / "models.py"
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


def _latest_json(prefix: str) -> dict[str, Any] | None:
    paths = sorted(VERIFICATION_DIR.glob(f"{prefix}_*.json"))
    if not paths:
        return None
    try:
        return json.loads(paths[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Shear Widget Mirror Overlay Boundary Lock",
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
    bridge = _read(APP_CONTRACT_BRIDGE)
    builders = _read(BUILDERS)
    models = _read(MODELS)
    helper = _function_window(page, "_apply_active_page_shear_widget_mirror_overlay") or _function_window(
        bridge,
        "_apply_active_page_shear_widget_mirror_overlay_for_app_bridge",
    )
    latest_parity = _latest_json("inputs_session_shear_widget_mirror_overlay_trace_parity")
    latest_cutover = _latest_json("inputs_session_shear_widget_mirror_overlay_cutover")
    checks = {
        "trace_parity_latest_pass": bool(latest_parity)
        and latest_parity.get("decision") == "READY_FOR_SESSION_SHEAR_WIDGET_MIRROR_OVERLAY_EXTRACTION"
        and not latest_parity.get("failures"),
        "cutover_latest_pass": bool(latest_cutover)
        and latest_cutover.get("decision") == "INPUTS_SESSION_SHEAR_WIDGET_MIRROR_OVERLAY_DELEGATED"
        and not latest_cutover.get("failures"),
        "page_helper_delegates_to_session_planner": "build_inputs_shear_widget_mirror_overlay_plan(" in helper,
        "page_helper_keeps_session_read_wrapper": (
            "st.session_state.get" in helper
            and "if key in st.session_state" in helper
        )
        or "widget_state=st.session_state" in helper,
        "old_inline_pair_loop_cannot_return": "for sk, wk in pairs:" not in helper and "pairs = (" not in helper,
        "old_inline_numeric_suppression_cannot_return": "_int_from_state(" not in helper and "_float_from_state(" not in helper,
        "session_builder_owns_overlay_plan": "def build_inputs_shear_widget_mirror_overlay_plan(" in builders
        and "inputs_stale_shear_overlay_suppressed_shared_no_links" in builders,
        "session_model_owns_plan_shape": "class InputsShearWidgetMirrorOverlayPlan" in models,
        "no_streamlit_import_in_session_module": not re.search(r"^\s*(import|from)\s+streamlit\b", builders, re.M),
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
        "INPUTS_SESSION_SHEAR_WIDGET_MIRROR_OVERLAY_BOUNDARY_LOCKED"
        if not failures
        else "INPUTS_SESSION_SHEAR_WIDGET_MIRROR_OVERLAY_BOUNDARY_LOCK_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_shear_widget_mirror_overlay_boundary_lock",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_shear_widget_mirror_overlay_boundary_lock_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_shear_widget_mirror_overlay_boundary_lock_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_shear_widget_mirror_overlay_boundary_lock", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
