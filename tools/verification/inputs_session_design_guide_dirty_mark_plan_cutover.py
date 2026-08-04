from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_dirty_mark_plan


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


def _write_report(payload: dict, report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Dirty Mark Plan Cutover",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        f"- scenarios checked: `{len(payload['scenario_results'])}`",
        f"- mismatches: `{len(payload['mismatches'])}`",
        f"- session writes moved: `{payload['session_writes_moved']}`",
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
    helper = _function_window(source, "_mark_design_guide_dirty")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    scenarios = [
        {
            "name": "current_dirty_defaults",
            "refresh_key": "design_guide_needs_refresh",
            "clear_history": False,
            "preserve_apply_banner": False,
        },
        {
            "name": "explicit_history_clear",
            "refresh_key": "custom_refresh",
            "clear_history": True,
            "preserve_apply_banner": False,
        },
        {
            "name": "preserve_apply_banner",
            "refresh_key": "custom_refresh",
            "clear_history": False,
            "preserve_apply_banner": True,
        },
    ]
    scenario_results = []
    mismatches = []
    for row in scenarios:
        plan = build_inputs_design_guide_dirty_mark_plan(
            refresh_key=row["refresh_key"],
            clear_history=row["clear_history"],
            preserve_apply_banner=row["preserve_apply_banner"],
        )
        expected = {
            "refresh_key": str(row["refresh_key"]),
            "refresh_value": True,
            "clear_history": bool(row["clear_history"]),
            "preserve_apply_banner": bool(row["preserve_apply_banner"]),
        }
        actual = {
            "refresh_key": plan.refresh_key,
            "refresh_value": plan.refresh_value,
            "clear_history": plan.clear_history,
            "preserve_apply_banner": plan.preserve_apply_banner,
        }
        match = expected == actual and bool(plan.display_hash)
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "expected": expected,
                "actual": actual,
                "display_hash_present": bool(plan.display_hash),
            }
        )
        if not match:
            mismatches.append({"scenario": row["name"], "expected": expected, "actual": actual})

    checks = {
        "helper_delegates_to_session_builder": "build_inputs_design_guide_dirty_mark_plan(" in helper,
        "helper_keeps_session_write": "st.session_state[dirty_plan.refresh_key] = dirty_plan.refresh_value" in helper,
        "helper_keeps_transient_clear_call": "_clear_design_guide_transient_ui_state(" in helper,
        "old_inline_refresh_assignment_removed": "st.session_state[DESIGN_GUIDE_NEEDS_REFRESH_KEY] = True" not in helper,
        "old_inline_clear_args_removed": "_clear_design_guide_transient_ui_state(clear_history=False, preserve_apply_banner=False)" not in helper,
        "session_builder_exists": "def build_inputs_design_guide_dirty_mark_plan(" in builders,
        "session_model_exists": "class InputsDesignGuideDirtyMarkPlan" in models,
        "session_init_exports_builder": "build_inputs_design_guide_dirty_mark_plan" in init_source,
        "session_init_exports_model": "InputsDesignGuideDirtyMarkPlan" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_DIRTY_MARK_PLAN_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_DIRTY_MARK_PLAN_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_dirty_mark_plan_cutover",
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
        "clear_call_moved": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_dirty_mark_plan_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_dirty_mark_plan_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_guide_dirty_mark_plan_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
