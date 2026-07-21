from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_cached_publication_availability_decision


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


def _old_available(
    *,
    fingerprint: Any,
    simple_cached_fp: Any,
    simple_cached_items_present: bool,
    simple_debug_complete: bool,
    cached_fp: Any,
    cached_items_present: bool,
    cached_debug_complete: bool,
) -> bool:
    if simple_cached_fp == fingerprint and bool(simple_cached_items_present):
        return bool(simple_debug_complete)
    if cached_fp == fingerprint and bool(cached_items_present):
        return bool(cached_debug_complete)
    return False


def _scenarios() -> list[dict[str, Any]]:
    fp = ("beam", "state", 1)
    other = ("beam", "state", 2)
    return [
        {
            "name": "simple_hit_complete_debug",
            "fingerprint": fp,
            "simple_cached_fp": fp,
            "simple_items": True,
            "simple_debug": True,
            "cached_fp": other,
            "cached_items": True,
            "cached_debug": True,
        },
        {
            "name": "simple_hit_incomplete_debug",
            "fingerprint": fp,
            "simple_cached_fp": fp,
            "simple_items": True,
            "simple_debug": False,
            "cached_fp": other,
            "cached_items": True,
            "cached_debug": True,
        },
        {
            "name": "simple_fp_match_missing_items_cached_hit",
            "fingerprint": fp,
            "simple_cached_fp": fp,
            "simple_items": False,
            "simple_debug": True,
            "cached_fp": fp,
            "cached_items": True,
            "cached_debug": True,
        },
        {
            "name": "guidance_cache_hit_complete_debug",
            "fingerprint": fp,
            "simple_cached_fp": other,
            "simple_items": True,
            "simple_debug": True,
            "cached_fp": fp,
            "cached_items": True,
            "cached_debug": True,
        },
        {
            "name": "guidance_cache_hit_incomplete_debug",
            "fingerprint": fp,
            "simple_cached_fp": other,
            "simple_items": True,
            "simple_debug": True,
            "cached_fp": fp,
            "cached_items": True,
            "cached_debug": False,
        },
        {
            "name": "guidance_cache_missing_items",
            "fingerprint": fp,
            "simple_cached_fp": other,
            "simple_items": True,
            "simple_debug": True,
            "cached_fp": fp,
            "cached_items": False,
            "cached_debug": True,
        },
        {
            "name": "miss",
            "fingerprint": fp,
            "simple_cached_fp": other,
            "simple_items": True,
            "simple_debug": True,
            "cached_fp": other,
            "cached_items": True,
            "cached_debug": True,
        },
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Cached Publication Availability Cutover",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        f"- scenarios checked: `{len(payload['scenario_results'])}`",
        f"- mismatches: `{len(payload['mismatches'])}`",
        f"- product behavior changed: `{payload['product_behavior_changed']}`",
        f"- session reads moved: `{payload['session_reads_moved']}`",
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
    helper = _function_window(source, "_design_guide_settle_gate_cached_publication_available")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    scenario_results = []
    mismatches = []
    for row in _scenarios():
        old = _old_available(
            fingerprint=row["fingerprint"],
            simple_cached_fp=row["simple_cached_fp"],
            simple_cached_items_present=row["simple_items"],
            simple_debug_complete=row["simple_debug"],
            cached_fp=row["cached_fp"],
            cached_items_present=row["cached_items"],
            cached_debug_complete=row["cached_debug"],
        )
        new = build_inputs_design_guide_cached_publication_availability_decision(
            fingerprint=row["fingerprint"],
            simple_cached_fp=row["simple_cached_fp"],
            simple_cached_items_present=row["simple_items"],
            simple_debug_complete=row["simple_debug"],
            cached_fp=row["cached_fp"],
            cached_items_present=row["cached_items"],
            cached_debug_complete=row["cached_debug"],
        )
        match = bool(old) == bool(new.available) and bool(new.display_hash)
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old": bool(old),
                "new": bool(new.available),
                "source": new.source,
                "display_hash_present": bool(new.display_hash),
            }
        )
        if not match:
            mismatches.append({"scenario": row["name"], "old": bool(old), "new": bool(new.available)})

    checks = {
        "helper_delegates_to_session_builder": "build_inputs_design_guide_cached_publication_availability_decision(" in helper,
        "helper_keeps_session_reads": "st.session_state.get" in helper,
        "helper_keeps_debug_bundle_validation": "_design_guide_cached_debug_bundle_complete(" in helper,
        "old_page_precedence_policy_removed": "if simple_cached_fp == fingerprint" not in helper
        and "if cached_fp == fingerprint" not in helper,
        "session_builder_exists": "def build_inputs_design_guide_cached_publication_availability_decision(" in builders,
        "session_model_exists": "class InputsDesignGuideCachedPublicationAvailabilityDecision" in models,
        "session_init_exports_builder": "build_inputs_design_guide_cached_publication_availability_decision" in init_source,
        "session_init_exports_model": "InputsDesignGuideCachedPublicationAvailabilityDecision" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_CACHED_PUBLICATION_AVAILABILITY_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_CACHED_PUBLICATION_AVAILABILITY_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_cached_publication_availability_cutover",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "scenario_results": scenario_results,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "session_reads_moved": False,
        "session_writes_moved": False,
        "debug_bundle_validation_moved": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "streamlit_reads_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_cached_publication_availability_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_cached_publication_availability_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_guide_cached_publication_availability_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
