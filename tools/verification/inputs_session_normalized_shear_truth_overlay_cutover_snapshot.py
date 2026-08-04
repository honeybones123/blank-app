from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_normalized_shear_truth_overlay_snapshot


INPUTS_PAGE = ROOT / "inputs_page.py"
SESSION_BUILDERS = ROOT / "inputs_page_modules" / "session" / "builders.py"
SESSION_MODELS = ROOT / "inputs_page_modules" / "session" / "models.py"
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


def _old_overlay(
    base_state: dict[str, Any],
    session_values: dict[str, Any],
    normalized_values: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(base_state or {})
    merged.update(dict(session_values or {}))
    merged.update(dict(normalized_values or {}))
    return merged


def _scenario_rows() -> list[dict[str, Any]]:
    return [
        {
            "name": "empty_state",
            "base": {},
            "session": {},
            "normalized": {},
        },
        {
            "name": "session_overrides_base",
            "base": {"Vu_star": 100.0, "other": "kept"},
            "session": {"Vu_star": 120.0, "shear_truth_status": "pass"},
            "normalized": {"final_shear_truth_resolved": True},
        },
        {
            "name": "normalized_overrides_session",
            "base": {"final_shear_truth_resolved": False},
            "session": {"final_shear_truth_resolved": False, "shear_truth_reason": "old"},
            "normalized": {"final_shear_truth_resolved": True, "shear_truth_reason": "normalized"},
        },
        {
            "name": "missing_values_preserved",
            "base": {"phi_Vu_cap": None},
            "session": {"phi_Vu_cap": 22.0, "published_result_spacing_mm": None},
            "normalized": {"_final_shear_truth_normalized_source": "test"},
        },
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Normalized Shear Truth Overlay Cutover Snapshot",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "## Result",
        "",
        f"- scenarios checked: `{len(payload['scenarios'])}`",
        f"- mismatches: `{len(payload['mismatches'])}`",
        f"- product behavior changed: `{payload['product_behavior_changed']}`",
        "",
        "## Source Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    if payload["mismatches"]:
        lines.extend(["", "## Mismatches", ""])
        for row in payload["mismatches"]:
            lines.append(f"- `{row['scenario']}`")
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = _read(INPUTS_PAGE)
    helper = _function_window(source, "_overlay_current_normalized_shear_truth")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    scenarios = []
    mismatches = []
    for row in _scenario_rows():
        old = _old_overlay(row["base"], row["session"], row["normalized"])
        new_snapshot = build_inputs_normalized_shear_truth_overlay_snapshot(
            base_state=row["base"],
            session_shear_truth_values=row["session"],
            normalized_shear_truth_values=row["normalized"],
        )
        new = dict(new_snapshot.merged_state)
        match = old == new
        scenarios.append(
            {
                "scenario": row["name"],
                "match": match,
                "old": old,
                "new": new,
                "display_hash": new_snapshot.display_hash,
            }
        )
        if not match:
            mismatches.append({"scenario": row["name"], "old": old, "new": new})
    checks = {
        "page_helper_delegates_to_session_builder": "build_inputs_normalized_shear_truth_overlay_snapshot(" in helper,
        "page_helper_keeps_session_reads": "st.session_state" in helper,
        "page_helper_keeps_normalization_callback": "normalize_final_published_shear_truth(pre_normalized)" in helper,
        "old_inline_return_loop_removed": "for key in _CURRENT_SHEAR_TRUTH_SESSION_KEYS:" not in helper
        and "merged.update(normalize_final_published_shear_truth(merged))" not in helper,
        "session_builder_exists": "def build_inputs_normalized_shear_truth_overlay_snapshot(" in builders,
        "session_model_exists": "class InputsNormalizedShearTruthOverlaySnapshot" in models,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "INPUTS_SESSION_NORMALIZED_SHEAR_TRUTH_OVERLAY_CUTOVER_LOCKED" if not failures else "INPUTS_SESSION_NORMALIZED_SHEAR_TRUTH_OVERLAY_CUTOVER_GAPS_REMAIN"
    payload = {
        "audit": "inputs_session_normalized_shear_truth_overlay_cutover_snapshot",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "scenarios": scenarios,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_normalized_shear_truth_overlay_cutover_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_normalized_shear_truth_overlay_cutover_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_normalized_shear_truth_overlay_cutover_snapshot", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
