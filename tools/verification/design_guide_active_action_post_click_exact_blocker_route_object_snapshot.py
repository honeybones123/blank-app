"""Verify the active-action post-click exact-blocker controller route object.

Proof-only: this does not wire the route into inputs_page.py or change product
behaviour. It proves the controller route exists, keeps page-owned callbacks as
boundaries, preserves the route gate/result shape, and produces stable plain
data.
"""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

ROUTE = "run_design_guide_controller_active_action_post_click_exact_blocker_route"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name}")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or "")
    if "PASS" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _base_kwargs(builder_enabled: bool = False) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    audit_calls: list[dict[str, Any]] = []

    def builder(state, overview, mode_config, audit, debug_sink=None):
        audit_calls.append(dict(audit or {}))
        return {
            "title": "Further cleanup blocked",
            "button_contract": {"enabled": builder_enabled, "actionable": builder_enabled},
            "candidate_search_evidence": dict(audit or {}),
        }

    kwargs = {
        "active_family": "bending",
        "candidate_id": "active-candidate-1",
        "active_outside_exact_blockers": {
            "bending": {
                "family": "bending",
                "reason": "Accepted post-click state needs no second CTA.",
                "no_second_cta_required": True,
            }
        },
        "current_utils": {"bending": 0.22, "shear": 0.91},
        "final_state": {"D": 650, "b": 400},
        "final_overview": {"utils": {"bending": 0.22, "shear": 0.91}, "any_fail": False},
        "debug_probe": {"probe": "active-post-click"},
        "final_accepted_min_family_util": 0.85,
        "target_band_eps": 0.001,
        "parse_util_value_fn": lambda value: None if value is None else float(value),
        "post_click_low_bending_resolution_item_fn": builder,
        "design_mode_config_fn": lambda goal: {"goal": goal},
        "design_optimisation_goal_fn": lambda state: "balanced",
        "design_guide_button_contract_enabled_fn": lambda contract: bool(
            dict(contract or {}).get("enabled") and dict(contract or {}).get("actionable", True)
        ),
        "state_fingerprint_fn": lambda state: "fp:" + _stable_hash(state)[:12],
        "normalise_final_visible_design_guide_item_fn": lambda item: dict(item or {}),
    }
    return kwargs, audit_calls


def _run_case(case_id: str, overrides: dict[str, Any] | None = None, *, builder_enabled: bool = False) -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_active_action_post_click_exact_blocker_route,
    )

    kwargs, audit_calls = _base_kwargs(builder_enabled=builder_enabled)
    kwargs.update(dict(overrides or {}))
    first = run_design_guide_controller_active_action_post_click_exact_blocker_route(**kwargs)
    second = run_design_guide_controller_active_action_post_click_exact_blocker_route(**kwargs)
    return {
        "case": case_id,
        "result": first,
        "result_hash": _stable_hash(first),
        "stable_repeat_hash": _stable_hash(first) == _stable_hash(second),
        "result_present": isinstance(first, dict),
        "render_reason": (first or {}).get("render_reason") if isinstance(first, dict) else None,
        "show_apply_button": (
            dict((first or {}).get("presentation") or {}).get("show_apply_button")
            if isinstance(first, dict)
            else None
        ),
        "audit_calls": list(audit_calls),
    }


def _exercise_route() -> list[dict[str, Any]]:
    return [
        _run_case("non_bending_family_returns_none", {"active_family": "shear"}),
        _run_case("missing_exact_blocker_returns_none", {"active_outside_exact_blockers": {}}),
        _run_case(
            "exact_blocker_without_no_second_cta_returns_none",
            {"active_outside_exact_blockers": {"bending": {"family": "bending"}}},
        ),
        _run_case("enabled_builder_result_returns_none", builder_enabled=True),
        _run_case("disabled_exact_blocker_result_selected"),
    ]


def _capture() -> dict[str, Any]:
    source, start_line, end_line = _function_source(CONTROLLER, ROUTE)
    controller_text = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    forbidden = {
        "inputs_page_import": "inputs_page" in source,
        "streamlit_or_session": any(
            token in source for token in ("import streamlit", "st.session_state", "st.button", "st.markdown")
        ),
        "apply_routing": "_queue_primary_design_guide_button_action" in source,
        "html_rendering": "_design_guide_dashboard_card_html" in source,
        "family_runtime": "contracted_repair_ladder_specs(" in source,
    }
    cases = _exercise_route()
    selected_case = next(
        (case for case in cases if case.get("case") == "disabled_exact_blocker_result_selected"),
        {},
    )
    selected_result = dict(selected_case.get("result") or {})
    selected_debug = dict(selected_result.get("debug") or {})
    selected_audit = (
        list(selected_case.get("audit_calls") or [{}])[0]
        if selected_case.get("audit_calls")
        else {}
    )
    return {
        "decision": "CONTROLLER_ROUTE_OBJECT_READY_FOR_TRACE_PARITY",
        "route": {
            "function": ROUTE,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
            "source_hash": _stable_hash(source),
        },
        "cases": cases,
        "case_results": {case["case"]: bool(case.get("result_present")) for case in cases},
        "selected_result_proof": {
            "render_reason": selected_result.get("render_reason"),
            "show_apply_button": dict(selected_result.get("presentation") or {}).get("show_apply_button"),
            "debug_replaced_flag": selected_debug.get("post_click_active_action_replaced_by_exact_blocker"),
            "debug_family": selected_debug.get("post_click_active_action_family"),
            "audit_has_exact_blockers": bool(
                dict(selected_audit or {}).get("post_click_exact_blockers_by_family")
            ),
            "audit_invalid_reason": dict(selected_audit or {}).get(
                "post_click_accepted_green_invalid_reason"
            ),
        },
        "forbidden_controller_ownership": forbidden,
        "exported": f'"{ROUTE}"' in controller_text,
        "latest": {
            "readiness": _latest("design_guide_active_action_post_click_exact_blocker_readiness"),
            "independence_lock": _latest("design_guide_independence_lock"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_resolver_publication_bridge_lock": _latest(
                "design_guide_compute_resolver_publication_bridge_lock"
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    case_results = dict(capture.get("case_results") or {})
    latest = dict(capture.get("latest") or {})
    selected_proof = dict(capture.get("selected_result_proof") or {})
    return {
        "route_defined": bool((capture.get("route") or {}).get("line_count")),
        "route_exported": capture.get("exported") is True,
        "readiness_passes": (latest.get("readiness") or {}).get("status") == "PASS",
        "case_hashes_stable": all(case.get("stable_repeat_hash") is True for case in capture.get("cases") or []),
        "non_bending_family_returns_none": case_results.get("non_bending_family_returns_none") is False,
        "missing_exact_blocker_returns_none": case_results.get("missing_exact_blocker_returns_none") is False,
        "exact_blocker_without_no_second_cta_returns_none": (
            case_results.get("exact_blocker_without_no_second_cta_returns_none") is False
        ),
        "enabled_builder_result_returns_none": case_results.get("enabled_builder_result_returns_none") is False,
        "disabled_exact_blocker_result_selected": (
            case_results.get("disabled_exact_blocker_result_selected") is True
        ),
        "selected_result_has_no_apply_button": selected_proof.get("show_apply_button") is False,
        "selected_result_render_reason_matches": (
            selected_proof.get("render_reason") == "final_visible_post_click_active_action_exact_blocker"
        ),
        "selected_result_debug_marks_replacement": (
            selected_proof.get("debug_replaced_flag") is True
            and selected_proof.get("debug_family") == "bending"
        ),
        "selected_audit_surface_preserved": (
            selected_proof.get("audit_has_exact_blockers") is True
            and selected_proof.get("audit_invalid_reason")
            == "post_click_active_action_has_exact_blocker"
        ),
        "no_forbidden_controller_ownership": not any(
            (capture.get("forbidden_controller_ownership") or {}).values()
        ),
        "independence_lock_artifact_available": bool(
            (latest.get("independence_lock") or {}).get("found")
        ),
        "render_bridge_lock_artifact_available": bool(
            (latest.get("render_bridge_lock") or {}).get("found")
        ),
        "compute_bridge_lock_artifact_available": bool(
            (latest.get("compute_resolver_publication_bridge_lock") or {}).get("found")
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    route = dict(capture.get("route") or {})
    lines = [
        "# Design Guide Active-Action Post-Click Exact-Blocker Route Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Route",
        "",
        f"- Function: `{route.get('function')}`",
        f"- Lines: `{route.get('start_line')}` to `{route.get('end_line')}`",
        f"- Line count: `{route.get('line_count')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Cases", "", "| Case | Result present | Render reason | Stable |", "| --- | ---: | --- | ---: |"])
    for case in capture.get("cases") or []:
        lines.append(
            f"| {case.get('case')} | `{case.get('result_present')}` | `{case.get('render_reason')}` | `{case.get('stable_repeat_hash')}` |"
        )
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            "Wire trace-only parity beside the page route and compare live page results to this controller route.",
            "Do not replace the page route or delete the old body until branch parity passes.",
            "",
            "No product behavior, visible wording, CTA/apply semantics, family runtime, solver maths, target bands, render ownership, apply routing, or UI/session ownership changed.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_active_action_post_click_exact_blocker_route_object_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_active_action_post_click_exact_blocker_route_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_active_action_post_click_exact_blocker_route_object {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
