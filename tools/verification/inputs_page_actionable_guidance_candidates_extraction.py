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

from inputs_page_modules.app_bridge import actionable_guidance_candidates


BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "app_bridge" / "actionable_guidance_candidates.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def _bind(payload: dict[str, Any], trace: list[dict[str, Any]]) -> None:
    def compute_design_guidance_items(state: dict, **kwargs: Any) -> dict:
        trace.append({"kind": "compute_call", "state": dict(state), "kwargs": dict(kwargs)})
        return dict(payload)

    def append_design_guide_trace(event: str, body: dict, *, run_id: str, source: str) -> None:
        trace.append(
            {
                "kind": "trace",
                "event": event,
                "body": dict(body),
                "run_id": run_id,
                "source": source,
            }
        )

    def ensure_resolved_candidate_payload(item: dict, state: dict | None = None) -> None:
        item["resolved_candidate_payload_checked"] = True
        item["state_seen"] = dict(state or {})

    def guidance_action_updates(action_type: str, payload: dict, *, state: dict | None = None) -> dict | None:
        if payload.get("raise"):
            raise RuntimeError("intentional resolver failure")
        if payload.get("direct_update"):
            return dict(payload["direct_update"])
        if payload.get("fallback_update"):
            return dict(payload["fallback_update"])
        return None

    actionable_guidance_candidates.bind_actionable_guidance_candidate_dependencies(
        {
            "_append_design_guide_trace": append_design_guide_trace,
            "_compute_design_guidance_items": compute_design_guidance_items,
            "_ensure_guidance_item_resolved_candidate_payload": ensure_resolved_candidate_payload,
            "_guidance_action_updates": guidance_action_updates,
            "_updates_match_state": lambda state, updates: all(state.get(k) == v for k, v in dict(updates).items()),
            "_resolve_geometry_width_context": lambda state: ("bf" if "bf" in state else "b", None, state.get("bf", state.get("b"))),
            "_float_from_state": lambda state, key, default=0.0: float(state.get(key, default) or default),
            "_design_width_value": lambda state: float(state.get("bf", state.get("b", 0.0)) or 0.0),
            "TARGET_BAND_ACTIONABLE_GEO_DELTA_MM": 1.0,
            "TARGET_BAND_ACTIONABLE_AST_DELTA_MM2": 10.0,
        }
    )


def _case_results() -> list[dict[str, Any]]:
    raw_direct = {
        "action_type": "increase_depth",
        "title_main": "Increase depth",
        "action_payload": {"direct_update": {"D": 650}},
    }
    raw_fallback = {
        "action_type": "increase_width",
        "canonical_winner_label": "Increase width",
        "action_payload": {"raise": True},
        "fallback_update": {"b": 350},
    }
    raw_skip = {
        "action_type": "noop",
        "title_main": "No-op",
        "action_payload": {},
    }
    payload = {
        "guidance_items": [
            raw_direct,
            raw_fallback,
            raw_skip,
            {"title_main": "Missing action"},
            "not a dict",
        ],
        "debug_trace": {
            "guidance_branch": "test_branch",
            "selected_action_type": "increase_depth",
            "selected_title": "Increase depth",
            "one_click_convergence_available": True,
            "one_click_convergence_reason": "test",
            "actionable_target_band_winner_exists": True,
        },
    }
    trace: list[dict[str, Any]] = []
    _bind(payload, trace)
    candidates, raw_count = actionable_guidance_candidates._one_click_collect_actionable_guidance_candidates(
        {"D": 600, "b": 300},
        debug_enabled=True,
        trace_run_id="run-1",
        trace_step=4,
    )
    return [
        {
            "name": "collects_direct_and_fallback_candidates_only",
            "passed": raw_count == 5
            and [row["action_type"] for row in candidates] == ["increase_depth", "increase_width"]
            and candidates[0]["raw_updates"] == {"D": 650}
            and candidates[1]["raw_updates"] == {"b": 350}
            and candidates[1]["title"] == "Increase width",
            "result": {"candidates": candidates, "raw_count": raw_count},
        },
        {
            "name": "trace_records_guidance_pool_metadata",
            "passed": any(
                row.get("kind") == "trace"
                and row.get("event") == "guidance_pool"
                and row.get("source") == "one_click_guidance"
                and row.get("body", {}).get("step") == 4
                and row.get("body", {}).get("raw_guidance_item_count") == 5
                and row.get("body", {}).get("selected_action_type") == "increase_depth"
                for row in trace
            ),
            "trace": trace,
        },
        {
            "name": "source_items_are_deepcopied_before_payload_enrichment",
            "passed": "resolved_candidate_payload_checked" not in raw_direct
            and candidates[0]["item"]["resolved_candidate_payload_checked"] is True
            and candidates[0]["item"]["state_seen"] == {"D": 600, "b": 300},
            "source_item": raw_direct,
            "candidate_item": candidates[0]["item"],
        },
    ]


def _materiality_cases() -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    _bind({"guidance_items": []}, trace)
    base = {"b": 300.0, "bf": 500.0, "D": 600.0, "s_lig": 200.0}
    cases = {
        "change_lines": actionable_guidance_candidates._candidate_is_materially_actionable(
            base,
            {},
            guidance_change_lines=["Increase depth"],
        ),
        "empty": actionable_guidance_candidates._candidate_is_materially_actionable(base, {}),
        "same_state": actionable_guidance_candidates._candidate_is_materially_actionable(base, {"D": 600.0}),
        "delta_b": actionable_guidance_candidates._candidate_is_materially_actionable(base, {"_probe": 1}, delta_b_mm=2.0),
        "delta_ast": actionable_guidance_candidates._candidate_is_materially_actionable(base, {"_probe": 1}, delta_Ast_bot=20.0),
        "material_key": actionable_guidance_candidates._candidate_is_materially_actionable(base, {"s_lig": 250.0}),
        "width_key": actionable_guidance_candidates._candidate_is_materially_actionable(base, {"bf": 503.0}),
        "depth_key": actionable_guidance_candidates._candidate_is_materially_actionable(base, {"D": 604.0}),
        "b_when_width_key_not_b": actionable_guidance_candidates._candidate_is_materially_actionable(base, {"b": 303.0}),
        "small_depth": actionable_guidance_candidates._candidate_is_materially_actionable(base, {"D": 600.5}),
    }
    return [
        {"name": "change_lines_are_actionable", "passed": cases["change_lines"] is True, "result": cases},
        {"name": "empty_or_same_updates_not_actionable", "passed": cases["empty"] is False and cases["same_state"] is False, "result": cases},
        {"name": "explicit_deltas_are_actionable", "passed": cases["delta_b"] is True and cases["delta_ast"] is True, "result": cases},
        {"name": "material_reinforcement_key_actionable", "passed": cases["material_key"] is True, "result": cases},
        {"name": "geometry_deltas_obey_threshold", "passed": cases["width_key"] is True and cases["depth_key"] is True and cases["small_depth"] is False, "result": cases},
        {"name": "fallback_b_width_delta_actionable", "passed": cases["b_when_width_key_not_b"] is True, "result": cases},
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Page Actionable Guidance Candidates Extraction",
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
    bridge_helper = _function_source(bridge_source, "_one_click_collect_actionable_guidance_candidates")
    bridge_materiality_helper = _function_source(bridge_source, "_candidate_is_materially_actionable")
    module_helper = _function_source(module_source, "_one_click_collect_actionable_guidance_candidates")
    module_materiality_helper = _function_source(module_source, "_candidate_is_materially_actionable")
    cases = _case_results()
    materiality_cases = _materiality_cases()
    checks = {
        "module_exists": MODULE.exists(),
        "bridge_imports_extracted_helper": "_one_click_collect_actionable_guidance_candidates_extracted" in bridge_source,
        "bridge_imports_materiality_helper": "_candidate_is_materially_actionable_extracted" in bridge_source,
        "bridge_helper_is_thin_delegate": len(bridge_helper.splitlines()) <= 14,
        "bridge_binds_actionable_candidate_dependencies": "_bind_actionable_guidance_candidate_dependencies(globals())" in bridge_helper,
        "bridge_delegates_to_extracted": "_one_click_collect_actionable_guidance_candidates_extracted(" in bridge_helper,
        "bridge_materiality_helper_is_thin_delegate": len(bridge_materiality_helper.splitlines()) <= 18,
        "bridge_materiality_binds_dependencies": "_bind_actionable_guidance_candidate_dependencies(globals())" in bridge_materiality_helper,
        "bridge_materiality_delegates_to_extracted": "_candidate_is_materially_actionable_extracted(" in bridge_materiality_helper,
        "bridge_removed_candidate_collection_body": "guidance_pool" not in bridge_helper
        and "raw_guidance_item_count" not in bridge_helper,
        "bridge_removed_materiality_body": "TARGET_BAND_ACTIONABLE_GEO_DELTA_MM" not in bridge_materiality_helper
        and "material_keys" not in bridge_materiality_helper,
        "module_keeps_candidate_collection_body": "guidance_pool" in module_helper
        and "raw_guidance_item_count" in module_helper,
        "module_keeps_materiality_body": "TARGET_BAND_ACTIONABLE_GEO_DELTA_MM" in module_materiality_helper
        and "material_keys" in module_materiality_helper,
        "all_cases_pass": all(row["passed"] for row in cases),
        "all_materiality_cases_pass": all(row["passed"] for row in materiality_cases),
    }
    failures = [key for key, value in checks.items() if not value]
    failures.extend(f"case:{row['name']}" for row in cases if not row["passed"])
    failures.extend(f"materiality_case:{row['name']}" for row in materiality_cases if not row["passed"])
    decision = (
        "INPUTS_PAGE_ACTIONABLE_GUIDANCE_CANDIDATES_EXTRACTION_LOCKED"
        if not failures
        else "GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_page_actionable_guidance_candidates_extraction",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "case_results": cases,
        "materiality_case_results": materiality_cases,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_behavior_changed": False,
        "engineering_calculations_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_page_actionable_guidance_candidates_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_actionable_guidance_candidates_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_page_actionable_guidance_candidates_extraction", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
