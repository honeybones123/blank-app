from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

ANNOTATION_ASSIGNMENT_KEYS = [
    "winning_candidate_post_util",
    "winning_candidate_reaches_target_band",
    "winning_candidate_distance_to_target_band",
    "winning_candidate_selected_because_reaches_band",
    "winning_candidate_selected_from_band_reachers",
    "winner_pool_mode",
    "band_reacher_labels_considered",
    "winning_candidate_goal_score",
    "runner_up_goal_score",
    "goal_tie_break_reason",
    "winning_candidate_goal_preference",
    "canonical_winner_label",
    "title_locked_from_final_winner",
]


def _stable_hash(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _order_hash(value: dict[str, Any]) -> str:
    raw = json.dumps(list(value.items()), default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _read_latest(pattern: str) -> tuple[Path | None, dict[str, Any]]:
    files = sorted(ARTIFACT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None, {}
    path = files[0]
    return path, json.loads(path.read_text(encoding="utf-8"))


def _source_assignment_order() -> list[str]:
    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    start = source.index("def _select_best_auto_design_candidate")
    annotation_start = source.index('        winner["winning_candidate_post_util"] =', start)
    end = source.index("        selected_candidate_identity =", annotation_start)
    block = source[annotation_start:end]
    return re.findall(r'winner\["([^"]+)"\]\s*=', block)


def _goal_preference(seed_state: dict[str, Any]) -> str:
    return "shallower" if str(seed_state.get("optimisation_goal") or "") == "shallower_beam" else "balanced"


def _annotation_pairs(
    winner: dict[str, Any],
    *,
    selected_because_band: bool,
    winner_pool_mode: str,
    band_reachers: list[dict[str, Any]],
    winner_goal_score: float | None,
    runner_up_goal_score: float | None,
    goal_tie_break_reason: str | None,
    seed_state: dict[str, Any],
) -> list[tuple[str, Any]]:
    pairs: list[tuple[str, Any]] = [
        ("winning_candidate_post_util", winner.get("candidate_post_util")),
        ("winning_candidate_reaches_target_band", winner.get("candidate_reaches_target_band")),
        ("winning_candidate_distance_to_target_band", winner.get("candidate_distance_to_target_band")),
        ("winning_candidate_selected_because_reaches_band", selected_because_band),
        ("winning_candidate_selected_from_band_reachers", selected_because_band),
        ("winner_pool_mode", winner_pool_mode),
        ("band_reacher_labels_considered", [str(c.get("label") or "")[:100] for c in band_reachers[:24]]),
        ("winning_candidate_goal_score", winner_goal_score),
        ("runner_up_goal_score", runner_up_goal_score),
        ("goal_tie_break_reason", goal_tie_break_reason),
        ("winning_candidate_goal_preference", _goal_preference(seed_state)),
    ]
    label = str(winner.get("label") or "").strip()
    if label:
        pairs.extend(
            [
                ("canonical_winner_label", label),
                ("title_locked_from_final_winner", True),
            ]
        )
    return pairs


def _apply_sequential(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    winner = copy.deepcopy(candidate)
    winner["winning_candidate_post_util"] = winner.get("candidate_post_util")
    winner["winning_candidate_reaches_target_band"] = winner.get("candidate_reaches_target_band")
    winner["winning_candidate_distance_to_target_band"] = winner.get("candidate_distance_to_target_band")
    winner["winning_candidate_selected_because_reaches_band"] = context["selected_because_band"]
    winner["winning_candidate_selected_from_band_reachers"] = context["selected_because_band"]
    winner["winner_pool_mode"] = context["winner_pool_mode"]
    winner["band_reacher_labels_considered"] = [
        str(c.get("label") or "")[:100] for c in context["band_reachers"][:24]
    ]
    winner["winning_candidate_goal_score"] = context["winner_goal_score"]
    winner["runner_up_goal_score"] = context["runner_up_goal_score"]
    winner["goal_tie_break_reason"] = context["goal_tie_break_reason"]
    winner["winning_candidate_goal_preference"] = _goal_preference(context["seed_state"])
    label = str(winner.get("label") or "").strip()
    if label:
        winner["canonical_winner_label"] = label
        winner["title_locked_from_final_winner"] = True
    return winner


def _apply_ordered_pairs(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    winner = copy.deepcopy(candidate)
    for key, value in _annotation_pairs(winner, **context):
        winner[key] = value
    return winner


def _apply_dict_update(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    winner = copy.deepcopy(candidate)
    payload = dict(_annotation_pairs(winner, **context))
    winner.update(payload)
    return winner


def _candidate_from_bottom_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    selected = ((snapshot.get("scenarios") or {}).get("bottom_reo_recommendation_selected") or {})
    decision = selected.get("selected_candidate_decision_exact") or {}
    update_keys = list(decision.get("selected_candidate_update_keys") or selected.get("selected_update_keys") or [])
    return {
        "candidate_id": decision.get("selected_candidate_id") or selected.get("selected_candidate_id"),
        "label": selected.get("result_label") or "Bottom reo candidate",
        "candidate_post_util": decision.get("selected_candidate_post_util"),
        "candidate_reaches_target_band": decision.get("selected_because_reaches_band"),
        "candidate_distance_to_target_band": decision.get("selected_distance_to_target_band"),
        "score": selected.get("selected_score"),
        "family_tag": decision.get("selected_family_tag") or "bending",
        "updates": {key: f"sample:{key}" for key in update_keys},
    }


def _candidate_from_geometry_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    selected = ((snapshot.get("scenarios") or {}).get("geometry_recommendation_selected") or {})
    update_keys = list(selected.get("selected_update_keys") or selected.get("result_update_keys") or [])
    return {
        "candidate_id": selected.get("selected_candidate_id"),
        "label": "Geometry candidate",
        "candidate_post_util": None,
        "candidate_reaches_target_band": None,
        "candidate_distance_to_target_band": None,
        "score": selected.get("selected_score"),
        "family_tag": "geometry",
        "updates": {key: f"sample:{key}" for key in update_keys},
    }


def _scenario_inputs() -> tuple[list[dict[str, Any]], dict[str, Path | None]]:
    bottom_path, bottom = _read_latest("*bottom_reo_recommendation_readiness_snapshot_9N*.json")
    geometry_path, geometry = _read_latest("*geometry_recommendation_readiness_snapshot_9H*.json")
    bottom_candidate = _candidate_from_bottom_snapshot(bottom) if bottom else {}
    geometry_candidate = _candidate_from_geometry_snapshot(geometry) if geometry else {}
    preannotated = copy.deepcopy(bottom_candidate)
    preannotated.update(
        {
            "winning_candidate_post_util": "old",
            "canonical_winner_label": "Old label",
            "title_locked_from_final_winner": False,
            "post_annotation_existing_tail": True,
        }
    )
    blank_label = copy.deepcopy(geometry_candidate)
    blank_label["label"] = "   "
    return [
        {"name": "bottom_readiness_selected_summary", "candidate": bottom_candidate},
        {"name": "geometry_readiness_selected_summary", "candidate": geometry_candidate},
        {"name": "preannotated_bottom_candidate_summary", "candidate": preannotated},
        {"name": "blank_label_geometry_candidate_summary", "candidate": blank_label},
    ], {"bottom_snapshot": bottom_path, "geometry_snapshot": geometry_path}


def _compare_candidate(name: str, candidate: dict[str, Any]) -> dict[str, Any]:
    context = {
        "selected_because_band": bool(candidate.get("candidate_reaches_target_band")),
        "winner_pool_mode": "band_reachers" if candidate.get("candidate_reaches_target_band") else "fallback_pool",
        "band_reachers": [candidate, {"label": "Runner-up candidate"}],
        "winner_goal_score": 1.25,
        "runner_up_goal_score": 1.5,
        "goal_tie_break_reason": "offline_parity_probe",
        "seed_state": {"optimisation_goal": "shallower_beam"},
    }
    sequential = _apply_sequential(candidate, context)
    ordered_pairs = _apply_ordered_pairs(candidate, context)
    dict_update = _apply_dict_update(candidate, context)
    sensitive_keys = [key for key in ANNOTATION_ASSIGNMENT_KEYS if key in sequential]
    return {
        "scenario": name,
        "input_key_order": list(candidate.keys()),
        "annotation_keys_present": sensitive_keys,
        "sequential_stable_hash": _stable_hash(sequential),
        "ordered_pairs_stable_hash": _stable_hash(ordered_pairs),
        "dict_update_stable_hash": _stable_hash(dict_update),
        "sequential_order_hash": _order_hash(sequential),
        "ordered_pairs_order_hash": _order_hash(ordered_pairs),
        "dict_update_order_hash": _order_hash(dict_update),
        "ordered_pairs_exact_match": sequential == ordered_pairs and list(sequential.keys()) == list(ordered_pairs.keys()),
        "dict_update_exact_match": sequential == dict_update and list(sequential.keys()) == list(dict_update.keys()),
        "title_lock_present": bool(sequential.get("title_locked_from_final_winner")),
        "canonical_winner_label": sequential.get("canonical_winner_label"),
    }


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    scenarios, sources = _scenario_inputs()
    source_order = _source_assignment_order()
    source_order_matches_model = source_order[: len(ANNOTATION_ASSIGNMENT_KEYS)] == ANNOTATION_ASSIGNMENT_KEYS
    comparisons = [_compare_candidate(str(item["name"]), dict(item["candidate"] or {})) for item in scenarios]
    ordered_pairs_all_match = all(row["ordered_pairs_exact_match"] for row in comparisons)
    dict_update_all_match = all(row["dict_update_exact_match"] for row in comparisons)
    raw_shapes_available = False
    recommendation = (
        "coverage_gap_leave_live_lane_local"
        if dict_update_all_match and not raw_shapes_available
        else ("order_preserving_helper_candidate" if ordered_pairs_all_match and not dict_update_all_match else "stop_lane")
    )
    failures: list[str] = []
    if not source_order_matches_model:
        failures.append("source_assignment_order_does_not_match_harness_model")
    if not ordered_pairs_all_match:
        failures.append("ordered_pair_application_does_not_match_sequential")
    result = {
        "schema": "auto_design_winner_annotation_order_parity.v1",
        "status": "PASS" if not failures else "FAIL",
        "phase": "10J",
        "sources": {key: str(path) if path else None for key, path in sources.items()},
        "raw_candidate_shapes_available": raw_shapes_available,
        "source_assignment_order": source_order,
        "source_order_matches_model": source_order_matches_model,
        "comparisons": comparisons,
        "ordered_pairs_all_match": ordered_pairs_all_match,
        "dict_update_all_match": dict_update_all_match,
        "recommendation": recommendation,
        "failures": failures,
    }
    json_path = ARTIFACT_DIR / f"auto_design_winner_annotation_order_parity_10J_{stamp}.json"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    md_lines = [
        "# Phase 10J - Auto-Design Winner Annotation Order Parity",
        "",
        f"Status: {result['status']}",
        f"Recommendation: `{recommendation}`",
        "",
        "## Source Artifacts",
        "",
        f"- bottom readiness: `{result['sources']['bottom_snapshot']}`",
        f"- geometry readiness: `{result['sources']['geometry_snapshot']}`",
        "",
        "## Assignment Order",
        "",
        f"- source order matches harness model: `{source_order_matches_model}`",
        f"- raw full winner candidate shapes available: `{raw_shapes_available}`",
        "",
        "## Comparison Table",
        "",
        "| Scenario | Ordered-pair exact | dict.update exact | Sequential hash | Ordered hash | Update hash |",
        "|---|---:|---:|---|---|---|",
    ]
    for row in comparisons:
        md_lines.append(
            f"| {row['scenario']} | {row['ordered_pairs_exact_match']} | {row['dict_update_exact_match']} | "
            f"`{row['sequential_order_hash']}` | `{row['ordered_pairs_order_hash']}` | `{row['dict_update_order_hash']}` |"
        )
    md_lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The ordered-pair strategy matches sequential assignment for the available representative summary shapes.",
            "However, `dict.update(...)` also matches those shapes. Because Phase 10H already proved `dict.update(...)` drifts in the live product path, the available artifacts do not contain the raw/order-sensitive winner shape needed to explain the drift offline.",
            "",
            "Conclusion: do not extract the live winner annotation block from this evidence. Leave the lane local or add a narrower capture artifact that records the raw candidate shape before annotation without live per-assignment tracing.",
        ]
    )
    md_path = AUDIT_DIR / f"auto_design_winner_annotation_order_parity_10J_{stamp}.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"{result['status']}: {json_path}")
    print(f"REPORT: {md_path}")
    print(f"RECOMMENDATION: {recommendation}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
