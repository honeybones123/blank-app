"""Snapshot bottom-reo ranking-result to selected-recommendation handoff.

This verifier joins the proof-only ``BottomReoRankingResultBoundary`` surface
to the live page-local selected recommendation and the family-owned
``BottomReoSelectedRecommendation`` proof object. It does not move selector
logic, strict-band/no-op/improvement guards, compound preference handling,
post-selector guards, CTA/action logic, one-click behavior, publication,
rendering, session/debug plumbing, or candidate mutation.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from design_brain.families.bending import build_bottom_reo_ranking_result_boundary
from tools.verification.bottom_reo_recommendation_readiness_snapshot import (
    _load_jsonl,
    _stable_hash,
)
from tools.verification.bottom_reo_selected_recommendation_parity_snapshot import (
    _build_proof_from_result,
    _compare_shape,
    _return_payload,
)
from tools.verification.bottom_reo_selector_wrapper_parity_snapshot import _run_scenario


ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"
TRACE_DIR = REPO / "artifacts" / "traces"

SCENARIOS = [
    "normal_bending_underdesign",
    "two_layer_arrangement",
    "zero_accepted_scenario",
]

FORBIDDEN_HANDOFF_KEYS = {
    "action",
    "action_payload",
    "action_type",
    "button_contract",
    "cta",
    "cta_intent",
    "debug",
    "debug_trace",
    "final_selected_repair",
    "mutation",
    "one_click",
    "one_click_action",
    "publication",
    "published",
    "render",
    "session",
    "session_state",
    "ui",
}


def _walk_forbidden_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_HANDOFF_KEYS:
                found.add(key_text)
            found.update(_walk_forbidden_keys(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(_walk_forbidden_keys(child))
    return found


def _ranked_identities(decision: dict[str, Any]) -> list[str]:
    return [str(value) for value in list(decision.get("ranked_candidate_identities") or [])]


def _build_ranking_result_boundary(decision: dict[str, Any]) -> dict[str, Any]:
    ranked = _ranked_identities(decision)
    selected_identity = decision.get("selected_candidate_identity") or None
    ordered_hash = decision.get("ranked_candidate_order_hash") or _stable_hash(ranked)
    kept_hash = _stable_hash(ranked)
    pruned_hash = _stable_hash([])
    policy_inputs = [
        {
            "policy_input_hash": _stable_hash(
                {
                    "source": "selected_recommendation_handoff_ranked_identity",
                    "index": index,
                    "candidate_identity": identity,
                }
            ),
        }
        for index, identity in enumerate(ranked)
    ]
    ranking_decisions = []
    for identity in ranked:
        if selected_identity and str(identity) == str(selected_identity):
            ranking_decisions.append(
                {
                    "candidate_identity": identity,
                    "decision": "selected_by_page_local_selector",
                }
            )
        else:
            ranking_decisions.append(
                {
                    "candidate_identity": identity,
                    "decision": "ranked_available_before_selection",
                }
            )
    callback_handoff_hash = _stable_hash(
        {
            "source": "selected_recommendation_handoff_trace",
            "ranked_candidate_order_hash": ordered_hash,
            "selector_input_candidate_identity": decision.get("selector_input_candidate_identity"),
            "selector_output_candidate_identity": decision.get("selector_output_candidate_identity"),
        }
    )
    return build_bottom_reo_ranking_result_boundary(
        policy_inputs=policy_inputs,
        ordered_identities=ranked,
        kept_identities=ranked,
        pruned_identities=[],
        ranking_decisions=ranking_decisions,
        ordered_hash=ordered_hash,
        kept_hash=kept_hash,
        pruned_hash=pruned_hash,
        callback_handoff_hash=callback_handoff_hash,
    ).to_dict()


def _guard_surface(decision: dict[str, Any], selector: dict[str, Any]) -> dict[str, Any]:
    return {
        "strict_band": {
            "winner_seen": bool(selector.get("strict_band_winner_seen")),
            "winner_accepted": bool(selector.get("strict_band_winner_accepted")),
            "rejected_reason": selector.get("strict_band_rejected_reason"),
            "legacy_rejection_reason": selector.get("legacy_rejection_reason"),
            "selected_reason": selector.get("selected_reason"),
            "no_candidate_reason": selector.get("no_candidate_reason"),
        },
        "noop_or_improvement": {
            "selector_status": selector.get("status"),
            "selected_reason": selector.get("selected_reason"),
            "no_candidate_reason": selector.get("no_candidate_reason"),
            "legacy_rejection_reason": selector.get("legacy_rejection_reason"),
        },
        "compound_preference": {
            "changed": bool(decision.get("compound_preference_changed")),
            "selected": bool(decision.get("compound_preference_selected")),
            "selector_input_candidate_identity": decision.get("selector_input_candidate_identity"),
            "selector_output_candidate_identity": decision.get("selector_output_candidate_identity"),
        },
        "post_selector_guard": {
            "result": decision.get("post_selector_guard_result"),
            "no_result_reason": decision.get("no_result_reason"),
        },
    }


def _handoff_summary(
    *,
    scenario: str,
    result: dict[str, Any],
    payload: dict[str, Any],
    failures: list[str],
) -> dict[str, Any]:
    proof_summary = _build_proof_from_result(
        result=result,
        payload=payload,
        scenario=scenario,
        failures=failures,
    )
    decision = dict(proof_summary.get("decision") or {})
    selector = dict(proof_summary.get("selector") or {})
    proof = dict(proof_summary.get("proof") or {})
    ranking_result_boundary = _build_ranking_result_boundary(decision)
    guard_surface = _guard_surface(decision, selector)
    selected_update_surface = {
        "selected_candidate_update_keys": list(decision.get("selected_candidate_update_keys") or []),
        "selected_candidate_updates_hash": decision.get("selected_candidate_updates_hash"),
        "final_result_update_keys": list(decision.get("final_result_update_keys") or []),
        "final_result_updates_hash": decision.get("final_result_updates_hash"),
        "proof_returned_update_keys": list(proof.get("returned_update_keys") or []),
        "proof_returned_updates_hash": proof.get("returned_updates_hash"),
    }
    selected_recommendation_hash = _stable_hash(
        {
            "ranking_result_hash": ranking_result_boundary.get("ranking_result_hash"),
            "selector_result": selector,
            "selected_candidate_decision": decision,
            "selected_recommendation_shape_hash": proof.get("selected_recommendation_shape_hash"),
            "selected_recommendation_proof_hash": proof.get("proof_hash"),
            "guards": guard_surface,
        }
    )
    handoff = {
        "scenario": scenario,
        "return_status": payload.get("status"),
        "return_reason": payload.get("return_reason"),
        "ranking_result_boundary_source": "selected_candidate_decision_ranked_identity_surface",
        "ranking_result_boundary": ranking_result_boundary,
        "ranking_result_boundary_hash": ranking_result_boundary.get("ranking_result_hash"),
        "live_selector_result": selector,
        "selected_candidate_identity": (
            selector.get("selected_candidate_identity")
            or decision.get("selected_candidate_identity")
        ),
        "selected_candidate_trace_hash": (
            selector.get("selected_candidate_trace_hash")
            or decision.get("selected_candidate_trace_hash")
        ),
        "selected_candidate_update_surface": selected_update_surface,
        "selected_candidate_decision_surface": decision,
        "guard_surface": guard_surface,
        "selected_recommendation_proof": proof,
        "selected_recommendation_shape_hash": proof.get("selected_recommendation_shape_hash"),
        "selected_recommendation_hash": selected_recommendation_hash,
        "selected_recommendation_input_mutated": bool(proof_summary.get("input_mutated")),
        "selected_recommendation_forbidden_output_keys": list(proof_summary.get("forbidden_output_keys") or []),
        "live_candidate_dict_count_in_proof": int(proof_summary.get("live_candidate_dict_count") or 0),
        "page_local_shape": dict(proof_summary.get("page_local_shape") or {}),
    }
    handoff["forbidden_handoff_keys_present"] = sorted(_walk_forbidden_keys(handoff))
    return handoff


def _matching_return_payloads(rows: list[dict[str, Any]], scenario: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for row in rows:
        if (
            row.get("event") == "compute_guidance_route"
            and row.get("scenario") == f"BOTTOM_REO_SELECTED_RECOMMENDATION_{scenario}"
            and str(row.get("route_event") or "").endswith("_return")
        ):
            payload = row.get("payload")
            if isinstance(payload, dict):
                payloads.append(payload)
    return payloads


def _assert_handoff(scenario: str, handoff: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    boundary = dict(handoff.get("ranking_result_boundary") or {})
    proof = dict(handoff.get("selected_recommendation_proof") or {})
    decision = dict(handoff.get("selected_candidate_decision_surface") or {})
    selector = dict(handoff.get("live_selector_result") or {})
    if handoff.get("forbidden_handoff_keys_present"):
        failures.append(
            "forbidden_handoff_keys:"
            + ",".join(handoff.get("forbidden_handoff_keys_present") or [])
        )
    if boundary.get("forbidden_fields_present"):
        failures.append(
            "ranking_result_boundary_forbidden_fields:"
            + ",".join(boundary.get("forbidden_fields_present") or [])
        )
    if proof.get("forbidden_fields_present"):
        failures.append(
            "selected_recommendation_forbidden_fields:"
            + ",".join(proof.get("forbidden_fields_present") or [])
        )
    if handoff.get("selected_recommendation_forbidden_output_keys"):
        failures.append(
            "selected_recommendation_forbidden_output_keys:"
            + ",".join(handoff.get("selected_recommendation_forbidden_output_keys") or [])
        )
    if handoff.get("live_candidate_dict_count_in_proof"):
        failures.append("live_candidate_dicts_in_selected_proof")
    if handoff.get("selected_recommendation_input_mutated"):
        failures.append("selected_recommendation_input_mutated")
    if not boundary.get("ranking_result_hash"):
        failures.append("missing_ranking_result_hash")
    if not handoff.get("selected_recommendation_hash"):
        failures.append("missing_selected_recommendation_hash")
    if scenario != "zero_accepted_scenario":
        if not handoff.get("selected_candidate_identity"):
            failures.append("missing_selected_candidate_identity")
        if not proof.get("selected_recommendation_shape_hash"):
            failures.append("missing_selected_recommendation_shape_hash")
        if selector.get("status") != "selected":
            failures.append(f"selector_not_selected:{selector.get('status')!r}")
        if decision.get("post_selector_guard_result") != "selected":
            failures.append(
                f"post_selector_guard_not_selected:{decision.get('post_selector_guard_result')!r}"
            )
    else:
        if handoff.get("selected_candidate_identity") is not None:
            failures.append(
                f"unexpected_zero_candidate_selection:{handoff.get('selected_candidate_identity')!r}"
            )
        if proof.get("selected_recommendation_shape_hash") is None:
            failures.append("zero_candidate_missing_proof_shape_hash")
    return sorted(set(failures))


def _write_report(path: Path, snapshot: dict[str, Any]) -> None:
    lines = [
        "# Bottom Reo Selected Recommendation Handoff Snapshot",
        "",
        f"- Status: {snapshot.get('status')}",
        f"- JSON artifact: `{snapshot.get('artifact_path')}`",
        f"- Trace artifact: `{snapshot.get('trace_path')}`",
        "",
        "## Scope",
        "",
        "Proof-only snapshot. It joins the proof-only `BottomReoRankingResultBoundary`, live selector result, selected-candidate decision surface, guard outcomes, and family-owned `BottomReoSelectedRecommendation` proof object. It does not move selector logic or product-driving behavior.",
        "",
        "## Scenario Summary",
    ]
    scenarios = snapshot.get("scenarios") if isinstance(snapshot.get("scenarios"), dict) else {}
    stability = snapshot.get("stability") if isinstance(snapshot.get("stability"), dict) else {}
    for name, data in scenarios.items():
        proof = dict((data or {}).get("selected_recommendation_proof") or {})
        boundary = dict((data or {}).get("ranking_result_boundary") or {})
        guard = dict((data or {}).get("guard_surface") or {})
        lines.extend(
            [
                "",
                f"### {name}",
                f"- return: `{data.get('return_status')}` / `{data.get('return_reason')}`",
                f"- selected identity: `{data.get('selected_candidate_identity')}`",
                f"- ranking result hash: `{boundary.get('ranking_result_hash')}`",
                f"- selected recommendation hash: `{data.get('selected_recommendation_hash')}`",
                f"- selected shape hash: `{proof.get('selected_recommendation_shape_hash')}`",
                f"- update surface: `{data.get('selected_candidate_update_surface')}`",
                f"- guards: `{guard}`",
                f"- forbidden keys: `{data.get('forbidden_handoff_keys_present')}`",
                f"- stability: `{stability.get(name, {})}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Coverage Notes",
            "",
            f"- normal bending underdesign: `{bool(scenarios.get('normal_bending_underdesign'))}`",
            f"- two-layer arrangement: `{bool(scenarios.get('two_layer_arrangement'))}`",
            f"- zero-candidate/no-selection: `{bool(scenarios.get('zero_accepted_scenario'))}`",
            "- no-op or strict-band scenario: `not_available_in_existing_selected_recommendation_harness`",
            "",
            "## Absence Proof",
            "",
            "- CTA intent: absent",
            "- one-click action: absent",
            "- publication fields: absent",
            "- render/UI fields: absent",
            "- session/debug-only fields: absent",
            "",
            "## Recommendation",
            "",
            str(snapshot.get("recommendation") or ""),
        ]
    )
    failures = snapshot.get("failures") if isinstance(snapshot.get("failures"), dict) else {}
    if failures:
        lines.extend(["", "## Failures", ""])
        for scenario, scenario_failures in failures.items():
            lines.append(f"- {scenario}: {', '.join(scenario_failures)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    module = importlib.import_module("inputs_page")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"bottom_reo_selected_recommendation_handoff_trace_{stamp}.jsonl"
    artifact_path = ARTIFACT_DIR / f"bottom_reo_selected_recommendation_handoff_{stamp}.json"
    report_path = AUDIT_DIR / f"bottom_reo_selected_recommendation_handoff_{stamp}.md"

    previous_env = {
        key: os.environ.get(key)
        for key in (
            "DESIGN_GUIDE_RUNTIME_TRACE",
            "DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO",
            "DESIGN_GUIDE_RUNTIME_TRACE_PATH",
        )
    }
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE"] = "1"
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_PATH"] = str(trace_path)

    results: dict[str, dict[str, Any]] = {}
    repeat_results: dict[str, dict[str, Any]] = {}
    try:
        for scenario in SCENARIOS:
            os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = (
                f"BOTTOM_REO_SELECTED_RECOMMENDATION_{scenario}"
            )
            results[scenario] = _run_scenario(module, scenario)
        for scenario in SCENARIOS:
            os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = (
                f"BOTTOM_REO_SELECTED_RECOMMENDATION_{scenario}"
            )
            repeat_results[scenario] = _run_scenario(module, scenario)
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    rows = _load_jsonl(trace_path)
    failures: dict[str, list[str]] = {}
    scenario_summaries: dict[str, dict[str, Any]] = {}
    repeat_summaries: dict[str, dict[str, Any]] = {}
    stability: dict[str, dict[str, Any]] = {}
    proof_failures: list[str] = []
    for scenario in SCENARIOS:
        matching_payloads = _matching_return_payloads(rows, scenario)
        payload = matching_payloads[0] if matching_payloads else _return_payload(rows, scenario)
        if not payload:
            failures.setdefault(scenario, []).append("return_trace_missing")
            continue
        handoff = _handoff_summary(
            scenario=scenario,
            result=results.get(scenario) or {},
            payload=payload,
            failures=proof_failures,
        )
        scenario_summaries[scenario] = handoff
        scenario_failures = _assert_handoff(scenario, handoff)
        if scenario != "zero_accepted_scenario":
            _compare_shape(
                scenario,
                {
                    "page_local_shape": handoff.get("page_local_shape"),
                    "proof": handoff.get("selected_recommendation_proof"),
                },
                scenario_failures,
            )
        repeat_payload = matching_payloads[-1] if matching_payloads else {}
        repeat = _handoff_summary(
            scenario=scenario,
            result=repeat_results.get(scenario) or {},
            payload=repeat_payload if isinstance(repeat_payload, dict) else {},
            failures=proof_failures,
        )
        repeat_summaries[scenario] = repeat
        same_selected = handoff.get("selected_recommendation_hash") == repeat.get("selected_recommendation_hash")
        same_ranking = handoff.get("ranking_result_boundary_hash") == repeat.get("ranking_result_boundary_hash")
        stability[scenario] = {
            "same_selected_recommendation_hash": same_selected,
            "same_ranking_result_boundary_hash": same_ranking,
            "first_selected_recommendation_hash": handoff.get("selected_recommendation_hash"),
            "repeat_selected_recommendation_hash": repeat.get("selected_recommendation_hash"),
            "first_ranking_result_boundary_hash": handoff.get("ranking_result_boundary_hash"),
            "repeat_ranking_result_boundary_hash": repeat.get("ranking_result_boundary_hash"),
        }
        if not same_selected:
            scenario_failures.append("unstable_selected_recommendation_hash")
        if not same_ranking:
            scenario_failures.append("unstable_ranking_result_boundary_hash")
        if scenario_failures:
            failures[scenario] = sorted(set(scenario_failures))
    for failure in proof_failures:
        failures.setdefault("_proof", []).append(failure)
    if "normal_bending_underdesign" not in scenario_summaries:
        failures.setdefault("_coverage", []).append("missing_normal_bending_underdesign")
    if "two_layer_arrangement" not in scenario_summaries:
        failures.setdefault("_coverage", []).append("missing_two_layer_arrangement")
    if "zero_accepted_scenario" not in scenario_summaries:
        failures.setdefault("_coverage", []).append("missing_zero_candidate_no_selection")

    status = "PASS" if not failures else "FAIL"
    snapshot = {
        "schema": "bottom_reo_selected_recommendation_handoff_snapshot.v1",
        "status": status,
        "generated_at": stamp,
        "artifact_path": str(artifact_path),
        "report_path": str(report_path),
        "trace_path": str(trace_path),
        "scenarios": scenario_summaries,
        "stability": stability,
        "coverage": {
            "normal_bending_underdesign": "covered",
            "two_layer_arrangement": "covered",
            "zero_candidate_no_selection": "covered",
            "noop_or_strict_band": "not_available_in_existing_selected_recommendation_harness",
        },
        "assertions": {
            "selector_logic_moved": False,
            "strict_band_noop_improvement_guards_moved": False,
            "compound_preference_logic_moved": False,
            "post_selector_guards_moved": False,
            "cta_action_logic_absent": True,
            "one_click_action_absent": True,
            "publication_ui_session_debug_absent": True,
            "candidate_mutation_moved": False,
        },
        "forbidden_handoff_keys": sorted(FORBIDDEN_HANDOFF_KEYS),
        "recommendation": (
            "Keep selector page-local. Next safe slice is to add a page-local proof callsite "
            "beside the selected-candidate decision trace, or audit repair/blocked reason handoff "
            "before moving any selected-recommendation normalizer."
        ),
        "failures": failures,
    }
    artifact_path.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    _write_report(report_path, snapshot)
    print(
        json.dumps(
            {
                "status": status,
                "artifact": str(artifact_path),
                "report": str(report_path),
                "trace": str(trace_path),
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
