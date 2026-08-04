"""Focused snapshot for bottom reo accepted-candidate normalization.

This verifier derives accepted-candidate proof records from the already
normalized evaluated/filter boundary records. It does not read live candidate
objects, run ranking/selection ownership, or include CTA/publication/render
surfaces.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from design_brain.families.bending import build_bottom_reo_accepted_candidates
from tools.verification import bottom_reo_evaluated_candidate_filter_boundary_snapshot as boundary_snapshot


ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"
TRACE_DIR = REPO / "artifacts" / "traces"

FORBIDDEN_ACCEPTED_KEYS = {
    "action_payload",
    "action_type",
    "button_contract",
    "cta",
    "debug",
    "final_selected_repair",
    "mutation",
    "one_click",
    "publication",
    "rank",
    "ranking",
    "ranking_score",
    "render",
    "score",
    "selected_recommendation",
    "session_state",
    "ui",
}

SCENARIOS = [
    "normal_bending_underdesign",
    "bending_overdesign_cleanup",
    "spacing_limited_arrangement",
    "two_layer_arrangement",
    "geometry_constrained_arrangement",
]


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _accepted_candidates_from_boundary(boundary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item.to_dict()
        for item in build_bottom_reo_accepted_candidates(boundary=boundary)
    ]


def _run_boundary_scenarios(module: Any, trace_path: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        results.append(boundary_snapshot._run_scenario(module, scenario, trace_path))
    return results


def _assert_accepted_snapshot(result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    boundary = result.get("boundary") if isinstance(result.get("boundary"), dict) else {}
    accepted = result.get("accepted_candidates") if isinstance(result.get("accepted_candidates"), list) else []
    boundary_ids = list(boundary.get("accepted_prerank_candidate_ids") or [])
    accepted_ids = [str(item.get("candidate_identity") or "") for item in accepted if isinstance(item, dict)]
    if accepted_ids != boundary_ids:
        failures.append("accepted_order_mismatch")
    if result.get("accepted_candidate_count") != len(boundary_ids):
        failures.append("accepted_count_mismatch")
    if result.get("accepted_candidate_count") and not result.get("accepted_candidate_hash"):
        failures.append("missing_accepted_candidate_hash")
    for item in accepted:
        if not isinstance(item, dict):
            failures.append("accepted_record_not_dict")
            continue
        leaked = sorted(set(item.keys()) & FORBIDDEN_ACCEPTED_KEYS)
        if leaked:
            failures.append(f"forbidden_accepted_keys:{','.join(leaked)}")
        for required in (
            "accepted_order_index",
            "source_record_order_index",
            "candidate_identity",
            "candidate_update_keys",
            "candidate_update_payload_hash",
            "arrangement_signature",
            "utilisation_summary",
            "acceptance_status",
        ):
            if required not in item:
                failures.append(f"missing_{required}")
        if item.get("acceptance_status") != "accepted_prerank":
            failures.append("wrong_acceptance_status")
    return sorted(set(failures))


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"bottom_reo_accepted_candidate_normalization_{stamp}.jsonl"
    artifact_path = ARTIFACT_DIR / f"bottom_reo_accepted_candidate_normalization_{stamp}.json"
    report_path = AUDIT_DIR / f"bottom_reo_accepted_candidate_normalization_{stamp}.md"

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
        boundary_results = _run_boundary_scenarios(module, trace_path)
        repeat_boundary_results = _run_boundary_scenarios(module, trace_path)
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    scenarios: list[dict[str, Any]] = []
    for boundary_result in boundary_results:
        boundary = boundary_result.get("boundary") if isinstance(boundary_result.get("boundary"), dict) else {}
        accepted = _accepted_candidates_from_boundary(boundary)
        scenarios.append(
            {
                "scenario": boundary_result.get("scenario"),
                "boundary_pre_rank_surface_hash": boundary_result.get("pre_rank_surface_hash"),
                "accepted_candidate_count": len(accepted),
                "accepted_candidate_order": [
                    str(item.get("candidate_identity") or "") for item in accepted
                ],
                "accepted_candidate_hash": _stable_hash(accepted),
                "accepted_candidates": accepted,
                "source_boundary_accepted_order_hash": boundary_result.get("accepted_prerank_order_hash"),
                "boundary": {
                    "accepted_prerank_candidate_ids": list(boundary.get("accepted_prerank_candidate_ids") or []),
                    "pre_rank_surface_hash": boundary.get("pre_rank_surface_hash"),
                    "forbidden_fields_present": list(boundary.get("forbidden_fields_present") or []),
                },
            },
        )

    repeat_by_scenario: dict[str, dict[str, Any]] = {}
    for boundary_result in repeat_boundary_results:
        accepted = _accepted_candidates_from_boundary(
            boundary_result.get("boundary") if isinstance(boundary_result.get("boundary"), dict) else {},
        )
        repeat_by_scenario[str(boundary_result.get("scenario"))] = {
            "accepted_candidate_order": [
                str(item.get("candidate_identity") or "") for item in accepted
            ],
            "accepted_candidate_hash": _stable_hash(accepted),
        }

    failures: dict[str, list[str]] = {}
    aggregate_accepted_count = 0
    stability: dict[str, dict[str, Any]] = {}
    for scenario_result in scenarios:
        scenario_name = str(scenario_result.get("scenario"))
        scenario_failures = _assert_accepted_snapshot(scenario_result)
        repeat = repeat_by_scenario.get(scenario_name, {})
        same_order = scenario_result.get("accepted_candidate_order") == repeat.get("accepted_candidate_order")
        same_hash = scenario_result.get("accepted_candidate_hash") == repeat.get("accepted_candidate_hash")
        aggregate_accepted_count += int(scenario_result.get("accepted_candidate_count") or 0)
        stability[scenario_name] = {
            "same_accepted_order": same_order,
            "same_accepted_candidate_hash": same_hash,
            "first_hash": scenario_result.get("accepted_candidate_hash"),
            "repeat_hash": repeat.get("accepted_candidate_hash"),
        }
        if not same_order:
            scenario_failures.append("unstable_accepted_order")
        if not same_hash:
            scenario_failures.append("unstable_accepted_candidate_hash")
        if scenario_failures:
            failures[scenario_name] = sorted(set(scenario_failures))
    if aggregate_accepted_count <= 0:
        failures.setdefault("_aggregate", []).append("no_accepted_candidates_observed")

    snapshot = {
        "status": "PASS" if not failures else "FAIL",
        "generated_at": stamp,
        "trace_path": str(trace_path),
        "scenarios": scenarios,
        "stability": stability,
        "forbidden_accepted_keys": sorted(FORBIDDEN_ACCEPTED_KEYS),
        "failures": failures,
        "assertions": {
            "derived_from_evaluated_filter_boundary_records": True,
            "live_candidate_objects_read": False,
            "ranking_selection_cta_one_click_publication_absent": not failures,
            "product_path_changed": False,
        },
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str), encoding="utf-8")

    report_lines = [
        "# Bottom Reo Accepted-Candidate Normalization Snapshot",
        "",
        f"- Status: {snapshot['status']}",
        f"- JSON artifact: `{artifact_path}`",
        f"- Trace artifact: `{trace_path}`",
        "",
        "## Scope",
        "",
        "Accepted-candidate proof records are derived only from evaluated/filter boundary records.",
        "Live candidate objects, ranking, selection, CTA, one-click, publication, render/UI, mutation, session, and debug fields are excluded.",
        "",
        "## Scenario Summary",
    ]
    for scenario_result in scenarios:
        name = str(scenario_result.get("scenario"))
        report_lines.extend([
            "",
            f"### {name}",
            f"- accepted count: {scenario_result.get('accepted_candidate_count')}",
            f"- accepted hash: `{scenario_result.get('accepted_candidate_hash')}`",
            f"- accepted order: `{scenario_result.get('accepted_candidate_order')}`",
            f"- stability: `{stability.get(name, {})}`",
        ])
    if failures:
        report_lines.extend(["", "## Failures", ""])
        for name, scenario_failures in failures.items():
            report_lines.append(f"- {name}: {', '.join(scenario_failures)}")
    else:
        report_lines.extend([
            "",
            "## Result",
            "",
            "PASS. Accepted-candidate normalization can be proven from boundary records without reading live candidate objects or including forbidden ranking/CTA/publication surfaces.",
            "",
            "## Recommendation",
            "",
            "Next slice can add a family-owned `BottomReoAcceptedCandidate` derived normalizer in `design_brain/families/bending.py`.",
        ])
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": snapshot["status"],
        "artifact": str(artifact_path),
        "report": str(report_path),
        "trace": str(trace_path),
        "failures": failures,
    }, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
