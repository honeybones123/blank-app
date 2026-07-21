from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_guidance_cache_result


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


def _old_cache_result(
    *,
    fingerprint: Any,
    simple_cached_fp: Any,
    simple_cached_items: Any,
    simple_debug: dict[str, Any],
    simple_debug_trustworthy: bool,
    cached_fp: Any,
    cached_items: Any,
    cached_debug: dict[str, Any],
    cached_debug_trustworthy: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any], bool]:
    if simple_cached_fp == fingerprint and simple_cached_items is not None:
        if not simple_debug_trustworthy:
            return [], {}, False
        return list(simple_cached_items or []), dict(simple_debug or {}), True
    if cached_fp != fingerprint:
        return [], {}, False
    if not cached_debug_trustworthy:
        return [], {}, False
    return list(cached_items or []), dict(cached_debug or {}), True


def _scenarios() -> list[dict[str, Any]]:
    fp = ("beam", "state", 1)
    other = ("beam", "state", 2)
    return [
        {
            "name": "simple_hit",
            "fingerprint": fp,
            "simple_fp": fp,
            "simple_items": [{"id": "simple"}],
            "simple_debug": {"ok": True},
            "simple_debug_ok": True,
            "cached_fp": fp,
            "cached_items": [{"id": "cached"}],
            "cached_debug": {"ok": True},
            "cached_debug_ok": True,
        },
        {
            "name": "simple_hit_empty_items",
            "fingerprint": fp,
            "simple_fp": fp,
            "simple_items": [],
            "simple_debug": {"ok": True},
            "simple_debug_ok": True,
            "cached_fp": other,
            "cached_items": [{"id": "cached"}],
            "cached_debug": {"ok": True},
            "cached_debug_ok": True,
        },
        {
            "name": "simple_hit_untrusted_debug",
            "fingerprint": fp,
            "simple_fp": fp,
            "simple_items": [{"id": "simple"}],
            "simple_debug": {"ok": False},
            "simple_debug_ok": False,
            "cached_fp": fp,
            "cached_items": [{"id": "cached"}],
            "cached_debug": {"ok": True},
            "cached_debug_ok": True,
        },
        {
            "name": "simple_missing_items_falls_to_cached",
            "fingerprint": fp,
            "simple_fp": fp,
            "simple_items": None,
            "simple_debug": {"ok": True},
            "simple_debug_ok": True,
            "cached_fp": fp,
            "cached_items": [{"id": "cached"}],
            "cached_debug": {"ok": True},
            "cached_debug_ok": True,
        },
        {
            "name": "fingerprint_miss",
            "fingerprint": fp,
            "simple_fp": other,
            "simple_items": [{"id": "simple"}],
            "simple_debug": {"ok": True},
            "simple_debug_ok": True,
            "cached_fp": other,
            "cached_items": [{"id": "cached"}],
            "cached_debug": {"ok": True},
            "cached_debug_ok": True,
        },
        {
            "name": "cached_untrusted_debug",
            "fingerprint": fp,
            "simple_fp": other,
            "simple_items": [{"id": "simple"}],
            "simple_debug": {"ok": True},
            "simple_debug_ok": True,
            "cached_fp": fp,
            "cached_items": [{"id": "cached"}],
            "cached_debug": {"ok": False},
            "cached_debug_ok": False,
        },
        {
            "name": "cached_hit_none_items",
            "fingerprint": fp,
            "simple_fp": other,
            "simple_items": [{"id": "simple"}],
            "simple_debug": {"ok": True},
            "simple_debug_ok": True,
            "cached_fp": fp,
            "cached_items": None,
            "cached_debug": {"ok": True},
            "cached_debug_ok": True,
        },
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Guidance Cache Result Cutover",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        f"- scenarios checked: `{len(payload['scenario_results'])}`",
        f"- mismatches: `{len(payload['mismatches'])}`",
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
    helper = _function_window(source, "_get_cached_design_guide_guidance")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    scenario_results = []
    mismatches = []
    for row in _scenarios():
        old_items, old_debug, old_hit = _old_cache_result(
            fingerprint=row["fingerprint"],
            simple_cached_fp=row["simple_fp"],
            simple_cached_items=row["simple_items"],
            simple_debug=row["simple_debug"],
            simple_debug_trustworthy=row["simple_debug_ok"],
            cached_fp=row["cached_fp"],
            cached_items=row["cached_items"],
            cached_debug=row["cached_debug"],
            cached_debug_trustworthy=row["cached_debug_ok"],
        )
        new = build_inputs_design_guide_guidance_cache_result(
            fingerprint=row["fingerprint"],
            simple_cached_fp=row["simple_fp"],
            simple_cached_items=row["simple_items"],
            simple_debug=row["simple_debug"],
            simple_debug_trustworthy=row["simple_debug_ok"],
            cached_fp=row["cached_fp"],
            cached_items=row["cached_items"],
            cached_debug=row["cached_debug"],
            cached_debug_trustworthy=row["cached_debug_ok"],
        )
        match = (
            old_items == list(new.items)
            and old_debug == dict(new.debug)
            and bool(old_hit) == bool(new.cache_hit)
            and bool(new.display_hash)
        )
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old_items": old_items,
                "new_items": list(new.items),
                "old_debug": old_debug,
                "new_debug": dict(new.debug),
                "old_hit": bool(old_hit),
                "new_hit": bool(new.cache_hit),
                "source": new.source,
                "display_hash_present": bool(new.display_hash),
            }
        )
        if not match:
            mismatches.append(scenario_results[-1])

    checks = {
        "helper_delegates_to_session_builder": "build_inputs_design_guide_guidance_cache_result(" in helper,
        "helper_keeps_session_reads": "st.session_state.get" in helper,
        "helper_keeps_debug_trust_callback": "_debug_trustworthy(" in helper,
        "helper_keeps_speed_diag": "_dg_speed_diag_note_guidance_cache(" in helper,
        "old_inline_simple_branch_removed": "if simple_cached_fp == fingerprint and simple_cached_items is not None:" not in helper,
        "old_inline_cached_fp_branch_removed": "if cached_fp != fingerprint:" not in helper,
        "old_inline_trust_return_removed": "return [], {}, False" not in helper,
        "session_builder_exists": "def build_inputs_design_guide_guidance_cache_result(" in builders,
        "session_model_exists": "class InputsDesignGuideGuidanceCacheResult" in models,
        "session_init_exports_builder": "build_inputs_design_guide_guidance_cache_result" in init_source,
        "session_init_exports_model": "InputsDesignGuideGuidanceCacheResult" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_GUIDANCE_CACHE_RESULT_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_GUIDANCE_CACHE_RESULT_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_guidance_cache_result_cutover",
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
        "debug_trust_validation_moved": False,
        "speed_diagnostics_moved": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_guidance_cache_result_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_guidance_cache_result_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_guide_guidance_cache_result_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
