from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_apply_trace_run_end_outcome


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


def _old_outcome(
    *,
    current_overview: Mapping[str, Any] | None,
    final_util_override: Any,
    final_statuses_override: Mapping[str, Any] | None,
) -> tuple[Any, dict[str, Any]]:
    overview = dict(current_overview or {})
    final_util = overview.get("worst_util")
    if final_util_override is not None:
        try:
            final_util = float(final_util_override)
        except Exception:
            pass
    statuses = dict(overview.get("statuses") or {})
    if not statuses and isinstance(final_statuses_override, Mapping) and final_statuses_override:
        statuses = dict(final_statuses_override)
    return final_util, statuses


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Apply Trace Run-End Outcome Cutover",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        f"- scenarios checked: `{len(payload['scenario_results'])}`",
        f"- mismatches: `{len(payload['mismatches'])}`",
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
    helper = _function_window(source, "_emit_design_guide_apply_trace_run_end")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    scenarios = [
        {
            "name": "overview_util_and_statuses",
            "overview": {"worst_util": 0.91, "statuses": {"bending": "PASS"}},
            "util_override": None,
            "statuses_override": {"shear": "FAIL"},
        },
        {
            "name": "util_override_wins",
            "overview": {"worst_util": 0.91, "statuses": {"bending": "PASS"}},
            "util_override": "0.77",
            "statuses_override": {},
        },
        {
            "name": "bad_util_override_ignored",
            "overview": {"worst_util": 0.91, "statuses": {"bending": "PASS"}},
            "util_override": "not-a-number",
            "statuses_override": {},
        },
        {
            "name": "empty_overview_statuses_use_override",
            "overview": {"worst_util": None, "statuses": {}},
            "util_override": None,
            "statuses_override": {"shear": "PASS"},
        },
        {
            "name": "missing_overview_defaults",
            "overview": {},
            "util_override": None,
            "statuses_override": {},
        },
    ]
    scenario_results = []
    mismatches = []
    for row in scenarios:
        old_util, old_statuses = _old_outcome(
            current_overview=row["overview"],
            final_util_override=row["util_override"],
            final_statuses_override=row["statuses_override"],
        )
        new = build_inputs_design_guide_apply_trace_run_end_outcome(
            current_overview=row["overview"],
            final_util_override=row["util_override"],
            final_statuses_override=row["statuses_override"],
        )
        match = old_util == new.final_util and old_statuses == dict(new.statuses) and bool(new.display_hash)
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old_final_util": old_util,
                "new_final_util": new.final_util,
                "old_statuses": old_statuses,
                "new_statuses": dict(new.statuses),
                "display_hash_present": bool(new.display_hash),
            }
        )
        if not match:
            mismatches.append(
                {
                    "scenario": row["name"],
                    "old_final_util": old_util,
                    "new_final_util": new.final_util,
                    "old_statuses": old_statuses,
                    "new_statuses": dict(new.statuses),
                }
            )

    checks = {
        "helper_delegates_to_session_builder": "build_inputs_design_guide_apply_trace_run_end_outcome(" in helper,
        "helper_keeps_state_collection": "_shared_state_snapshot()" in helper
        and "_collect_design_overview(" in helper,
        "helper_keeps_acceptance_fingerprint_write": "_design_guide_post_cleanup_acceptance_fp" in helper,
        "helper_keeps_trace_append": "_append_design_guide_trace(" in helper,
        "old_inline_final_util_resolution_removed": "final_util = current_overview.get(\"worst_util\") if isinstance(current_overview, dict) else None" not in helper,
        "old_inline_statuses_resolution_removed": "statuses = dict((current_overview or {}).get(\"statuses\") or {})" not in helper,
        "session_builder_exists": "def build_inputs_design_guide_apply_trace_run_end_outcome(" in builders,
        "session_model_exists": "class InputsDesignGuideApplyTraceRunEndOutcome" in models,
        "session_init_exports_builder": "build_inputs_design_guide_apply_trace_run_end_outcome" in init_source,
        "session_init_exports_model": "InputsDesignGuideApplyTraceRunEndOutcome" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_APPLY_TRACE_RUN_END_OUTCOME_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_APPLY_TRACE_RUN_END_OUTCOME_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_apply_trace_run_end_outcome_cutover",
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
        "state_collection_moved": False,
        "overview_collection_moved": False,
        "trace_append_moved": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_apply_trace_run_end_outcome_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_apply_trace_run_end_outcome_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_guide_apply_trace_run_end_outcome_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
