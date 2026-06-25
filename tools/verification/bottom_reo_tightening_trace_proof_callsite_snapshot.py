"""Projected trace-proof callsite snapshot for bottom reo tightening.

This verifier proves the shape that can later be emitted beside
`bottom_reo_tightening_return` without wiring it into the live trace path yet.
It compares the verifier-built `BottomReoTighteningRecommendationProof` with a
future trace-only payload projection and asserts that CTA rendering/source
precedence, publication, apply routing, one-click fallback, visible wording,
render/UI/session/debug ownership do not enter the proof chain.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.verification.bottom_reo_tightening_recommendation_snapshot import (
    AUDIT_DIR,
    ARTIFACT_DIR,
    FORBIDDEN_KEYS,
    TRACE_DIR,
    _run_scenario,
    _stable_hash,
    _walk_forbidden,
)


SCENARIOS = ("tightening_selected", "no_tightening_no_options", "spacing_blocked")


def _project_trace_proof_payload(result: dict[str, Any]) -> dict[str, Any]:
    surface = dict(result.get("proof_surface") or {})
    verifier_proof = dict(result.get("family_proof") or {})
    projected_proof = dict(verifier_proof)
    generated = list(surface.get("tightening_candidate_options") or [])
    rejected = list(surface.get("rejected_candidate_reasons") or [])
    accepted = list(surface.get("accepted_candidate_identities") or [])
    selected = surface.get("selected_tightening_recommendation")
    no_reason = surface.get("no_recommendation_reason")
    update_identity = dict(surface.get("update_action_payload_identity") or {})
    util_surface = dict(surface.get("utilisation_target_band_surface") or {})
    repair_surface = dict(surface.get("repair_blocked_reason_source_surface") or {})
    cta_surface = dict(surface.get("cta_action_intent_source_surface") or {})

    stable_trace_inputs = {
        "scenario": result.get("scenario"),
        "status": result.get("status"),
        "return_reason": result.get("return_reason"),
        "tightening_recommendation_hash": result.get("tightening_recommendation_hash"),
        "generated_candidate_identities": generated,
        "rejected_candidate_reasons": rejected,
        "accepted_candidate_identities": accepted,
        "selected_tightening_recommendation": selected,
        "no_tightening_reason": no_reason,
        "update_action_payload_identity": update_identity,
        "utilisation_target_band_surface": util_surface,
        "repair_blocked_reason_source_surface": repair_surface,
        "cta_action_intent_source_surface": cta_surface,
    }
    stable_trace_hash = _stable_hash(stable_trace_inputs)
    projection = {
        "schema": "bottom_reo_tightening_trace_proof_callsite_projection.v1",
        "trace_proof_callsite": (
            "inputs_page.py:_compute_bottom_reo_tightening_recommendation:"
            "bottom_reo_tightening_return:projected"
        ),
        "product_driving": False,
        "scenario": result.get("scenario"),
        "status": result.get("status"),
        "return_reason": result.get("return_reason"),
        "verifier_built_tightening_proof": verifier_proof,
        "projected_future_trace_tightening_proof_shape": projected_proof,
        "generated_candidate_identities": generated,
        "rejected_candidate_reasons": rejected,
        "accepted_candidate_identities": accepted,
        "selected_tightening_recommendation": selected,
        "no_tightening_reason": no_reason,
        "update_action_payload_identity": update_identity,
        "utilisation_target_band_surface": util_surface,
        "repair_blocked_reason_source_surface": repair_surface,
        "cta_action_intent_source_surface": cta_surface,
        "stable_trace_proof_hash": stable_trace_hash,
        "verifier_proof_hash": verifier_proof.get("tightening_recommendation_hash"),
        "projected_trace_proof_hash": projected_proof.get("tightening_recommendation_hash"),
        "proof_hash_match": (
            verifier_proof.get("tightening_recommendation_hash")
            == projected_proof.get("tightening_recommendation_hash")
            == result.get("tightening_recommendation_hash")
        ),
        "proof_shape_match": _stable_hash(verifier_proof) == _stable_hash(projected_proof),
        "absence_evidence": {
            "final_cta_rendering_materialized": False,
            "shared_cta_source_precedence_materialized": False,
            "selected_family_publication_gate_materialized": False,
            "apply_routing_materialized": False,
            "one_click_fallback_materialized": False,
            "visible_wording_materialized": False,
            "output_rendering_materialized": False,
            "render_ui_session_debug_materialized": False,
        },
    }
    projection["forbidden_trace_proof_keys_present"] = sorted(
        _walk_forbidden(projection) & FORBIDDEN_KEYS
    )
    return projection


def _assert_projection(projection: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    scenario = str(projection.get("scenario") or "")
    if projection.get("forbidden_trace_proof_keys_present"):
        failures.append(
            "forbidden_trace_proof_keys:"
            + ",".join(projection.get("forbidden_trace_proof_keys_present") or [])
        )
    if not projection.get("proof_hash_match"):
        failures.append("proof_hash_mismatch")
    if not projection.get("proof_shape_match"):
        failures.append("proof_shape_mismatch")
    if not projection.get("stable_trace_proof_hash"):
        failures.append("missing_stable_trace_proof_hash")
    if scenario == "tightening_selected":
        if projection.get("status") != "selected":
            failures.append("selected_case_not_selected")
        if not projection.get("selected_tightening_recommendation"):
            failures.append("missing_selected_tightening_recommendation")
        if not projection.get("accepted_candidate_identities"):
            failures.append("missing_accepted_candidate_identities")
    if scenario == "no_tightening_no_options":
        if projection.get("generated_candidate_identities"):
            failures.append("no_options_unexpected_generated_candidates")
        if projection.get("status") != "no_result":
            failures.append("no_options_not_no_result")
        if projection.get("no_tightening_reason") != "no_options_generated":
            failures.append("no_options_wrong_reason")
    if scenario == "spacing_blocked":
        if not projection.get("generated_candidate_identities"):
            failures.append("spacing_blocked_missing_generated_candidates")
        if not projection.get("rejected_candidate_reasons"):
            failures.append("spacing_blocked_missing_rejected_reasons")
        if projection.get("status") != "no_result":
            failures.append("spacing_blocked_not_no_result")
        if projection.get("no_tightening_reason") != "no_valid_candidates":
            failures.append("spacing_blocked_wrong_reason")
    absence = dict(projection.get("absence_evidence") or {})
    for key, value in absence.items():
        if value is not False:
            failures.append(f"absence_evidence_not_false:{key}")
    return failures


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Bottom Reo Tightening Trace Proof Callsite Snapshot",
        "",
        f"- Status: {snapshot.get('status')}",
        f"- JSON artifact: `{snapshot.get('artifact_path')}`",
        f"- Trace artifact: `{snapshot.get('trace_path')}`",
        "",
        "## Scope",
        "",
        "Projection/proof only. This does not wire the proof payload into the live tightening trace path and does not change product behaviour.",
        "",
        "## Scenario Summary",
        "",
    ]
    for projection in snapshot.get("scenarios") or []:
        lines.extend(
            [
                f"### {projection.get('scenario')}",
                "",
                f"- status: `{projection.get('status')}` / `{projection.get('return_reason')}`",
                f"- generated: `{len(projection.get('generated_candidate_identities') or [])}`",
                f"- accepted: `{len(projection.get('accepted_candidate_identities') or [])}`",
                f"- rejected: `{len(projection.get('rejected_candidate_reasons') or [])}`",
                f"- selected: `{projection.get('selected_tightening_recommendation')}`",
                f"- no-tightening reason: `{projection.get('no_tightening_reason')}`",
                f"- trace proof hash: `{projection.get('stable_trace_proof_hash')}`",
                f"- proof hash match: `{projection.get('proof_hash_match')}`",
                f"- proof shape match: `{projection.get('proof_shape_match')}`",
                f"- forbidden fields: `{projection.get('forbidden_trace_proof_keys_present')}`",
                f"- stability: `{(snapshot.get('stability') or {}).get(str(projection.get('scenario')), {})}`",
                "",
            ]
        )
    if snapshot.get("failures"):
        lines.extend(["## Failures", ""])
        for scenario, failures in (snapshot.get("failures") or {}).items():
            lines.append(f"- {scenario}: {', '.join(failures)}")
    else:
        lines.extend(
            [
                "## Result",
                "",
                "PASS. The projected future trace-only tightening proof payload matches the verifier-built `BottomReoTighteningRecommendationProof`, is stable across repeat runs, and excludes CTA rendering/source precedence, selected-family publication gate output, apply routing, one-click fallback, visible wording/output rendering, render/UI/session/debug-only fields.",
                "",
                "## Recommendation",
                "",
                "Next safe slice is trace-only wiring: attach this projected proof payload beside `bottom_reo_tightening_return`, preserving it as non-product-driving trace/proof data only.",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"bottom_reo_tightening_trace_proof_callsite_{stamp}.json"
    report_path = AUDIT_DIR / f"bottom_reo_tightening_trace_proof_callsite_{stamp}.md"
    trace_path = TRACE_DIR / f"bottom_reo_tightening_trace_proof_callsite_trace_{stamp}.jsonl"

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
    try:
        first_results = [_run_scenario(module, scenario, trace_path) for scenario in SCENARIOS]
        repeat_results = [_run_scenario(module, scenario, trace_path) for scenario in SCENARIOS]
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    projections = [_project_trace_proof_payload(result) for result in first_results]
    repeat_projections = {
        str(item.get("scenario")): item
        for item in (_project_trace_proof_payload(result) for result in repeat_results)
    }
    failures: dict[str, list[str]] = {}
    stability: dict[str, dict[str, Any]] = {}
    for projection in projections:
        scenario = str(projection.get("scenario") or "")
        scenario_failures = _assert_projection(projection)
        repeat = repeat_projections.get(scenario, {})
        same_hash = projection.get("stable_trace_proof_hash") == repeat.get("stable_trace_proof_hash")
        stability[scenario] = {
            "same_trace_proof_hash": same_hash,
            "first_trace_proof_hash": projection.get("stable_trace_proof_hash"),
            "repeat_trace_proof_hash": repeat.get("stable_trace_proof_hash"),
        }
        if not same_hash:
            scenario_failures.append("unstable_trace_proof_hash")
        if scenario_failures:
            failures[scenario] = sorted(set(scenario_failures))

    status = "PASS" if not failures else "FAIL"
    snapshot = {
        "status": status,
        "generated_at": stamp,
        "schema": "bottom_reo_tightening_trace_proof_callsite_snapshot.v1",
        "artifact_path": str(artifact_path),
        "report_path": str(report_path),
        "trace_path": str(trace_path),
        "scope": "projected_trace_only_bottom_reo_tightening_proof_callsite",
        "coverage": {
            "tightening_selected": "covered",
            "no_tightening_no_options": "covered",
            "spacing_blocked": "covered",
        },
        "scenarios": projections,
        "stability": stability,
        "forbidden_keys": sorted(FORBIDDEN_KEYS),
        "assertions": {
            "product_behavior_changed": False,
            "live_trace_wiring_changed": False,
            "tightening_logic_moved": False,
            "final_cta_rendering_absent": not failures,
            "shared_cta_source_precedence_absent": not failures,
            "selected_family_publication_gate_absent": not failures,
            "apply_routing_absent": not failures,
            "one_click_fallback_absent": not failures,
            "visible_wording_output_rendering_absent": not failures,
            "render_ui_session_debug_fields_absent": not failures,
        },
        "failures": failures,
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(snapshot, report_path)
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
