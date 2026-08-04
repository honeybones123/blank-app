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
SESSION_MODELS = ROOT / "inputs_page_modules" / "session" / "models.py"
SESSION_BUILDERS = ROOT / "inputs_page_modules" / "session" / "builders.py"
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
        if lines[idx - 1].startswith("def "):
            end = idx - 1
            break
    return start, end


def _constant_tuple(source: str, name: str) -> tuple[str, ...]:
    match = re.search(rf"{re.escape(name)}:\s*tuple\[str,\s*\.\.\.\]\s*=\s*\((.*?)\)\n", source, re.S)
    if not match:
        return ()
    return tuple(re.findall(r'"([^"]+)"', match.group(1)))


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Normalized Shear Truth Overlay Boundary Audit",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "## Surface",
        "",
        f"- function: `_overlay_current_normalized_shear_truth(...)`",
        f"- lines: `{payload['line_range']}`",
        f"- current owner: `{payload['current_owner']}`",
        f"- target owner: `{payload['target_owner']}`",
        "",
        "## Classification",
        "",
    ]
    for row in payload["classification"]:
        lines.extend(
            [
                f"### {row['surface']}",
                f"- owner now: {row['owner_now']}",
                f"- target owner: {row['target_owner']}",
                f"- action: {row['action']}",
                f"- reason: {row['reason']}",
                "",
            ]
        )
    lines.extend(["## Checks", ""])
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## First Safe Implementation Slice", "", payload["first_safe_slice"], ""])
    lines.extend(["## Stop Conditions", ""])
    for item in payload["stop_conditions"]:
        lines.append(f"- {item}")
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = _read(INPUTS_PAGE)
    models = _read(SESSION_MODELS)
    builders = _read(SESSION_BUILDERS)
    helper = _function_window(source, "_overlay_current_normalized_shear_truth")
    keys = _constant_tuple(source, "_CURRENT_SHEAR_TRUTH_SESSION_KEYS")
    checks = {
        "helper_present": bool(helper),
        "session_key_inventory_present": bool(keys) and len(keys) >= 10,
        "helper_reads_session": "st.session_state" in helper,
        "helper_uses_explicit_key_inventory": "_CURRENT_SHEAR_TRUTH_SESSION_KEYS" in helper,
        "helper_calls_normalized_shear_truth_callback": "normalize_final_published_shear_truth(" in helper,
        "helper_returns_new_merged_dict": "merged = dict(state or {})" in helper and "return merged" in helper,
        "session_module_does_not_yet_own_overlay_model": "InputsNormalizedShearTruthOverlay" not in models,
        "session_module_does_not_yet_own_overlay_builder": "build_inputs_normalized_shear_truth_overlay" not in builders,
        "no_streamlit_import_expected_in_session_module": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "no_runtime_behavior_changed_by_audit": True,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "READY_FOR_SESSION_NORMALIZED_SHEAR_TRUTH_OVERLAY_TRACE_PARITY" if not failures else "SESSION_NORMALIZED_SHEAR_TRUTH_OVERLAY_AUDIT_GAPS_REMAIN"
    payload = {
        "audit": "inputs_session_normalized_shear_truth_overlay_boundary_audit",
        "timestamp": timestamp,
        "decision": decision,
        "line_range": _line_range(source, "_overlay_current_normalized_shear_truth"),
        "current_owner": "inputs_page.py owns session key iteration, state merge, and normalized shear truth callback execution",
        "target_owner": "inputs_page_modules.session should own pure overlay planning; inputs_page.py should keep st.session_state reads and normalize_final_published_shear_truth callback execution",
        "session_key_count": len(keys),
        "session_keys": keys,
        "checks": checks,
        "failures": failures,
        "classification": [
            {
                "surface": "base state copy",
                "owner_now": "inputs_page.py",
                "target_owner": "inputs_page_modules.session",
                "action": "move",
                "reason": "pure data-copy/materialization; no Streamlit dependency once explicit state is passed",
            },
            {
                "surface": "current shear truth session key inventory",
                "owner_now": "inputs_page.py constant",
                "target_owner": "inputs_page.py for now",
                "action": "keep temporarily",
                "reason": "inventory is still shared by page-local callers; move only with parity proof to avoid widening scope",
            },
            {
                "surface": "session reads",
                "owner_now": "inputs_page.py",
                "target_owner": "inputs_page.py",
                "action": "keep",
                "reason": "Streamlit/session access remains page-shell owned",
            },
            {
                "surface": "session value overlay into merged state",
                "owner_now": "inputs_page.py",
                "target_owner": "inputs_page_modules.session",
                "action": "move after trace parity",
                "reason": "pure deterministic merge once explicit session values are supplied",
            },
            {
                "surface": "normalize_final_published_shear_truth callback execution",
                "owner_now": "inputs_page.py",
                "target_owner": "inputs_page.py for first cutover",
                "action": "keep as callback",
                "reason": "shared normalized shear truth API may be outside session module; first slice should not move callback ownership",
            },
        ],
        "first_safe_slice": (
            "Add a session dataclass and builder that accepts `base_state`, explicit `session_shear_truth_values`, "
            "and `normalized_shear_truth_values`; compare it against the current helper trace-only before any live cutover."
        ),
        "required_next_verifier": "inputs_session_normalized_shear_truth_overlay_trace_parity.py",
        "stop_conditions": [
            "merged state differs",
            "normalized shear truth values differ",
            "session reads move into inputs_page_modules.session",
            "normalize_final_published_shear_truth callback ownership changes",
            "any caller output changes",
        ],
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_normalized_shear_truth_overlay_boundary_audit_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_normalized_shear_truth_overlay_boundary_audit_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_normalized_shear_truth_overlay_boundary_audit", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
