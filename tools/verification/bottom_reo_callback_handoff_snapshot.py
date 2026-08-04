"""Snapshot bottom reo live callback handoff parity.

This verifier proves the page-owned callbacks passed into
``_keep_top_candidates_core(...)`` match the typed family-owned bottom reo
sort/dominance policy surfaces. It does not replace live callbacks, move
ranking sort/prune execution, select a recommendation, build CTA/action
payloads, publish, render UI, touch session/debug state, or execute evaluators
outside the existing focused fixture harness.
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
from tools.verification import bottom_reo_callback_policy_parity_snapshot as parity_snapshot


ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"
TRACE_DIR = REPO / "artifacts" / "traces"

HANDOFF_SCENARIO_NAMES = {
    "balanced_normal_bending_underdesign",
    "two_layer_arrangement",
    "zero_candidate_cleanup",
}

FORBIDDEN_HANDOFF_KEYS = {
    "action_payload",
    "action_type",
    "button_contract",
    "cta",
    "debug",
    "final_selected_repair",
    "one_click",
    "publication",
    "render",
    "selected_recommendation",
    "session_state",
    "ui",
}


def _stable_hash(value: Any) -> str:
    return parity_snapshot._stable_hash(value)


def _scenario_definitions() -> list[dict[str, Any]]:
    return [
        definition
        for definition in parity_snapshot.SCENARIOS
        if str(definition.get("name") or "") in HANDOFF_SCENARIO_NAMES
    ]


def _handoff_result(result: dict[str, Any]) -> dict[str, Any]:
    live_ordered = list(result.get("live_ordered_identities") or [])
    typed_ordered = list(result.get("typed_policy_ordered_identities") or [])
    live_kept = list(result.get("live_kept_identities") or [])
    typed_kept = list(result.get("typed_policy_kept_identities") or [])
    live_pruned = list(result.get("live_pruned_identities") or [])
    typed_pruned = list(result.get("typed_policy_pruned_identities") or [])
    policy_inputs = list(result.get("policy_inputs") or [])
    live_sort = dict(result.get("live_sort_key_by_identity") or {})
    typed_sort = dict(result.get("typed_policy_sort_key_by_identity") or {})
    live_dominance = list(result.get("live_dominance_decisions") or [])
    typed_dominance = list(result.get("typed_policy_dominance_decisions") or [])
    handoff_surface = {
        "candidate_identities": list(result.get("candidate_identities") or []),
        "policy_input_hashes": [
            str(record.get("policy_input_hash") or "")
            for record in policy_inputs
            if isinstance(record, dict)
        ],
        "live_sort": live_sort,
        "typed_sort": typed_sort,
        "live_dominance": live_dominance,
        "typed_dominance": typed_dominance,
        "live_ordered": live_ordered,
        "typed_ordered": typed_ordered,
        "live_kept": live_kept,
        "typed_kept": typed_kept,
        "live_pruned": live_pruned,
        "typed_pruned": typed_pruned,
    }
    ordered_hash = _stable_hash({"live": live_ordered, "typed": typed_ordered})
    kept_hash = _stable_hash({"live": live_kept, "typed": typed_kept})
    pruned_hash = _stable_hash({"live": live_pruned, "typed": typed_pruned})
    handoff_hash = _stable_hash(handoff_surface)
    parity = dict(result.get("parity") or {})
    mismatches = dict(result.get("mismatches") or {})
    decision_summaries = [
        {
            "candidate_identity": identity,
            "decision": "kept",
        }
        for identity in live_kept
    ] + [
        {
            "candidate_identity": identity,
            "decision": "discarded_by_live_core",
            "reason": "pruned_or_limited_by_live_core",
        }
        for identity in live_pruned
    ]
    ranking_result_boundary = build_bottom_reo_ranking_result_boundary(
        policy_inputs=policy_inputs,
        ordered_identities=live_ordered,
        kept_identities=live_kept,
        pruned_identities=live_pruned,
        ranking_decisions=decision_summaries,
        ordered_hash=ordered_hash,
        kept_hash=kept_hash,
        pruned_hash=pruned_hash,
        callback_handoff_hash=handoff_hash,
    ).to_dict()
    return {
        "scenario": result.get("scenario"),
        "mode": result.get("mode"),
        "mutator": result.get("mutator"),
        "candidate_count": int(result.get("candidate_count") or 0),
        "candidate_identities_before_core_handoff": list(result.get("candidate_identities") or []),
        "callback_policy_input_source": "BottomReoRankingPolicyInput-equivalent surfaces",
        "typed_policy_input_builder": "design_brain.families.bending.build_bottom_reo_ranking_policy_inputs",
        "typed_family_policy_helpers": {
            "sort": "design_brain.families.bending.bottom_reo_sort_key_from_policy_surface",
            "dominance": "design_brain.families.bending.bottom_reo_dominance_from_policy_surface",
        },
        "policy_inputs": policy_inputs,
        "live_page_sort_callback_result_by_identity": live_sort,
        "typed_family_policy_sort_result_by_identity": typed_sort,
        "live_page_dominance_callback_decisions": live_dominance,
        "typed_family_policy_dominance_decisions": typed_dominance,
        "ordered_identities_after_live_sort": live_ordered,
        "ordered_identities_after_typed_policy_replay": typed_ordered,
        "kept_identities_after_live_pruning": live_kept,
        "kept_identities_after_typed_policy_replay": typed_kept,
        "pruned_identities_and_reasons": [
            {
                "candidate_identity": identity,
                "reason": "discarded_by_live_core",
            }
            for identity in live_pruned
        ],
        "typed_policy_pruned_identities": typed_pruned,
        "ordered_hash": ordered_hash,
        "kept_hash": kept_hash,
        "pruned_hash": pruned_hash,
        "handoff_hash": handoff_hash,
        "parity_hash": result.get("parity_hash"),
        "ranking_result_boundary": ranking_result_boundary,
        "ranking_result_boundary_hash": ranking_result_boundary.get("ranking_result_hash"),
        "parity": {
            "sort_results_match": bool(parity.get("sort_keys_match")),
            "dominance_results_match": bool(parity.get("dominance_decisions_match")),
            "ordered_identities_match": bool(parity.get("ordered_identities_match")),
            "kept_identities_match": bool(parity.get("kept_identities_match")),
            "pruned_identities_match": bool(parity.get("pruned_identities_match")),
            "dedupe_keys_match": bool(parity.get("dedupe_keys_match")),
        },
        "mismatches": mismatches,
        "forbidden_keys_present": sorted(
            set(result.get("forbidden_keys_present") or []) & FORBIDDEN_HANDOFF_KEYS
        ),
        "source_boundary": dict(result.get("boundary") or {}),
    }


def _assert_handoff(result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if result.get("forbidden_keys_present"):
        failures.append(
            "forbidden_handoff_keys:" + ",".join(result.get("forbidden_keys_present") or [])
        )
    if result.get("candidate_count", 0) > 0:
        if not result.get("live_page_sort_callback_result_by_identity"):
            failures.append("missing_live_sort_callback_results")
        if not result.get("typed_family_policy_sort_result_by_identity"):
            failures.append("missing_typed_policy_sort_results")
    parity = dict(result.get("parity") or {})
    for key in (
        "sort_results_match",
        "dominance_results_match",
        "ordered_identities_match",
        "kept_identities_match",
        "pruned_identities_match",
    ):
        if not bool(parity.get(key)):
            failures.append(f"handoff_parity_failed:{key}")
    for key in ("ordered_hash", "kept_hash", "handoff_hash"):
        if not result.get(key):
            failures.append(f"missing_{key}")
    boundary = result.get("ranking_result_boundary") if isinstance(result.get("ranking_result_boundary"), dict) else {}
    if not boundary:
        failures.append("missing_ranking_result_boundary")
    else:
        if boundary.get("ordered_hash") != result.get("ordered_hash"):
            failures.append("ranking_result_boundary_ordered_hash_mismatch")
        if boundary.get("kept_hash") != result.get("kept_hash"):
            failures.append("ranking_result_boundary_kept_hash_mismatch")
        if boundary.get("pruned_hash") != result.get("pruned_hash"):
            failures.append("ranking_result_boundary_pruned_hash_mismatch")
        if boundary.get("callback_handoff_hash") != result.get("handoff_hash"):
            failures.append("ranking_result_boundary_handoff_hash_mismatch")
        forbidden = list(boundary.get("forbidden_fields_present") or [])
        if forbidden:
            failures.append("ranking_result_boundary_forbidden_fields:" + ",".join(forbidden))
        if not boundary.get("ranking_result_hash"):
            failures.append("missing_ranking_result_boundary_hash")
    return sorted(set(failures))


def main() -> int:
    module = importlib.import_module("inputs_page")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"bottom_reo_callback_handoff_{stamp}.jsonl"
    artifact_path = ARTIFACT_DIR / f"bottom_reo_callback_handoff_{stamp}.json"
    report_path = AUDIT_DIR / f"bottom_reo_callback_handoff_{stamp}.md"

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
        scenario_results = [
            _handoff_result(parity_snapshot._run_scenario(module, definition, trace_path))
            for definition in _scenario_definitions()
        ]
        repeat_results = [
            _handoff_result(parity_snapshot._run_scenario(module, definition, trace_path))
            for definition in _scenario_definitions()
        ]
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    repeats = {str(result.get("scenario")): result for result in repeat_results}
    failures: dict[str, list[str]] = {}
    stability: dict[str, dict[str, Any]] = {}
    zero_candidate_seen = False
    for result in scenario_results:
        scenario = str(result.get("scenario") or "")
        scenario_failures = _assert_handoff(result)
        repeat = repeats.get(scenario, {})
        same_ordered = result.get("ordered_hash") == repeat.get("ordered_hash")
        same_kept = result.get("kept_hash") == repeat.get("kept_hash")
        same_handoff = result.get("handoff_hash") == repeat.get("handoff_hash")
        stability[scenario] = {
            "same_ordered_hash": same_ordered,
            "same_kept_hash": same_kept,
            "same_handoff_hash": same_handoff,
            "first_ordered_hash": result.get("ordered_hash"),
            "repeat_ordered_hash": repeat.get("ordered_hash"),
            "first_kept_hash": result.get("kept_hash"),
            "repeat_kept_hash": repeat.get("kept_hash"),
            "first_handoff_hash": result.get("handoff_hash"),
            "repeat_handoff_hash": repeat.get("handoff_hash"),
        }
        if int(result.get("candidate_count") or 0) == 0:
            zero_candidate_seen = True
        if not same_ordered:
            scenario_failures.append("unstable_ordered_hash")
        if not same_kept:
            scenario_failures.append("unstable_kept_hash")
        if not same_handoff:
            scenario_failures.append("unstable_handoff_hash")
        if scenario_failures:
            failures[scenario] = sorted(set(scenario_failures))
    if not zero_candidate_seen:
        failures.setdefault("_coverage", []).append("missing_zero_accepted_scenario")

    status = "PASS" if not failures else "FAIL"
    snapshot = {
        "status": status,
        "generated_at": stamp,
        "trace_path": str(trace_path),
        "scenarios": scenario_results,
        "stability": stability,
        "forbidden_handoff_keys": sorted(FORBIDDEN_HANDOFF_KEYS),
        "assertions": {
            "live_callbacks_replaced": False,
            "keep_top_candidates_moved": False,
            "keep_top_candidates_core_moved": False,
            "ranking_sort_prune_execution_moved": False,
            "selection_cta_one_click_publication_absent": not any(
                set(result.get("forbidden_keys_present") or []) & FORBIDDEN_HANDOFF_KEYS
                for result in scenario_results
            ),
            "callback_policy_inputs_from_bottom_reo_ranking_policy_input_equivalent_surfaces": all(
                result.get("callback_policy_input_source")
                == "BottomReoRankingPolicyInput-equivalent surfaces"
                for result in scenario_results
            ),
        },
        "failures": failures,
    }
    artifact_path.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )

    lines = [
        "# Bottom Reo Callback Handoff Snapshot",
        "",
        f"- Status: {status}",
        f"- JSON artifact: `{artifact_path}`",
        f"- Trace artifact: `{trace_path}`",
        "",
        "## Scope",
        "",
        "Proof-only snapshot. It compares live page callbacks passed into `_keep_top_candidates_core(...)` against typed family-owned bottom reo policy surfaces. It does not replace callbacks or move ranking execution.",
        "",
        "## Scenario Summary",
    ]
    for result in scenario_results:
        scenario = str(result.get("scenario") or "")
        lines.extend(
            [
                "",
                f"### {scenario}",
                f"- candidate count: {result.get('candidate_count')}",
                f"- ordered hash: `{result.get('ordered_hash')}`",
                f"- kept hash: `{result.get('kept_hash')}`",
                f"- handoff hash: `{result.get('handoff_hash')}`",
                f"- ranking result boundary hash: `{result.get('ranking_result_boundary_hash')}`",
                f"- parity: `{result.get('parity')}`",
                f"- mismatches: `{result.get('mismatches')}`",
                f"- forbidden keys present: `{result.get('forbidden_keys_present')}`",
                f"- boundary forbidden fields: `{(result.get('ranking_result_boundary') or {}).get('forbidden_fields_present')}`",
                f"- stability: `{stability.get(scenario, {})}`",
            ]
        )
    if failures:
        lines.extend(["", "## Failures", ""])
        for scenario, scenario_failures in failures.items():
            lines.append(f"- {scenario}: {', '.join(scenario_failures)}")
        lines.extend(
            [
                "",
                "## Recommendation",
                "",
                "Do not move callback policy or ranking execution. Repair the handoff proof first.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Result",
                "",
                "PASS. Live page sort/dominance callbacks match typed family policy surfaces for the covered handoff fixtures. Ordered, kept, and handoff hashes are stable across repeated runs.",
                "",
                "The proof-only `BottomReoRankingResultBoundary` is built beside the live path and matches the ordered, kept, pruned, and callback handoff hashes without consuming live candidate dictionaries or product-driving fields.",
                "",
                "## Recommendation",
                "",
                "Next slice: add a page-local callback adapter boundary object that packages the live candidate-dict surfaces before invoking the family policy helpers. Keep `_keep_top_candidates(...)` and `_keep_top_candidates_core(...)` live paths unchanged.",
            ]
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

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
