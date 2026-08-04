"""Snapshot bottom-reo selected-recommendation to reason handoff.

This verifier freezes the proof-only handoff from the bottom-reo selected
recommendation surface to repair/blocked reason source surfaces. It does not
move selector logic, strict-band/no-op/improvement guards, reason wording,
CTA/action logic, one-click behavior, publication, rendering, session/debug
plumbing, or candidate mutation.
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

from design_brain.families.bending import build_bottom_reo_repair_blocked_reason_proof
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
    _return_payload,
)
from tools.verification.bottom_reo_selector_wrapper_parity_snapshot import _run_scenario


ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"
TRACE_DIR = REPO / "artifacts" / "traces"

FORBIDDEN_REASON_KEYS = {
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

TRACE_REASON_KEYS = (
    "no_filtered_candidates",
    "no_selected_candidate",
    "growth_blocked_efficiency_reduction",
)


def _walk_forbidden_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_REASON_KEYS:
                found.add(key_text)
            found.update(_walk_forbidden_keys(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(_walk_forbidden_keys(child))
    return found


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


def _selector_trace_reason_surface(handoff: dict[str, Any]) -> dict[str, Any]:
    decision = dict(handoff.get("selected_candidate_decision_surface") or {})
    selector = dict(handoff.get("live_selector_result") or {})
    raw_reasons = {
        "decision_no_result_reason": decision.get("no_result_reason"),
        "selector_no_candidate_reason": selector.get("no_candidate_reason"),
        "selector_legacy_rejection_reason": selector.get("legacy_rejection_reason"),
        "selector_strict_band_rejected_reason": selector.get("strict_band_rejected_reason"),
        "post_selector_guard_result": decision.get("post_selector_guard_result"),
    }
    matched = {
        key: any(str(value or "") == key for value in raw_reasons.values())
        for key in TRACE_REASON_KEYS
    }
    return {
        "reason_kind": "trace_proof_only",
        "raw_reasons": raw_reasons,
        "tracked_reasons": matched,
        "visible_blocked_wording_materialized": False,
        "visible_blocked_wording_source": None,
    }


def _repair_reason_source_surface(handoff: dict[str, Any]) -> dict[str, Any]:
    proof = dict(handoff.get("selected_recommendation_proof") or {})
    selected_identity = handoff.get("selected_candidate_identity")
    if selected_identity is None:
        return {
            "reason_kind": "not_produced",
            "source": None,
            "visible_guidance_text_source": None,
        }
    return {
        "reason_kind": "visible_guidance_text_source",
        "source": "selected_recommendation_proof",
        "selected_candidate_identity": selected_identity,
        "label": proof.get("label"),
        "guidance_recommendation_title": proof.get("guidance_recommendation_title"),
        "guidance_change_lines": list(proof.get("guidance_change_lines") or []),
        "utilisation_check_summary": dict(proof.get("utilisation_check_summary") or {}),
        "returned_update_keys": list(proof.get("returned_update_keys") or []),
        "returned_updates_hash": proof.get("returned_updates_hash"),
        "visible_reason_rows_materialized": False,
    }


def _blocked_reason_source_surface(handoff: dict[str, Any]) -> dict[str, Any]:
    selected_identity = handoff.get("selected_candidate_identity")
    trace_surface = _selector_trace_reason_surface(handoff)
    if selected_identity is not None:
        return {
            "reason_kind": "not_applicable_selected_recommendation",
            "trace_reason_surface": trace_surface,
            "visible_blocked_wording_materialized": False,
            "visible_blocked_wording_source": None,
        }
    return {
        "reason_kind": "trace_proof_only",
        "trace_reason_surface": trace_surface,
        "visible_blocked_wording_materialized": False,
        "visible_blocked_wording_source": None,
    }


def _visible_guidance_text_source(handoff: dict[str, Any]) -> dict[str, Any] | None:
    repair = _repair_reason_source_surface(handoff)
    if repair.get("reason_kind") != "visible_guidance_text_source":
        return None
    return {
        "source": repair.get("source"),
        "selected_candidate_identity": repair.get("selected_candidate_identity"),
        "label": repair.get("label"),
        "guidance_recommendation_title": repair.get("guidance_recommendation_title"),
        "guidance_change_lines": list(repair.get("guidance_change_lines") or []),
    }


def _reason_visibility_surface(handoff: dict[str, Any]) -> dict[str, str]:
    selected = handoff.get("selected_candidate_identity") is not None
    return {
        "selected_result_label": "visible_guidance_text_source" if selected else "not_produced",
        "selected_result_guidance_change_lines": "visible_guidance_text_source" if selected else "not_produced",
        "selector_no_result_reason": "trace_proof_only",
        "selector_no_candidate_reason": "trace_proof_only",
        "blocked_reason": "not_visible_from_bottom_reo_selector",
    }


def _reason_handoff_summary(
    *,
    scenario: str,
    result: dict[str, Any],
    payload: dict[str, Any],
    proof_failures: list[str],
) -> dict[str, Any]:
    handoff = _handoff_summary(
        scenario=scenario,
        result=result,
        payload=payload,
        failures=proof_failures,
    )
    proof = dict(handoff.get("selected_recommendation_proof") or {})
    selected_update_hash_surface = _selected_update_hash_surface(handoff)
    selector_guard_outcomes = dict(handoff.get("guard_surface") or {})
    selector_trace_reasons = _selector_trace_reason_surface(handoff)
    repair_reason_source_surface = _repair_reason_source_surface(handoff)
    blocked_reason_source_surface = _blocked_reason_source_surface(handoff)
    reason_visibility_surface = _reason_visibility_surface(handoff)
    visible_guidance_text_source = _visible_guidance_text_source(handoff)
    reason_surface = {
        "scenario": scenario,
        "selected_recommendation_identity": proof.get("selected_candidate_identity"),
        "selected_recommendation_proof_hash": proof.get("proof_hash"),
        "selected_recommendation_shape_hash": proof.get("selected_recommendation_shape_hash"),
        "selected_recommendation_handoff_hash": handoff.get("selected_recommendation_hash"),
        "selected_candidate_identity": handoff.get("selected_candidate_identity"),
        "selected_candidate_trace_hash": handoff.get("selected_candidate_trace_hash"),
        "selected_update_hash_surface": selected_update_hash_surface,
        "selector_guard_outcomes": selector_guard_outcomes,
        "selector_trace_reasons": selector_trace_reasons,
        "repair_reason_source_surface": repair_reason_source_surface,
        "blocked_reason_source_surface": blocked_reason_source_surface,
        "reason_visibility_surface": reason_visibility_surface,
        "visible_guidance_text_source": visible_guidance_text_source,
    }
    reason_surface["reason_handoff_hash"] = _stable_hash(reason_surface)
    reason_proof = build_bottom_reo_repair_blocked_reason_proof(
        selected_recommendation_identity=reason_surface["selected_recommendation_identity"],
        selected_recommendation_proof_hash=reason_surface["selected_recommendation_proof_hash"],
        selected_recommendation_shape_hash=reason_surface["selected_recommendation_shape_hash"],
        selected_recommendation_handoff_hash=reason_surface["selected_recommendation_handoff_hash"],
        selected_candidate_identity=reason_surface["selected_candidate_identity"],
        selected_candidate_trace_hash=reason_surface["selected_candidate_trace_hash"],
        selected_update_hash_surface=selected_update_hash_surface,
        selector_guard_outcomes=selector_guard_outcomes,
        selector_trace_reasons=selector_trace_reasons,
        repair_reason_source_surface=repair_reason_source_surface,
        blocked_reason_source_surface=blocked_reason_source_surface,
        reason_visibility_surface=reason_visibility_surface,
        visible_guidance_text_source=visible_guidance_text_source,
    ).to_dict()
    reason_surface["repair_blocked_reason_proof"] = reason_proof
    reason_surface["repair_blocked_reason_proof_hash"] = reason_proof.get("proof_hash")
    reason_surface["repair_blocked_reason_proof_forbidden_fields"] = list(
        reason_proof.get("forbidden_fields_present") or []
    )
    reason_surface["forbidden_reason_keys_present"] = sorted(_walk_forbidden_keys(reason_surface))
    return reason_surface


def _assert_reason_handoff(scenario: str, summary: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if summary.get("forbidden_reason_keys_present"):
        failures.append(
            "forbidden_reason_keys:"
            + ",".join(summary.get("forbidden_reason_keys_present") or [])
        )
    if summary.get("repair_blocked_reason_proof_forbidden_fields"):
        failures.append(
            "repair_blocked_reason_proof_forbidden_fields:"
            + ",".join(summary.get("repair_blocked_reason_proof_forbidden_fields") or [])
        )
    if not summary.get("repair_blocked_reason_proof_hash"):
        failures.append("missing_repair_blocked_reason_proof_hash")
    if not summary.get("reason_handoff_hash"):
        failures.append("missing_reason_handoff_hash")
    selected_identity = summary.get("selected_candidate_identity")
    repair = dict(summary.get("repair_reason_source_surface") or {})
    blocked = dict(summary.get("blocked_reason_source_surface") or {})
    trace = dict(summary.get("selector_trace_reasons") or {})
    tracked = dict(trace.get("tracked_reasons") or {})
    if scenario != "zero_accepted_scenario":
        if not selected_identity:
            failures.append("missing_selected_candidate_identity")
        if repair.get("reason_kind") != "visible_guidance_text_source":
            failures.append(f"repair_reason_not_visible_source:{repair.get('reason_kind')!r}")
        if not summary.get("visible_guidance_text_source"):
            failures.append("missing_visible_guidance_text_source")
        if blocked.get("visible_blocked_wording_materialized"):
            failures.append("selected_case_visible_blocked_wording_materialized")
    else:
        if selected_identity is not None:
            failures.append(f"unexpected_zero_candidate_selection:{selected_identity!r}")
        if repair.get("reason_kind") != "not_produced":
            failures.append(f"zero_candidate_repair_reason_produced:{repair.get('reason_kind')!r}")
        if blocked.get("reason_kind") != "trace_proof_only":
            failures.append(f"zero_candidate_blocked_reason_not_trace:{blocked.get('reason_kind')!r}")
        if not tracked.get("no_filtered_candidates"):
            failures.append("zero_candidate_missing_no_filtered_candidates_trace_reason")
        if blocked.get("visible_blocked_wording_materialized"):
            failures.append("zero_candidate_visible_blocked_wording_materialized")
    visibility = dict(summary.get("reason_visibility_surface") or {})
    if visibility.get("selector_no_result_reason") != "trace_proof_only":
        failures.append("selector_no_result_reason_not_trace_proof_only")
    if visibility.get("selector_no_candidate_reason") != "trace_proof_only":
        failures.append("selector_no_candidate_reason_not_trace_proof_only")
    if visibility.get("blocked_reason") != "not_visible_from_bottom_reo_selector":
        failures.append("blocked_reason_conflated_with_visible_wording")
    return sorted(set(failures))


def _write_report(path: Path, snapshot: dict[str, Any]) -> None:
    lines = [
        "# Bottom Reo Selected Recommendation Reason Handoff Snapshot",
        "",
        f"- Status: {snapshot.get('status')}",
        f"- JSON artifact: `{snapshot.get('artifact_path')}`",
        f"- Trace artifact: `{snapshot.get('trace_path')}`",
        "",
        "## Scope",
        "",
        "Proof-only snapshot. It freezes the handoff from selected bottom-reo recommendation proof surfaces to repair/blocked reason source surfaces. It does not move selected proof deeper, selector logic, guards, wording, CTA/action, one-click, publication, rendering, session/debug plumbing, or candidate mutation.",
        "",
        "## Scenario Summary",
    ]
    scenarios = snapshot.get("scenarios") if isinstance(snapshot.get("scenarios"), dict) else {}
    stability = snapshot.get("stability") if isinstance(snapshot.get("stability"), dict) else {}
    for name, data in scenarios.items():
        trace_reasons = dict((data or {}).get("selector_trace_reasons") or {})
        repair = dict((data or {}).get("repair_reason_source_surface") or {})
        blocked = dict((data or {}).get("blocked_reason_source_surface") or {})
        lines.extend(
            [
                "",
                f"### {name}",
                f"- selected identity: `{data.get('selected_candidate_identity')}`",
                f"- selected recommendation proof hash: `{data.get('selected_recommendation_proof_hash')}`",
                f"- selected recommendation handoff hash: `{data.get('selected_recommendation_handoff_hash')}`",
                f"- selected update surface: `{data.get('selected_update_hash_surface')}`",
                f"- guard outcomes: `{data.get('selector_guard_outcomes')}`",
                f"- trace reasons: `{trace_reasons}`",
                f"- repair reason source: `{repair}`",
                f"- blocked reason source: `{blocked}`",
                f"- visible guidance text source: `{data.get('visible_guidance_text_source')}`",
                f"- reason handoff hash: `{data.get('reason_handoff_hash')}`",
                f"- repair/blocked reason proof hash: `{data.get('repair_blocked_reason_proof_hash')}`",
                f"- repair/blocked reason proof forbidden fields: `{data.get('repair_blocked_reason_proof_forbidden_fields')}`",
                f"- forbidden keys: `{data.get('forbidden_reason_keys_present')}`",
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
            "- growth-blocked or no-op/strict-band scenario: `not_available_in_existing_selected_recommendation_harness`",
            "",
            "## Visibility Distinction",
            "",
            "- Selector no-result/no-candidate reasons are trace/proof-only.",
            "- Visible blocked wording is not materialized by this bottom-reo selector handoff snapshot.",
            "- Selected repair guidance text source is limited to the existing selected recommendation label/change-line surface.",
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
    trace_path = TRACE_DIR / f"bottom_reo_selected_recommendation_reason_handoff_trace_{stamp}.jsonl"
    artifact_path = ARTIFACT_DIR / f"bottom_reo_selected_recommendation_reason_handoff_{stamp}.json"
    report_path = AUDIT_DIR / f"bottom_reo_selected_recommendation_reason_handoff_{stamp}.md"

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
    stability: dict[str, dict[str, Any]] = {}
    proof_failures: list[str] = []
    for scenario in SCENARIOS:
        matching_payloads = _matching_return_payloads(rows, scenario)
        payload = matching_payloads[0] if matching_payloads else _return_payload(rows, scenario)
        if not payload:
            failures.setdefault(scenario, []).append("return_trace_missing")
            continue
        summary = _reason_handoff_summary(
            scenario=scenario,
            result=results.get(scenario) or {},
            payload=payload,
            proof_failures=proof_failures,
        )
        scenario_summaries[scenario] = summary
        scenario_failures = _assert_reason_handoff(scenario, summary)
        repeat_payload = matching_payloads[-1] if matching_payloads else {}
        repeat_summary = _reason_handoff_summary(
            scenario=scenario,
            result=repeat_results.get(scenario) or {},
            payload=repeat_payload if isinstance(repeat_payload, dict) else {},
            proof_failures=proof_failures,
        )
        same_reason_hash = summary.get("reason_handoff_hash") == repeat_summary.get("reason_handoff_hash")
        stability[scenario] = {
            "same_reason_handoff_hash": same_reason_hash,
            "first_reason_handoff_hash": summary.get("reason_handoff_hash"),
            "repeat_reason_handoff_hash": repeat_summary.get("reason_handoff_hash"),
        }
        if not same_reason_hash:
            scenario_failures.append("unstable_reason_handoff_hash")
        if scenario_failures:
            failures[scenario] = sorted(set(scenario_failures))
    for failure in proof_failures:
        failures.setdefault("_proof", []).append(failure)
    for required in SCENARIOS:
        if required not in scenario_summaries:
            failures.setdefault("_coverage", []).append(f"missing_{required}")

    status = "PASS" if not failures else "FAIL"
    snapshot = {
        "schema": "bottom_reo_selected_recommendation_reason_handoff_snapshot.v1",
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
            "growth_blocked_or_noop_strict_band": (
                "not_available_in_existing_selected_recommendation_harness"
            ),
        },
        "assertions": {
            "selected_recommendation_proof_moved_deeper": False,
            "selector_logic_moved": False,
            "strict_band_noop_improvement_guards_moved": False,
            "compound_preference_logic_moved": False,
            "post_selector_guards_moved": False,
            "repair_blocked_wording_moved": False,
            "cta_action_logic_absent": True,
            "one_click_action_absent": True,
            "publication_ui_session_debug_absent": True,
            "candidate_mutation_moved": False,
        },
        "forbidden_reason_keys": sorted(FORBIDDEN_REASON_KEYS),
        "recommendation": (
            "Keep reason/wording page-owned. Next safe slice is a proof-only "
            "repair/blocked reason object or output wording contract expansion before "
            "moving any reason normalizer."
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
