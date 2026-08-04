"""Proof-only snapshot for bottom-reo CTA/action intent boundary.

This verifier freezes the current bottom-reo guidance action payload surface and
projects the future family-owned CTA/action intent proof shape. It does not make
the proof product-driving, move CTA/action logic, move apply routing, move
one-click fallback logic, resolve final button source precedence, publish, render,
or read UI/session/debug state.
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

from design_brain.families.bending import build_bottom_reo_cta_intent_proof
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
    _normalise_result_shape,
    _return_payload,
)
from tools.verification.bottom_reo_selected_recommendation_reason_handoff_snapshot import (
    _reason_handoff_summary,
)
from tools.verification.bottom_reo_selector_wrapper_parity_snapshot import _run_scenario


ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"
TRACE_DIR = REPO / "artifacts" / "traces"

FORBIDDEN_FUTURE_INTENT_KEYS = {
    "apply_actionable",
    "apply_enabled",
    "button_contract",
    "button_contract_enabled",
    "cta_source_precedence",
    "debug",
    "debug_trace",
    "disabled_reason",
    "enabled",
    "final_button_contract",
    "final_enabled",
    "final_rendered_button_label",
    "html",
    "one_click_fallback_route",
    "one_click_routing",
    "publication",
    "publication_gate",
    "published",
    "render",
    "rendered_button_label",
    "selected_family_publication_gate",
    "session",
    "session_state",
    "shared_source_precedence_decision",
    "ui",
    "visible_wording",
}


def _walk_forbidden_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_FUTURE_INTENT_KEYS:
                found.add(key_text)
            found.update(_walk_forbidden_keys(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(_walk_forbidden_keys(child))
    return found


def _json_normalized(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


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


def _current_guidance_action_payload(result: dict[str, Any]) -> dict[str, Any]:
    shape = _normalise_result_shape(result)
    updates = dict(shape.get("updates") or {})
    if not updates:
        return {
            "materialized": False,
            "source": "bottom_reo_recommendation:no_action",
            "action_type": None,
            "payload": {},
            "payload_hash": _stable_hash({}),
            "update_keys": [],
            "updates_hash": _stable_hash({}),
            "action_kind_source": "no_selected_bottom_reo_recommendation",
        }
    title = (
        str(shape.get("guidance_recommendation_title") or shape.get("label") or "").strip()
        or "Apply bottom recommendation"
    )
    action_type = (
        "apply_compound_guidance"
        if bool(shape.get("recommendation_compound"))
        else "apply_bottom_recommendation"
    )
    payload = {
        "updates": updates,
        "guidance_banner_title": title,
        "label": title,
    }
    return {
        "materialized": True,
        "source": "inputs_page.py:_get_one_click_band_reaching_candidate:bottom_recommendation_option",
        "action_type": action_type,
        "payload": payload,
        "payload_hash": _stable_hash(payload),
        "update_keys": sorted(str(key) for key in updates.keys()),
        "updates_hash": _stable_hash(updates),
        "action_kind_source": (
            "recommendation_compound"
            if bool(shape.get("recommendation_compound"))
            else "bottom_recommendation"
        ),
    }


def _selected_update_hash_surface(handoff: dict[str, Any]) -> dict[str, Any]:
    surface = dict(handoff.get("selected_candidate_update_surface") or {})
    return {
        "selected_candidate_update_keys": list(surface.get("selected_candidate_update_keys") or []),
        "selected_candidate_updates_hash": surface.get("selected_candidate_updates_hash"),
        "final_result_update_keys": list(surface.get("final_result_update_keys") or []),
        "final_result_updates_hash": surface.get("final_result_updates_hash"),
        "proof_returned_update_keys": list(surface.get("proof_returned_update_keys") or []),
        "proof_returned_updates_hash": surface.get("proof_returned_updates_hash"),
    }


def _future_cta_intent_projection(
    *,
    scenario: str,
    handoff: dict[str, Any],
    reason_handoff: dict[str, Any],
    current_action: dict[str, Any],
) -> dict[str, Any]:
    selected_proof = dict(handoff.get("selected_recommendation_proof") or {})
    reason_proof = dict(reason_handoff.get("repair_blocked_reason_proof") or {})
    selected_update_surface = _selected_update_hash_surface(handoff)
    action_materialized = bool(current_action.get("materialized"))
    no_action_surface = (
        dict(reason_handoff.get("selector_trace_reasons") or {})
        if not action_materialized
        else {}
    )
    intent_state = (
        "actionable_candidate"
        if action_materialized
        else (
            "trace_only_no_selection"
            if scenario == "zero_accepted_scenario"
            else "not_materialized"
        )
    )
    return build_bottom_reo_cta_intent_proof(
        selected_recommendation_identity=selected_proof.get("selected_candidate_identity"),
        selected_recommendation_proof_hash=selected_proof.get("proof_hash"),
        selected_recommendation_shape_hash=selected_proof.get("selected_recommendation_shape_hash"),
        repair_blocked_reason_proof_hash=reason_proof.get("proof_hash"),
        selected_update_hash_surface=selected_update_surface,
        action_payload_identity={
            "materialized": action_materialized,
            "action_type": current_action.get("action_type"),
            "action_type_source": current_action.get("action_kind_source"),
            "payload_hash": current_action.get("payload_hash"),
            "update_keys": list(current_action.get("update_keys") or []),
            "updates_hash": current_action.get("updates_hash"),
        },
        action_intent_source={
            "source": current_action.get("source"),
            "recommendation_family_tag": selected_proof.get("recommendation_family_tag"),
            "subfamilies": list(selected_proof.get("subfamilies") or []),
            "recommendation_compound": bool(selected_proof.get("recommendation_compound")),
        },
        intent_state=intent_state,
        no_action_or_blocked_proof_source=no_action_surface,
    ).to_dict()


def _scenario_summary(
    *,
    scenario: str,
    result: dict[str, Any],
    payload: dict[str, Any],
    failures: list[str],
) -> dict[str, Any]:
    handoff = _handoff_summary(
        scenario=scenario,
        result=result,
        payload=payload,
        failures=failures,
    )
    reason_handoff = _reason_handoff_summary(
        scenario=scenario,
        result=result,
        payload=payload,
        proof_failures=failures,
    )
    current_action = _current_guidance_action_payload(result)
    emitted_selected_proof = _json_field(
        payload,
        "selected_recommendation_proof_json",
        failures,
        scenario,
    )
    emitted_reason_proof = _json_field(
        payload,
        "repair_blocked_reason_proof_json",
        failures,
        scenario,
    )
    emitted_cta_intent_proof = _json_field(
        payload,
        "bottom_reo_cta_intent_proof_json",
        failures,
        scenario,
    )
    projected = _future_cta_intent_projection(
        scenario=scenario,
        handoff=handoff,
        reason_handoff=reason_handoff,
        current_action=current_action,
    )
    summary = {
        "scenario": scenario,
        "return_status": payload.get("status"),
        "return_reason": payload.get("return_reason"),
        "current_guidance_action_payload": current_action,
        "selected_recommendation_identity": handoff.get("selected_candidate_identity"),
        "selected_recommendation_proof_hash": (
            (emitted_selected_proof or {}).get("proof_hash")
            or (handoff.get("selected_recommendation_proof") or {}).get("proof_hash")
        ),
        "selected_recommendation_shape_hash": (
            (emitted_selected_proof or {}).get("selected_recommendation_shape_hash")
            or (handoff.get("selected_recommendation_proof") or {}).get("selected_recommendation_shape_hash")
        ),
        "repair_blocked_reason_proof_hash": (
            (emitted_reason_proof or {}).get("proof_hash")
            or reason_handoff.get("repair_blocked_reason_proof_hash")
        ),
        "selected_update_hash_surface": _selected_update_hash_surface(handoff),
        "action_apply_payload_identity": {
            "action_type": current_action.get("action_type"),
            "payload_hash": current_action.get("payload_hash"),
            "update_keys": list(current_action.get("update_keys") or []),
            "updates_hash": current_action.get("updates_hash"),
        },
        "action_kind_source": current_action.get("action_kind_source"),
        "no_action_blocked_proof_source": (
            projected.get("no_action_or_blocked_proof_source")
            if not current_action.get("materialized")
            else {}
        ),
        "future_bottom_reo_cta_intent_projection": projected,
        "future_bottom_reo_cta_intent_proof_hash": projected.get("cta_intent_proof_hash"),
        "trace_emitted_bottom_reo_cta_intent_proof": emitted_cta_intent_proof,
        "trace_emitted_bottom_reo_cta_intent_proof_hash": (
            (emitted_cta_intent_proof or {}).get("cta_intent_proof_hash")
            or payload.get("bottom_reo_cta_intent_proof_hash")
        ),
        "trace_emitted_bottom_reo_cta_intent_proof_hash_match": (
            ((emitted_cta_intent_proof or {}).get("cta_intent_proof_hash") or payload.get("bottom_reo_cta_intent_proof_hash"))
            == projected.get("cta_intent_proof_hash")
        ),
        "trace_emitted_bottom_reo_cta_intent_shape_match": (
            _json_normalized(emitted_cta_intent_proof or {}) == _json_normalized(projected)
        ),
        "absence_proof": {
            "final_rendered_button_label_absent": "final_rendered_button_label" not in projected,
            "final_enabled_disabled_state_absent": not any(
                key in projected
                for key in (
                    "apply_enabled",
                    "apply_actionable",
                    "button_contract_enabled",
                    "final_enabled",
                    "disabled_reason",
                )
            ),
            "shared_source_precedence_decision_absent": "shared_source_precedence_decision" not in projected,
            "selected_family_publication_gate_output_absent": "selected_family_publication_gate" not in projected,
            "visible_wording_absent": "visible_wording" not in projected,
            "one_click_fallback_routing_absent": "one_click_fallback_route" not in projected,
            "render_ui_session_debug_absent": not (
                {"render", "ui", "session", "session_state", "debug", "debug_trace"} & set(_walk_forbidden_keys(projected))
            ),
        },
    }
    summary["scenario_cta_intent_handoff_hash"] = _stable_hash(
        {
            "current_guidance_action_payload": current_action,
            "selected_recommendation_proof_hash": summary["selected_recommendation_proof_hash"],
            "repair_blocked_reason_proof_hash": summary["repair_blocked_reason_proof_hash"],
            "selected_update_hash_surface": summary["selected_update_hash_surface"],
            "future_bottom_reo_cta_intent_projection": projected,
        }
    )
    return summary


def _assert_summary(scenario: str, summary: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    projected = dict(summary.get("future_bottom_reo_cta_intent_projection") or {})
    current_action = dict(summary.get("current_guidance_action_payload") or {})
    absence = dict(summary.get("absence_proof") or {})
    forbidden = list(projected.get("forbidden_fields_present") or [])
    if forbidden:
        failures.append("forbidden_future_intent_keys:" + ",".join(forbidden))
    for key, value in absence.items():
        if value is not True:
            failures.append(f"absence_proof_failed:{key}")
    if not summary.get("future_bottom_reo_cta_intent_proof_hash"):
        failures.append("missing_cta_intent_proof_hash")
    if not isinstance(summary.get("trace_emitted_bottom_reo_cta_intent_proof"), dict):
        failures.append("missing_trace_emitted_cta_intent_proof")
    if not summary.get("trace_emitted_bottom_reo_cta_intent_proof_hash_match"):
        failures.append("trace_emitted_cta_intent_proof_hash_mismatch")
    if not summary.get("trace_emitted_bottom_reo_cta_intent_shape_match"):
        failures.append("trace_emitted_cta_intent_shape_mismatch")
    if not summary.get("selected_recommendation_proof_hash"):
        failures.append("missing_selected_recommendation_proof_hash")
    if not summary.get("repair_blocked_reason_proof_hash"):
        failures.append("missing_repair_blocked_reason_proof_hash")
    if scenario == "zero_accepted_scenario":
        if current_action.get("materialized"):
            failures.append("zero_candidate_unexpected_action_payload")
        if projected.get("intent_state") != "trace_only_no_selection":
            failures.append(f"zero_candidate_wrong_intent_state:{projected.get('intent_state')!r}")
        no_action = dict(summary.get("no_action_blocked_proof_source") or {})
        tracked = dict(no_action.get("tracked_reasons") or {})
        if not tracked.get("no_filtered_candidates"):
            failures.append("zero_candidate_missing_no_filtered_candidates_source")
    else:
        if not current_action.get("materialized"):
            failures.append("selected_case_missing_action_payload")
        if current_action.get("action_type") not in {"apply_bottom_recommendation", "apply_compound_guidance"}:
            failures.append(f"unexpected_action_type:{current_action.get('action_type')!r}")
        if projected.get("intent_state") != "actionable_candidate":
            failures.append(f"selected_case_wrong_intent_state:{projected.get('intent_state')!r}")
        current_keys = list(current_action.get("update_keys") or [])
        selected_surface = dict(summary.get("selected_update_hash_surface") or {})
        proof_keys = list(selected_surface.get("proof_returned_update_keys") or [])
        if current_keys != proof_keys:
            failures.append(f"action_update_keys_do_not_match_proof:{current_keys!r}!={proof_keys!r}")
    return sorted(set(failures))


def _write_report(path: Path, snapshot: dict[str, Any]) -> None:
    lines = [
        "# Bottom Reo CTA/Action Intent Boundary Snapshot",
        "",
        f"- Status: {snapshot.get('status')}",
        f"- JSON artifact: `{snapshot.get('artifact_path')}`",
        f"- Trace artifact: `{snapshot.get('trace_path')}`",
        "",
        "## Scope",
        "",
        "Proof-only snapshot. It compares the current bottom-reo guidance action payload with a projected future family-owned CTA/action intent proof shape. It does not change product behaviour or make the proof product-driving.",
        "",
        "## Scenario Summary",
    ]
    scenarios = snapshot.get("scenarios") if isinstance(snapshot.get("scenarios"), dict) else {}
    stability = snapshot.get("stability") if isinstance(snapshot.get("stability"), dict) else {}
    for name, data in scenarios.items():
        action_identity = dict(data.get("action_apply_payload_identity") or {})
        projection = dict(data.get("future_bottom_reo_cta_intent_projection") or {})
        lines.extend(
            [
                "",
                f"### {name}",
                f"- return: `{data.get('return_status')}` / `{data.get('return_reason')}`",
                f"- selected identity: `{data.get('selected_recommendation_identity')}`",
                f"- action type: `{action_identity.get('action_type')}`",
                f"- action update keys: `{action_identity.get('update_keys')}`",
                f"- action payload hash: `{action_identity.get('payload_hash')}`",
                f"- selected proof hash: `{data.get('selected_recommendation_proof_hash')}`",
                f"- repair/blocked proof hash: `{data.get('repair_blocked_reason_proof_hash')}`",
                f"- projected intent state: `{projection.get('intent_state')}`",
                f"- projected CTA intent hash: `{data.get('future_bottom_reo_cta_intent_proof_hash')}`",
                f"- emitted CTA intent hash: `{data.get('trace_emitted_bottom_reo_cta_intent_proof_hash')}`",
                f"- emitted CTA intent hash match: `{data.get('trace_emitted_bottom_reo_cta_intent_proof_hash_match')}`",
                f"- handoff hash: `{data.get('scenario_cta_intent_handoff_hash')}`",
                f"- stability: `{stability.get(name, {})}`",
                f"- forbidden future intent keys: `{projection.get('forbidden_fields_present')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Absence Proof",
            "",
            "- final rendered button label: absent from projected family-owned intent",
            "- final enabled/disabled state from shared CTA precedence: absent from projected family-owned intent",
            "- shared source-precedence decision: absent",
            "- selected-family publication gate output: absent",
            "- visible wording: absent",
            "- one-click fallback routing: absent",
            "- render/UI/session/debug fields: absent",
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
    trace_path = TRACE_DIR / f"bottom_reo_cta_intent_boundary_trace_{stamp}.jsonl"
    artifact_path = ARTIFACT_DIR / f"bottom_reo_cta_intent_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"bottom_reo_cta_intent_boundary_{stamp}.md"

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
    scenarios: dict[str, dict[str, Any]] = {}
    stability: dict[str, dict[str, Any]] = {}
    failures: dict[str, list[str]] = {}
    proof_failures: list[str] = []
    for scenario in SCENARIOS:
        matching_payloads = _matching_return_payloads(rows, scenario)
        payload = matching_payloads[0] if matching_payloads else _return_payload(rows, scenario)
        if not payload:
            failures.setdefault(scenario, []).append("return_trace_missing")
            continue
        summary = _scenario_summary(
            scenario=scenario,
            result=results.get(scenario) or {},
            payload=payload,
            failures=proof_failures,
        )
        scenarios[scenario] = summary
        scenario_failures = _assert_summary(scenario, summary)

        repeat_payload = matching_payloads[-1] if matching_payloads else {}
        repeat_summary = _scenario_summary(
            scenario=scenario,
            result=repeat_results.get(scenario) or {},
            payload=repeat_payload if isinstance(repeat_payload, dict) else {},
            failures=proof_failures,
        )
        same_intent_hash = (
            summary.get("future_bottom_reo_cta_intent_proof_hash")
            == repeat_summary.get("future_bottom_reo_cta_intent_proof_hash")
        )
        same_handoff_hash = (
            summary.get("scenario_cta_intent_handoff_hash")
            == repeat_summary.get("scenario_cta_intent_handoff_hash")
        )
        stability[scenario] = {
            "same_cta_intent_proof_hash": same_intent_hash,
            "same_cta_intent_handoff_hash": same_handoff_hash,
            "first_cta_intent_proof_hash": summary.get("future_bottom_reo_cta_intent_proof_hash"),
            "repeat_cta_intent_proof_hash": repeat_summary.get("future_bottom_reo_cta_intent_proof_hash"),
            "first_cta_intent_handoff_hash": summary.get("scenario_cta_intent_handoff_hash"),
            "repeat_cta_intent_handoff_hash": repeat_summary.get("scenario_cta_intent_handoff_hash"),
        }
        if not same_intent_hash:
            scenario_failures.append("unstable_cta_intent_proof_hash")
        if not same_handoff_hash:
            scenario_failures.append("unstable_cta_intent_handoff_hash")
        if scenario_failures:
            failures[scenario] = sorted(set(scenario_failures))
    for failure in proof_failures:
        failures.setdefault("_proof", []).append(failure)
    for required in SCENARIOS:
        if required not in scenarios:
            failures.setdefault("_coverage", []).append(f"missing_{required}")

    status = "PASS" if not failures else "FAIL"
    snapshot = {
        "schema": "bottom_reo_cta_intent_boundary_snapshot.v1",
        "status": status,
        "generated_at": stamp,
        "artifact_path": str(artifact_path),
        "report_path": str(report_path),
        "trace_path": str(trace_path),
        "scenarios": scenarios,
        "stability": stability,
        "coverage": {
            "normal_bending_underdesign_with_action": "covered",
            "two_layer_arrangement_with_action": "covered",
            "zero_candidate_no_action": "covered",
            "blocked_no_action": "not_available_in_existing_bottom_reo_harness",
        },
        "assertions": {
            "product_behaviour_changed": False,
            "cta_action_logic_moved": False,
            "apply_routing_moved": False,
            "one_click_solver_logic_moved": False,
            "cta_source_precedence_moved": False,
            "selected_family_publication_gate_moved": False,
            "render_ui_session_debug_moved": False,
            "visible_wording_moved": False,
        },
        "forbidden_future_intent_keys": sorted(FORBIDDEN_FUTURE_INTENT_KEYS),
        "recommendation": (
            "Add a family-owned proof-only BottomReoCtaIntentProof or "
            "BottomReoRecommendationActionIntent next. Keep final CTA rendering, "
            "source precedence, selected-family publication gate, apply routing, "
            "one-click fallback, visible wording, and UI/session/debug ownership "
            "shared/page-owned."
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
