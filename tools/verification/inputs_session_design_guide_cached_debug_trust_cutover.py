from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_cached_debug_trust_decision


INPUTS_PAGE = ROOT / "inputs_page.py"
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
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


def _old_trust(
    *,
    bundle_complete: bool,
    debug_publication_fingerprint: Any,
    requested_fingerprint: Any,
) -> bool:
    if not bool(bundle_complete):
        return False
    return debug_publication_fingerprint in (None, "", str(requested_fingerprint))


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Cached Debug Trust Cutover",
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
    source = "\n".join(
        _read(path)
        for path in (INPUTS_PAGE, ROUTE_COORDINATORS, APP_CONTRACT_BRIDGE)
        if path.exists()
    )
    helper = _function_window(source, "_get_cached_design_guide_guidance")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    fingerprint = ("beam", "state", 1)
    scenarios = [
        {
            "name": "complete_unscoped_none",
            "bundle_complete": True,
            "debug_fp": None,
            "requested_fp": fingerprint,
        },
        {
            "name": "complete_unscoped_empty",
            "bundle_complete": True,
            "debug_fp": "",
            "requested_fp": fingerprint,
        },
        {
            "name": "complete_matching_string",
            "bundle_complete": True,
            "debug_fp": str(fingerprint),
            "requested_fp": fingerprint,
        },
        {
            "name": "complete_mismatch",
            "bundle_complete": True,
            "debug_fp": "other",
            "requested_fp": fingerprint,
        },
        {
            "name": "incomplete_even_if_matching",
            "bundle_complete": False,
            "debug_fp": str(fingerprint),
            "requested_fp": fingerprint,
        },
    ]
    scenario_results = []
    mismatches = []
    for row in scenarios:
        old = _old_trust(
            bundle_complete=row["bundle_complete"],
            debug_publication_fingerprint=row["debug_fp"],
            requested_fingerprint=row["requested_fp"],
        )
        new = build_inputs_design_guide_cached_debug_trust_decision(
            bundle_complete=row["bundle_complete"],
            debug_publication_fingerprint=row["debug_fp"],
            requested_fingerprint=row["requested_fp"],
        )
        match = bool(old) == bool(new.trustworthy) and bool(new.display_hash)
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old": bool(old),
                "new": bool(new.trustworthy),
                "reason": new.reason,
                "display_hash_present": bool(new.display_hash),
            }
        )
        if not match:
            mismatches.append({"scenario": row["name"], "old": bool(old), "new": bool(new.trustworthy)})

    checks = {
        "cache_helper_delegates_to_session_builder": "build_inputs_design_guide_cached_debug_trust_decision(" in helper,
        "cache_helper_keeps_bundle_complete_callback": "_design_guide_cached_debug_bundle_complete(" in helper,
        "cache_helper_keeps_session_reads": "st.session_state.get(DESIGN_GUIDE_GUIDANCE_CACHE_DEBUG_KEY)" in helper,
        "old_inline_completion_return_removed": "return debug_fp in (None, \"\", str(fingerprint))" not in helper,
        "session_builder_exists": "def build_inputs_design_guide_cached_debug_trust_decision(" in builders,
        "session_model_exists": "class InputsDesignGuideCachedDebugTrustDecision" in models,
        "session_init_exports_builder": "build_inputs_design_guide_cached_debug_trust_decision" in init_source,
        "session_init_exports_model": "InputsDesignGuideCachedDebugTrustDecision" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_CACHED_DEBUG_TRUST_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_CACHED_DEBUG_TRUST_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_cached_debug_trust_cutover",
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
        "debug_bundle_completeness_moved": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_cached_debug_trust_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_cached_debug_trust_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_guide_cached_debug_trust_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
