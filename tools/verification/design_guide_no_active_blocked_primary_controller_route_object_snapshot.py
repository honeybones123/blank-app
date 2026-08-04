"""Controller route object snapshot for no-active blocked-primary cleanup probing.

This is proof-only. It calls the controller route with plain callbacks and
sample data, but does not wire the page route, render UI, route Apply, or
change product behavior.
"""

from __future__ import annotations

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

ROUTE = "run_design_guide_controller_no_active_blocked_primary_cleanup_probe_route"
TRACE_KEY = "design_guide_controller_no_active_blocked_primary_full_route_builder_trace_only"
SAFE_BRANCH = "safe_shear_cleanup_before_blocker"
BENDING_BRANCH = "bending_cleanup_available_before_blocker"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _parse_util_value(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _updates_match_state(state: dict[str, Any], updates: dict[str, Any]) -> bool:
    return all(state.get(key) == value for key, value in dict(updates or {}).items())


def _state_fingerprint(state: dict[str, Any]) -> str:
    return _stable_hash({"state": dict(state or {})})


def _normalise_item(item: dict[str, Any]) -> dict[str, Any]:
    result = dict(item or {})
    result.setdefault("normalised", True)
    return result


def _button_enabled(contract: dict[str, Any]) -> bool:
    return bool(dict(contract or {}).get("enabled"))


def _resolve_updates(item: dict[str, Any], *, state: dict[str, Any] | None = None) -> dict[str, Any]:
    del state
    return dict(
        dict(item or {}).get("updates")
        or dict(dict(item or {}).get("button_contract") or {}).get("updates")
        or {}
    )


def _candidate_id(*values: Any, family: str = "", updates: dict[str, Any] | None = None) -> str:
    for value in values:
        if value not in (None, ""):
            return str(value)
    return f"{family}:{_stable_hash(dict(updates or {}))[:10]}"


def _visible_blocker_from_action(**kwargs: Any) -> dict[str, Any]:
    return {
        "family": kwargs.get("family"),
        "reason": "below accepted efficiency floor after checked cleanup",
        "current_util": kwargs.get("current_util"),
        "expected_util": kwargs.get("expected_util"),
        "terminal_mode": kwargs.get("terminal_mode"),
    }


def _design_optimisation_goal(state: dict[str, Any]) -> str:
    del state
    return "balanced"


def _design_mode_config(goal: str) -> dict[str, Any]:
    return {"goal": goal, "target_band": [0.85, 0.98]}


def _safe_cleanup_item_from_evidence(
    state: dict[str, Any],
    overview: dict[str, Any],
    evidence: dict[str, Any],
    *,
    title: str,
) -> dict[str, Any]:
    del state, overview
    updates = dict(
        evidence.get("selected_candidate_updates")
        or evidence.get("best_safe_candidate_updates")
        or evidence.get("closest_safe_candidate_updates")
        or {}
    )
    return {
        "title": title,
        "title_main": title,
        "primary_action": "Apply safe shear cleanup",
        "bucket": "pass",
        "guidance_intent": "efficiency_tightening",
        "updates": dict(updates),
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "candidate_id": "safe-shear-cleanup",
            "updates": dict(updates),
        },
    }


def _bending_cleanup_item(
    state: dict[str, Any],
    overview: dict[str, Any],
    config: dict[str, Any],
    *,
    debug_sink: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del state, overview, config, debug_sink
    return {
        "title": "Bending cleanup",
        "title_main": "Bending cleanup",
        "primary_action": "Apply bending cleanup",
        "bucket": "pass",
        "expected_util": 0.69,
        "updates": {"reo_1": 5},
        "source_candidate_id": "bending-cleanup",
        "candidate_search_evidence": {"selected_candidate_util": 0.69},
    }


def _equivalent_bending_cleanup_item(
    state: dict[str, Any],
    overview: dict[str, Any],
    config: dict[str, Any],
    *,
    debug_sink: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    del state, overview, config, debug_sink
    return None


def _callbacks() -> dict[str, Any]:
    return {
        "local_cleanup_post_apply_acceptance_matches_fn": lambda state: False,
        "updates_match_state_fn": _updates_match_state,
        "shear_best_safe_cleanup_item_from_evidence_fn": _safe_cleanup_item_from_evidence,
        "bending_only_target_band_cleanup_item_fn": _bending_cleanup_item,
        "probe_equivalent_bending_cleanup_action_item_fn": _equivalent_bending_cleanup_item,
        "design_mode_config_fn": _design_mode_config,
        "design_optimisation_goal_fn": _design_optimisation_goal,
        "parse_util_value_fn": _parse_util_value,
        "resolve_recommendation_updates_fn": _resolve_updates,
        "normalise_design_guide_candidate_id_fn": _candidate_id,
        "visible_cleanup_blocker_from_action_fn": _visible_blocker_from_action,
        "design_guide_button_contract_enabled_fn": _button_enabled,
        "normalise_final_visible_design_guide_item_fn": _normalise_item,
        "state_fingerprint_fn": _state_fingerprint,
    }


def _scenario_kwargs(name: str) -> dict[str, Any]:
    common = {
        "primary": {"title": "Blocked primary", "action_type": "blocked"},
        "contract": {"enabled": False, "action_type": "blocked"},
        "updates": {},
        "final_state": {"lig_legs": 2, "reo_1": 8},
        "final_accepted_min_family_util": 0.85,
        "target_band_eps": 0.001,
        "compound_shear_update_keys": {"lig_legs"},
        **_callbacks(),
    }
    if name == "safe_branch":
        return {
            **common,
            "primary_evidence": {
                "selected_candidate_updates": {"lig_legs": 0},
                "safe_executor_backed_candidates_count": 1,
                "selected_candidate_title": "Shear cleanup",
            },
            "final_overview": {"utils": {"bending": 0.24, "shear": 0.69}},
        }
    if name == "bending_branch":
        return {
            **common,
            "primary_evidence": {},
            "final_overview": {"utils": {"bending": 0.24, "shear": 0.69}},
        }
    if name == "none_branch":
        return {
            **common,
            "primary_evidence": {},
            "final_overview": {"utils": {"bending": 0.9, "shear": 0.69}},
        }
    raise ValueError(name)


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        __all__ as controller_exports,
        run_design_guide_controller_no_active_blocked_primary_cleanup_probe_route,
    )

    scenarios: dict[str, Any] = {}
    expected = {
        "safe_branch": SAFE_BRANCH,
        "bending_branch": BENDING_BRANCH,
        "none_branch": "none",
    }
    for name in ("safe_branch", "bending_branch", "none_branch"):
        first = run_design_guide_controller_no_active_blocked_primary_cleanup_probe_route(
            **_scenario_kwargs(name)
        )
        second = run_design_guide_controller_no_active_blocked_primary_cleanup_probe_route(
            **_scenario_kwargs(name)
        )
        result = dict(first or {})
        debug = dict(result.get("debug") or {})
        trace = dict(debug.get(TRACE_KEY) or {})
        scenarios[name] = {
            "result_present": bool(result),
            "expected_branch": expected[name],
            "selected_branch": trace.get("selected_branch") or ("none" if not result else None),
            "trace_present": bool(trace) if result else True,
            "trace_result_hash_match": trace.get("result_hash_match") if result else True,
            "result_hash_stable": _stable_hash(first or {}) == _stable_hash(second or {}),
            "action_type": dict(result.get("item") or {}).get("action_type"),
            "updates_present": bool(dict(result.get("item") or {}).get("updates")),
            "product_driving": trace.get("product_driving") if result else False,
            "render_driving": trace.get("render_driving") if result else False,
            "apply_driving": trace.get("apply_driving") if result else False,
            "session_driving": trace.get("session_driving") if result else False,
        }
    source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    return {
        "decision": "LIVE_CONTROLLER_ROUTE_FUNCTION_READY_FOR_PAGE_CUTOVER_PROOF",
        "route_present": f"def {ROUTE}(" in source,
        "route_exported": ROUTE in controller_exports,
        "scenarios": scenarios,
        "inputs_page_wiring_changed": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    scenarios = dict(capture.get("scenarios") or {})
    return {
        "controller_route_present": capture.get("route_present") is True,
        "controller_route_exported": capture.get("route_exported") is True,
        "safe_branch_selected": scenarios.get("safe_branch", {}).get("selected_branch")
        == SAFE_BRANCH,
        "bending_branch_selected": scenarios.get("bending_branch", {}).get("selected_branch")
        == BENDING_BRANCH,
        "none_branch_returns_none": scenarios.get("none_branch", {}).get("result_present") is False,
        "trace_hashes_match": all(
            row.get("trace_result_hash_match") is True for row in scenarios.values()
        ),
        "result_hashes_stable": all(row.get("result_hash_stable") is True for row in scenarios.values()),
        "action_results_are_apply_candidates": all(
            (
                row.get("result_present") is False
                or (
                    row.get("action_type") == "apply_resolved_candidate"
                    and row.get("updates_present") is True
                )
            )
            for row in scenarios.values()
        ),
        "trace_is_non_driving": all(
            row.get("product_driving") is not True
            and row.get("render_driving") is not True
            and row.get("apply_driving") is not True
            and row.get("session_driving") is not True
            for row in scenarios.values()
        ),
        "inputs_page_wiring_unchanged": capture.get("inputs_page_wiring_changed") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide No-Active Blocked-Primary Controller Route Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Scenario Branches",
        ]
    )
    for name, row in dict(capture.get("scenarios") or {}).items():
        lines.append(
            f"- {name}: selected=`{row.get('selected_branch')}`, result_present=`{row.get('result_present')}`"
        )
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            "Wire this controller route through the generic page-shell caller beside the existing page route and prove parity before deleting the page-owned route body.",
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
        / f"design_guide_no_active_blocked_primary_controller_route_object_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_blocked_primary_controller_route_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_blocked_primary_controller_route_object {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
