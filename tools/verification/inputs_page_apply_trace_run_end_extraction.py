from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.design_guide import apply_trace_run_end as extracted
from inputs_page_modules.session import (
    build_inputs_design_guide_apply_trace_run_end_meta_plan,
    build_inputs_design_guide_apply_trace_run_end_outcome,
)


BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "apply_trace_run_end.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


class FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, Any] = {}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def _run_extracted_scenario() -> dict[str, Any]:
    fake_st = FakeStreamlit()
    fake_st.session_state["_design_guide_apply_trace_run_id"] = "run_existing"
    fake_st.session_state["_design_guide_apply_trace_meta"] = {
        "source": "design_guide_apply",
        "action_type": "apply_update",
        "title": "Apply update",
        "starting_worst_util": 0.91,
    }
    fake_st.session_state["primary_binding"] = {"candidate_id": "cand-1"}
    fake_st.session_state["last_route"] = {"route": "apply"}
    accepted_fps: set[str] = set()
    appended: list[dict[str, Any]] = []

    def _shared_state_snapshot() -> dict[str, Any]:
        return {"base": True, "d": 500}

    def _context(state: dict[str, Any]) -> dict[str, Any]:
        return {"state": dict(state)}

    def _overview(state: dict[str, Any], *, context: dict[str, Any]) -> dict[str, Any]:
        current = dict(context.get("state") or state)
        return {
            "worst_util": 0.72 if current.get("trace") else 0.84,
            "statuses": {"bending": "PASS", "shear": "PASS"},
            "all_key_pass": True,
            "any_fail": False,
        }

    def _guidance_state_snapshot(state: dict[str, Any]) -> dict[str, Any]:
        out = dict(state)
        out["trace"] = True
        return out

    def _identity_state(state: dict[str, Any]) -> dict[str, Any]:
        return dict(state)

    def _append(event: str, data: dict, *, run_id: str, source: str) -> None:
        appended.append(
            {
                "event": event,
                "data": dict(data),
                "run_id": run_id,
                "source": source,
            }
        )

    extracted.bind_apply_trace_run_end_dependencies(
        {
            "DESIGN_GUIDE_APPLY_TRACE_META_KEY": "_design_guide_apply_trace_meta",
            "DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY": "_design_guide_apply_trace_run_id",
            "DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY": "last_route",
            "DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS": accepted_fps,
            "DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY": "primary_binding",
            "_append_design_guide_trace": _append,
            "_build_design_actions_context_for_app_bridge": _context,
            "_collect_design_overview": _overview,
            "_design_guide_trace_compare_meta": lambda **kwargs: dict(kwargs),
            "_guidance_state_snapshot": _guidance_state_snapshot,
            "_local_cleanup_acceptance_fingerprint": lambda state: f"fp:{state.get('d')}:{state.get('trace')}",
            "_new_design_guide_trace_run_id": lambda prefix: f"{prefix}_1",
            "_overlay_current_normalized_shear_truth_for_app_bridge": _identity_state,
            "_recompute_summary_local_derived_fields_for_app_bridge": _identity_state,
            "_shared_state_snapshot": _shared_state_snapshot,
            "_trace_compact_overview_dict": lambda overview: {"worst_util": overview.get("worst_util")},
            "_trace_compact_shared_geom_reo": lambda state: {"d": state.get("d"), "trace": state.get("trace")},
            "build_inputs_design_guide_apply_trace_run_end_meta_plan": (
                build_inputs_design_guide_apply_trace_run_end_meta_plan
            ),
            "build_inputs_design_guide_apply_trace_run_end_outcome": (
                build_inputs_design_guide_apply_trace_run_end_outcome
            ),
            "build_legacy_longitudinal_mirrors_from_rows": lambda state: {"mirror": True},
            "st": fake_st,
        }
    )
    extracted._emit_design_guide_apply_trace_run_end(
        stop_reason="applied",
        final_updates={"d": 525},
        winner_label="Winner",
    )
    row = appended[0] if appended else {}
    data = dict(row.get("data") or {})
    return {
        "trace_appended": len(appended) == 1,
        "event": row.get("event"),
        "run_id": row.get("run_id"),
        "source": row.get("source"),
        "session_trace_keys_removed": "_design_guide_apply_trace_run_id" not in fake_st.session_state
        and "_design_guide_apply_trace_meta" not in fake_st.session_state,
        "accepted_fp_written": bool(accepted_fps)
        and bool(fake_st.session_state.get("_design_guide_post_cleanup_acceptance_enabled")),
        "status": data.get("status"),
        "stop_reason": data.get("stop_reason"),
        "final_live_worst_util": data.get("final_live_worst_util"),
        "all_key_pass": data.get("all_key_pass"),
        "primary_payload_binding_audit": data.get("primary_payload_binding_audit"),
        "last_apply_route": data.get("last_apply_route"),
        "compare": data.get("compare"),
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Page Apply Trace Run-End Extraction",
        "",
        f"## Decision: {payload['decision']}",
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
    bridge_source = _read(BRIDGE)
    module_source = _read(MODULE)
    bridge_helper = _function_source(bridge_source, "_emit_design_guide_apply_trace_run_end")
    module_helper = _function_source(module_source, "_emit_design_guide_apply_trace_run_end")
    scenario = _run_extracted_scenario()
    checks = {
        "module_exists": MODULE.exists(),
        "bridge_imports_extracted_helper": "_emit_design_guide_apply_trace_run_end_extracted" in bridge_source,
        "bridge_helper_is_thin_delegate": len(bridge_helper.splitlines()) <= 18,
        "bridge_binds_module_dependencies": "_bind_apply_trace_run_end_dependencies(globals())" in bridge_helper,
        "bridge_delegates_to_extracted": "_emit_design_guide_apply_trace_run_end_extracted(" in bridge_helper,
        "bridge_removed_session_pop_body": "st.session_state.pop(DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY" not in bridge_helper,
        "module_keeps_session_pop_body": "st.session_state.pop(DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY" in module_helper,
        "module_keeps_trace_append": "_append_design_guide_trace(" in module_helper,
        "module_uses_session_builders": "build_inputs_design_guide_apply_trace_run_end_meta_plan(" in module_helper
        and "build_inputs_design_guide_apply_trace_run_end_outcome(" in module_helper,
        "scenario_trace_appended": scenario["trace_appended"],
        "scenario_run_id_preserved": scenario["run_id"] == "run_existing",
        "scenario_trace_source_preserved": scenario["source"] == "design_guide_apply",
        "scenario_session_trace_keys_removed": scenario["session_trace_keys_removed"],
        "scenario_acceptance_state_written": scenario["accepted_fp_written"],
        "scenario_status_pass": scenario["status"] == "pass",
        "scenario_final_trace_overview_used": scenario["final_live_worst_util"] == 0.72,
        "scenario_primary_payload_binding_audit_preserved": scenario["primary_payload_binding_audit"]
        == {"candidate_id": "cand-1"},
        "scenario_last_apply_route_preserved": scenario["last_apply_route"] == {"route": "apply"},
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "INPUTS_PAGE_APPLY_TRACE_RUN_END_EXTRACTION_LOCKED" if not failures else "GAPS_REMAIN"
    payload = {
        "audit": "inputs_page_apply_trace_run_end_extraction",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "scenario": scenario,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_behavior_changed": False,
        "engineering_calculations_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_page_apply_trace_run_end_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_apply_trace_run_end_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_page_apply_trace_run_end_extraction", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
