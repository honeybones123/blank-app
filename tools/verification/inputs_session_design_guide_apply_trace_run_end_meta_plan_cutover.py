from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_apply_trace_run_end_meta_plan


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


def _old_meta_plan(
    *,
    run_id: Any,
    meta: Mapping[str, Any] | None,
    recovered_run_id: Any,
    winner_label: Any,
) -> tuple[str, dict[str, Any], bool]:
    final_run_id = run_id
    meta_d = dict(meta or {})
    recovered = not bool(final_run_id)
    if recovered:
        final_run_id = recovered_run_id
        meta_d.setdefault("source", "design_guide_apply_trace_recovered")
        meta_d.setdefault("action_type", "apply_recommendation")
        meta_d.setdefault("title", winner_label or "Apply recommendation")
        meta_d.setdefault("starting_worst_util", None)
    return str(final_run_id or ""), meta_d, recovered


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Apply Trace Run-End Meta Plan Cutover",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        f"- scenarios checked: `{len(payload['scenario_results'])}`",
        f"- mismatches: `{len(payload['mismatches'])}`",
        f"- session reads moved: `{payload['session_reads_moved']}`",
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
    helper = _function_window(source, "_emit_design_guide_apply_trace_run_end")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    scenarios = [
        {
            "name": "existing_run_preserves_meta",
            "run_id": "dgapply_existing",
            "meta": {
                "source": "design_guide_apply",
                "action_type": "custom_action",
                "title": "Custom",
                "starting_worst_util": 0.8,
            },
            "recovered_run_id": "dgapply_recovered_1",
            "winner_label": "Winner",
        },
        {
            "name": "missing_run_uses_recovery_defaults",
            "run_id": None,
            "meta": {},
            "recovered_run_id": "dgapply_recovered_1",
            "winner_label": "Winner",
        },
        {
            "name": "missing_run_preserves_existing_meta_fields",
            "run_id": "",
            "meta": {
                "source": "existing_source",
                "action_type": "existing_action",
                "title": "Existing title",
                "starting_worst_util": 0.5,
            },
            "recovered_run_id": "dgapply_recovered_2",
            "winner_label": "Winner",
        },
        {
            "name": "missing_run_default_title_without_winner",
            "run_id": None,
            "meta": {},
            "recovered_run_id": "dgapply_recovered_3",
            "winner_label": None,
        },
    ]
    scenario_results = []
    mismatches = []
    for row in scenarios:
        old_run_id, old_meta, old_recovered = _old_meta_plan(
            run_id=row["run_id"],
            meta=row["meta"],
            recovered_run_id=row["recovered_run_id"],
            winner_label=row["winner_label"],
        )
        new = build_inputs_design_guide_apply_trace_run_end_meta_plan(
            run_id=row["run_id"],
            meta=row["meta"],
            recovered_run_id=row["recovered_run_id"],
            winner_label=row["winner_label"],
        )
        match = (
            old_run_id == new.run_id
            and old_meta == dict(new.meta)
            and bool(old_recovered) == bool(new.recovered)
            and bool(new.display_hash)
        )
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old_run_id": old_run_id,
                "new_run_id": new.run_id,
                "old_meta": old_meta,
                "new_meta": dict(new.meta),
                "old_recovered": bool(old_recovered),
                "new_recovered": bool(new.recovered),
                "display_hash_present": bool(new.display_hash),
            }
        )
        if not match:
            mismatches.append(
                {
                    "scenario": row["name"],
                    "old_run_id": old_run_id,
                    "new_run_id": new.run_id,
                    "old_meta": old_meta,
                    "new_meta": dict(new.meta),
                }
            )

    checks = {
        "helper_delegates_to_session_builder": "build_inputs_design_guide_apply_trace_run_end_meta_plan(" in helper,
        "helper_keeps_session_pops": "st.session_state.pop(DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY" in helper
        and "st.session_state.pop(DESIGN_GUIDE_APPLY_TRACE_META_KEY" in helper,
        "helper_keeps_recovered_run_id_generation": "_new_design_guide_trace_run_id(\"dgapply_recovered\")" in helper,
        "helper_keeps_state_collection": "_shared_state_snapshot()" in helper
        and "_collect_design_overview(" in helper,
        "helper_keeps_trace_append": "_append_design_guide_trace(" in helper,
        "old_inline_meta_dict_removed": "meta_d = dict(meta or {})" not in helper,
        "old_inline_recovery_setdefaults_removed": "meta_d.setdefault(\"source\", \"design_guide_apply_trace_recovered\")" not in helper
        and "meta_d.setdefault(\"action_type\", \"apply_recommendation\")" not in helper,
        "session_builder_exists": "def build_inputs_design_guide_apply_trace_run_end_meta_plan(" in builders,
        "session_model_exists": "class InputsDesignGuideApplyTraceRunEndMetaPlan" in models,
        "session_init_exports_builder": "build_inputs_design_guide_apply_trace_run_end_meta_plan" in init_source,
        "session_init_exports_model": "InputsDesignGuideApplyTraceRunEndMetaPlan" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_APPLY_TRACE_RUN_END_META_PLAN_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_APPLY_TRACE_RUN_END_META_PLAN_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_apply_trace_run_end_meta_plan_cutover",
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
        "run_id_generation_moved": False,
        "state_collection_moved": False,
        "overview_collection_moved": False,
        "trace_append_moved": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_apply_trace_run_end_meta_plan_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_apply_trace_run_end_meta_plan_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_guide_apply_trace_run_end_meta_plan_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
