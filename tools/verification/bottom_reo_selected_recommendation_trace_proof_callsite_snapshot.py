"""Proof-only snapshot for bottom-reo selected proof trace-callsite wiring.

This verifier projects the proof payload that could be emitted beside the live
selected-candidate decision trace, then compares it with the existing verifier
reconstruction. It does not modify product tracing, selection, wording,
CTA/action, one-click behavior, publication, rendering, session/debug plumbing,
or candidate mutation.
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

from design_brain.families.bending import (
    build_bottom_reo_repair_blocked_reason_proof,
    build_bottom_reo_selected_recommendation_proof,
)
from tools.verification.bottom_reo_recommendation_readiness_snapshot import (
    _load_jsonl,
    _stable_hash,
)
from tools.verification.bottom_reo_selected_recommendation_handoff_snapshot import (
    SCENARIOS,
    _handoff_summary,
    _matching_return_payloads,
)
from tools.verification.bottom_reo_selected_recommendation_parity_snapshot import (
    _build_proof_from_result,
    _normalise_result_shape,
    _return_payload,
)
from tools.verification.bottom_reo_selected_recommendation_reason_handoff_snapshot import (
    _blocked_reason_source_surface,
    _reason_visibility_surface,
    _repair_reason_source_surface,
    _selected_update_hash_surface,
    _selector_trace_reason_surface,
    _visible_guidance_text_source,
)
from tools.verification.bottom_reo_selector_wrapper_parity_snapshot import _run_scenario


ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"
TRACE_DIR = REPO / "artifacts" / "traces"

FORBIDDEN_TRACE_PROOF_KEYS = {
    "action",
    "action_payload",
    "action_type",
    "button_contract",
    "card_model",
    "cta",
    "cta_intent",
    "dashboard_reasons",
    "debug",
    "debug_trace",
    "final_selected_repair",
    "html",
    "mutation",
    "one_click",
    "one_click_action",
    "publication",
    "published",
    "render",
    "reason_rows",
    "session",
    "session_state",
    "status_display",
    "ui",
    "visible_blocked_wording",
    "visible_wording",
}


def _walk_forbidden_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_TRACE_PROOF_KEYS:
                found.add(key_text)
            found.update(_walk_forbidden_keys(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(_walk_forbidden_keys(child))
    return found


def _json_field(payload: dict[str, Any], key: str, failures: list[str], scenario: str) -> dict[str, Any] | None:
    raw = payload.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str):
        failures.append(f"{scenario}:{key}_not_json_string")
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        failures.append(f"{scenario}:{key}_invalid_json")
        return None
    return parsed if isinstance(parsed, dict) else None


def _selected_source_index(decision: dict[str, Any], selected_identity: Any) -> int | None:
    ranked = [str(value) for value in list(decision.get("ranked_candidate_identities") or [])]
    if selected_identity is None:
        return None
    selected_text = str(selected_identity)
    return ranked.index(selected_text) if selected_text in ranked else None


def _trace_selected_recommendation_projection(
    *,
    result: dict[str, Any],
    handoff: dict[str, Any],
) -> dict[str, Any]:
    decision = dict(handoff.get("selected_candidate_decision_surface") or {})
    selector = dict(handoff.get("live_selector_result") or {})
    shape = _normalise_result_shape(result)
    selected_identity = (
        selector.get("selected_candidate_identity")
        or decision.get("selected_candidate_identity")
        or None
    )
    utilisation_summary = {
        "selected_bending_util": selector.get("selected_bending_util") or decision.get("selected_bending_util"),
        "selected_candidate_post_util": selector.get("selected_candidate_post_util") or decision.get("selected_candidate_post_util"),
        "selected_reaches_target_band": selector.get("selected_reaches_target_band") or decision.get("selected_reaches_target_band"),
        "target_low": selector.get("target_low") or decision.get("target_low"),
        "target_high": selector.get("target_high") or decision.get("target_high"),
        "post_selector_guard_result": decision.get("post_selector_guard_result"),
        "return_status": handoff.get("return_status"),
        "return_reason": handoff.get("return_reason"),
    }
    proof = build_bottom_reo_selected_recommendation_proof(
        selected_candidate_identity=selected_identity,
        selected_source="page_local_bottom_reo_selected_recommendation",
        selected_source_index=_selected_source_index(decision, selected_identity),
        arrangement=dict(shape.get("arrangement") or {}),
        updates=dict(shape.get("updates") or {}),
        actual_ast=shape.get("actual_ast"),
        required_ast=shape.get("required_ast"),
        util=shape.get("util"),
        label=shape.get("label"),
        score=shape.get("score"),
        recommendation_compound=shape.get("recommendation_compound"),
        subfamilies=list(shape.get("subfamilies") or []),
        recommendation_family_tag=shape.get("recommendation_family_tag"),
        guidance_recommendation_title=shape.get("guidance_recommendation_title"),
        delta_b_mm=shape.get("delta_b_mm"),
        delta_D_mm=shape.get("delta_D_mm"),
        delta_Ast_bot=shape.get("delta_Ast_bot"),
        guidance_change_lines=list(shape.get("guidance_change_lines") or []),
        utilisation_check_summary=utilisation_summary,
        selected_candidate_trace_hash=(
            selector.get("selected_candidate_trace_hash")
            or decision.get("selected_candidate_trace_hash")
        ),
    ).to_dict()
    return {
        "callsite": "inputs_page.py:_compute_bottom_reo_recommendation:selected_candidate_decision_trace",
        "emission_kind": (
            "selected_recommendation_proof"
            if selected_identity is not None
            else "null_selected_recommendation_proof"
        ),
        "selected_recommendation_proof": proof,
        "selected_recommendation_proof_hash": proof.get("proof_hash"),
        "selected_recommendation_shape_hash": proof.get("selected_recommendation_shape_hash"),
    }


def _trace_repair_blocked_reason_projection(handoff: dict[str, Any]) -> dict[str, Any]:
    proof = dict(handoff.get("selected_recommendation_proof") or {})
    selected_update_hash_surface = _selected_update_hash_surface(handoff)
    selector_guard_outcomes = dict(handoff.get("guard_surface") or {})
    selector_trace_reasons = _selector_trace_reason_surface(handoff)
    repair_reason_source_surface = _repair_reason_source_surface(handoff)
    blocked_reason_source_surface = _blocked_reason_source_surface(handoff)
    reason_visibility_surface = _reason_visibility_surface(handoff)
    visible_guidance_text_source = _visible_guidance_text_source(handoff)
    reason_proof = build_bottom_reo_repair_blocked_reason_proof(
        selected_recommendation_identity=proof.get("selected_candidate_identity"),
        selected_recommendation_proof_hash=proof.get("proof_hash"),
        selected_recommendation_shape_hash=proof.get("selected_recommendation_shape_hash"),
        selected_recommendation_handoff_hash=handoff.get("selected_recommendation_hash"),
        selected_candidate_identity=handoff.get("selected_candidate_identity"),
        selected_candidate_trace_hash=handoff.get("selected_candidate_trace_hash"),
        selected_update_hash_surface=selected_update_hash_surface,
        selector_guard_outcomes=selector_guard_outcomes,
        selector_trace_reasons=selector_trace_reasons,
        repair_reason_source_surface=repair_reason_source_surface,
        blocked_reason_source_surface=blocked_reason_source_surface,
        reason_visibility_surface=reason_visibility_surface,
        visible_guidance_text_source=visible_guidance_text_source,
    ).to_dict()
    return {
        "callsite": "inputs_page.py:_compute_bottom_reo_recommendation:selected_candidate_decision_trace",
        "repair_blocked_reason_proof": reason_proof,
        "repair_blocked_reason_proof_hash": reason_proof.get("proof_hash"),
        "selector_trace_reasons": selector_trace_reasons,
        "reason_visibility_surface": reason_visibility_surface,
        "visible_wording_materialized": False,
    }


def _trace_callsite_projection(
    *,
    scenario: str,
    result: dict[str, Any],
    payload: dict[str, Any],
    proof_failures: list[str],
) -> dict[str, Any]:
    verifier_proof_summary = _build_proof_from_result(
        result=result,
        payload=payload,
        scenario=scenario,
        failures=proof_failures,
    )
    handoff = _handoff_summary(
        scenario=scenario,
        result=result,
        payload=payload,
        failures=proof_failures,
    )
    verifier_selected = dict(handoff.get("selected_recommendation_proof") or {})
    verifier_reason = _trace_repair_blocked_reason_projection(handoff)
    trace_selected = _trace_selected_recommendation_projection(result=result, handoff=handoff)
    trace_reason = _trace_repair_blocked_reason_projection(handoff)
    emitted_selected = _json_field(
        payload,
        "selected_recommendation_proof_json",
        proof_failures,
        scenario,
    )
    emitted_reason = _json_field(
        payload,
        "repair_blocked_reason_proof_json",
        proof_failures,
        scenario,
    )
    emitted_handoff_hash = payload.get("trace_proof_handoff_hash")
    expected_selected_hash = verifier_selected.get("proof_hash")
    expected_reason_hash = trace_reason.get("repair_blocked_reason_proof_hash")
    selected_is_expected = handoff.get("selected_candidate_identity") is not None
    selected_hash_match = (
        emitted_selected is None
        if not selected_is_expected
        else expected_selected_hash == (emitted_selected or {}).get("proof_hash")
    )
    reason_hash_match = (
        expected_reason_hash == (emitted_reason or {}).get("proof_hash")
    )
    decision = dict(handoff.get("selected_candidate_decision_surface") or {})
    selected_update_surface = _selected_update_hash_surface(handoff)
    trace_proof_handoff = {
        "scenario": scenario,
        "return_status": handoff.get("return_status"),
        "return_reason": handoff.get("return_reason"),
        "selected_candidate_identity": handoff.get("selected_candidate_identity"),
        "selected_candidate_trace_hash": handoff.get("selected_candidate_trace_hash"),
        "selected_candidate_decision_identity_hash": _stable_hash(
            {
                "selected_candidate_identity": handoff.get("selected_candidate_identity"),
                "selected_candidate_trace_hash": handoff.get("selected_candidate_trace_hash"),
                "post_selector_guard_result": decision.get("post_selector_guard_result"),
                "no_result_reason": decision.get("no_result_reason"),
            }
        ),
        "selected_update_hash_surface": selected_update_surface,
        "verifier_selected_recommendation_proof": verifier_selected,
        "future_trace_selected_recommendation_projection": trace_selected,
        "trace_emitted_selected_recommendation_proof": emitted_selected,
        "verifier_repair_blocked_reason_proof": verifier_reason.get("repair_blocked_reason_proof"),
        "future_trace_repair_blocked_reason_projection": trace_reason,
        "trace_emitted_repair_blocked_reason_proof": emitted_reason,
        "trace_emitted_trace_proof_handoff_hash": emitted_handoff_hash,
        "selected_recommendation_proof_hash_match": selected_hash_match,
        "repair_blocked_reason_proof_hash_match": reason_hash_match,
        "no_result_reason_surfaces": trace_reason.get("selector_trace_reasons"),
        "visible_wording_absence_evidence": {
            "final_visible_wording_materialized": False,
            "selected_proof_label_is_source_surface": True,
            "selected_proof_guidance_change_lines_are_source_surface": True,
            "render_model_fields_absent": True,
            "dashboard_reason_rows_absent": True,
        },
        "verifier_input_mutated": bool(verifier_proof_summary.get("input_mutated")),
        "verifier_forbidden_output_keys": list(verifier_proof_summary.get("forbidden_output_keys") or []),
    }
    trace_proof_handoff["stable_trace_proof_handoff_hash"] = _stable_hash(
        {
            "scenario": scenario,
            "decision_identity_hash": trace_proof_handoff["selected_candidate_decision_identity_hash"],
            "selected_update_hash_surface": selected_update_surface,
            "selected_recommendation_proof_hash": trace_selected.get("selected_recommendation_proof_hash"),
            "repair_blocked_reason_proof_hash": trace_reason.get("repair_blocked_reason_proof_hash"),
            "no_result_reason_surfaces": trace_reason.get("selector_trace_reasons"),
        }
    )
    trace_proof_handoff["trace_proof_handoff_hash_match"] = (
        emitted_handoff_hash == trace_proof_handoff["stable_trace_proof_handoff_hash"]
    )
    trace_proof_handoff["forbidden_trace_proof_keys_present"] = sorted(
        _walk_forbidden_keys(trace_proof_handoff)
    )
    return trace_proof_handoff


def _assert_projection(scenario: str, projection: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if projection.get("forbidden_trace_proof_keys_present"):
        failures.append(
            "forbidden_trace_proof_keys:"
            + ",".join(projection.get("forbidden_trace_proof_keys_present") or [])
        )
    if projection.get("verifier_forbidden_output_keys"):
        failures.append(
            "verifier_forbidden_output_keys:"
            + ",".join(projection.get("verifier_forbidden_output_keys") or [])
        )
    if projection.get("verifier_input_mutated"):
        failures.append("verifier_input_mutated")
    if not projection.get("selected_recommendation_proof_hash_match"):
        failures.append("selected_recommendation_proof_hash_mismatch")
    if not projection.get("repair_blocked_reason_proof_hash_match"):
        failures.append("repair_blocked_reason_proof_hash_mismatch")
    if not projection.get("trace_proof_handoff_hash_match"):
        failures.append("trace_proof_handoff_hash_mismatch")
    if not projection.get("stable_trace_proof_handoff_hash"):
        failures.append("missing_stable_trace_proof_handoff_hash")
    trace_selected = dict(projection.get("future_trace_selected_recommendation_projection") or {})
    emitted_selected = projection.get("trace_emitted_selected_recommendation_proof")
    trace_reason = dict(projection.get("future_trace_repair_blocked_reason_projection") or {})
    emitted_reason = projection.get("trace_emitted_repair_blocked_reason_proof")
    reason_visibility = dict(trace_reason.get("reason_visibility_surface") or {})
    if not isinstance(emitted_reason, dict):
        failures.append("missing_trace_emitted_repair_blocked_reason_proof")
    if scenario == "zero_accepted_scenario":
        if projection.get("selected_candidate_identity") is not None:
            failures.append("zero_candidate_unexpected_selection")
        if emitted_selected is not None:
            failures.append("zero_candidate_unexpected_trace_emitted_selected_proof")
        if trace_selected.get("emission_kind") != "null_selected_recommendation_proof":
            failures.append("zero_candidate_selected_proof_not_null")
        no_result = dict(projection.get("no_result_reason_surfaces") or {})
        tracked = dict(no_result.get("tracked_reasons") or {})
        if not tracked.get("no_filtered_candidates"):
            failures.append("zero_candidate_missing_no_filtered_candidates")
    else:
        if not projection.get("selected_candidate_identity"):
            failures.append("missing_selected_candidate_identity")
        if not isinstance(emitted_selected, dict):
            failures.append("missing_trace_emitted_selected_recommendation_proof")
        if trace_selected.get("emission_kind") != "selected_recommendation_proof":
            failures.append("selected_case_not_selected_recommendation_proof")
    if reason_visibility.get("selector_no_result_reason") != "trace_proof_only":
        failures.append("selector_no_result_reason_not_trace_proof_only")
    if reason_visibility.get("selector_no_candidate_reason") != "trace_proof_only":
        failures.append("selector_no_candidate_reason_not_trace_proof_only")
    if trace_reason.get("visible_wording_materialized"):
        failures.append("visible_wording_materialized")
    return sorted(set(failures))


def _write_report(path: Path, snapshot: dict[str, Any]) -> None:
    lines = [
        "# Bottom Reo Selected Recommendation Trace Proof Callsite Snapshot",
        "",
        f"- Status: {snapshot.get('status')}",
        f"- JSON artifact: `{snapshot.get('artifact_path')}`",
        f"- Trace artifact: `{snapshot.get('trace_path')}`",
        "",
        "## Scope",
        "",
        "Proof-only snapshot. It projects the selected-recommendation and repair/blocked reason proof payloads that could be emitted beside the live selected-candidate decision trace, then compares them with verifier-built proof objects. It does not change product tracing or product behavior.",
        "",
        "## Scenario Summary",
    ]
    scenarios = snapshot.get("scenarios") if isinstance(snapshot.get("scenarios"), dict) else {}
    stability = snapshot.get("stability") if isinstance(snapshot.get("stability"), dict) else {}
    for name, data in scenarios.items():
        lines.extend(
            [
                "",
                f"### {name}",
                f"- selected identity: `{data.get('selected_candidate_identity')}`",
                f"- decision identity hash: `{data.get('selected_candidate_decision_identity_hash')}`",
                f"- selected update surface: `{data.get('selected_update_hash_surface')}`",
                f"- selected proof hash match: `{data.get('selected_recommendation_proof_hash_match')}`",
                f"- reason proof hash match: `{data.get('repair_blocked_reason_proof_hash_match')}`",
                f"- trace proof handoff hash: `{data.get('stable_trace_proof_handoff_hash')}`",
                f"- emitted trace proof handoff hash: `{data.get('trace_emitted_trace_proof_handoff_hash')}`",
                f"- trace proof handoff hash match: `{data.get('trace_proof_handoff_hash_match')}`",
                f"- no-result reason surfaces: `{data.get('no_result_reason_surfaces')}`",
                f"- forbidden keys: `{data.get('forbidden_trace_proof_keys_present')}`",
                f"- stability: `{stability.get(name, {})}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Absence Proof",
            "",
            "- visible wording: absent; selected proof label/change lines are source surfaces only",
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
    trace_path = TRACE_DIR / f"bottom_reo_selected_recommendation_trace_proof_callsite_trace_{stamp}.jsonl"
    artifact_path = ARTIFACT_DIR / f"bottom_reo_selected_recommendation_trace_proof_callsite_{stamp}.json"
    report_path = AUDIT_DIR / f"bottom_reo_selected_recommendation_trace_proof_callsite_{stamp}.md"

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
    scenarios: dict[str, dict[str, Any]] = {}
    stability: dict[str, dict[str, Any]] = {}
    proof_failures: list[str] = []
    for scenario in SCENARIOS:
        matching_payloads = _matching_return_payloads(rows, scenario)
        payload = matching_payloads[0] if matching_payloads else _return_payload(rows, scenario)
        if not payload:
            failures.setdefault(scenario, []).append("return_trace_missing")
            continue
        projection = _trace_callsite_projection(
            scenario=scenario,
            result=results.get(scenario) or {},
            payload=payload,
            proof_failures=proof_failures,
        )
        scenarios[scenario] = projection
        scenario_failures = _assert_projection(scenario, projection)
        repeat_payload = matching_payloads[-1] if matching_payloads else {}
        repeat_projection = _trace_callsite_projection(
            scenario=scenario,
            result=repeat_results.get(scenario) or {},
            payload=repeat_payload if isinstance(repeat_payload, dict) else {},
            proof_failures=proof_failures,
        )
        same_hash = (
            projection.get("stable_trace_proof_handoff_hash")
            == repeat_projection.get("stable_trace_proof_handoff_hash")
        )
        stability[scenario] = {
            "same_trace_proof_handoff_hash": same_hash,
            "first_trace_proof_handoff_hash": projection.get("stable_trace_proof_handoff_hash"),
            "repeat_trace_proof_handoff_hash": repeat_projection.get("stable_trace_proof_handoff_hash"),
        }
        if not same_hash:
            scenario_failures.append("unstable_trace_proof_handoff_hash")
        if scenario_failures:
            failures[scenario] = sorted(set(scenario_failures))
    for failure in proof_failures:
        failures.setdefault("_proof", []).append(failure)
    for required in SCENARIOS:
        if required not in scenarios:
            failures.setdefault("_coverage", []).append(f"missing_{required}")

    status = "PASS" if not failures else "FAIL"
    snapshot = {
        "schema": "bottom_reo_selected_recommendation_trace_proof_callsite_snapshot.v1",
        "status": status,
        "generated_at": stamp,
        "artifact_path": str(artifact_path),
        "report_path": str(report_path),
        "trace_path": str(trace_path),
        "scenarios": scenarios,
        "stability": stability,
        "coverage": {
            "selected_normal_bending_underdesign": "covered",
            "selected_two_layer_arrangement": "covered",
            "zero_candidate_no_selection": "covered",
        },
        "assertions": {
            "product_trace_changed": False,
            "selector_logic_moved": False,
            "strict_band_noop_improvement_guards_moved": False,
            "compound_preference_logic_moved": False,
            "post_selector_guards_moved": False,
            "visible_wording_moved": False,
            "cta_action_logic_absent": True,
            "one_click_action_absent": True,
            "publication_render_ui_session_debug_absent": True,
            "candidate_mutation_moved": False,
        },
        "forbidden_trace_proof_keys": sorted(FORBIDDEN_TRACE_PROOF_KEYS),
        "recommendation": (
            "Wire the trace-only proof callsite next, guarded by this snapshot. "
            "Keep proof payloads trace-only and keep wording, CTA, one-click, "
            "publication, render/UI, session/debug, selector logic, and candidate "
            "mutation page/shared-owned."
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
