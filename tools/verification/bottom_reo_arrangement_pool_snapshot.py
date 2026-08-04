"""Focused snapshot for normal bottom-reo arrangement/spec generation.

This verifier freezes the output of the local bottom reinforcement arrangement
pool before evaluator, filter, ranking, selector, CTA, or publication logic is
allowed to touch it.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

ARTIFACT_DIR = REPO / "artifacts" / "verification"

FORBIDDEN_DESCRIPTOR_KEYS = {
    "candidate_id",
    "source_candidate_id",
    "overview",
    "score",
    "rank",
    "ranking",
    "selected",
    "selected_candidate",
    "selector_result",
    "filter_result",
    "is_compliant",
    "worst_util",
    "candidate_reaches_target_band",
    "candidate_distance_to_target_band",
    "action_type",
}


def _stable_hash(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _base_state(**overrides: Any) -> dict[str, Any]:
    state = {
        "b": 300.0,
        "D": 600.0,
        "bw": 300.0,
        "cover_side": 40.0,
        "cover_bot": 40.0,
        "rowgap_bot": 60.0,
        "fc": 40.0,
        "fsy": 500.0,
        "uls_Mstar": 160.0,
        "uls_Vstar": 60.0,
        "bot1_count": 4,
        "bot2_count": 0,
        "db_bot_1": 16,
        "db_bot_2": 16,
        "bot_row_count": 1,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200,
        "design_optimisation_goal": "balanced",
        "optimisation_lock_geometry": True,
    }
    state.update(overrides)
    return state


def _mode_config(search_strategy: str, **overrides: Any) -> dict[str, Any]:
    mode = {
        "target_util_min": 0.85,
        "target_util_max": 1.0,
        "target_low": 0.85,
        "target_high": 1.0,
        "search_strategy": search_strategy,
    }
    mode.update(overrides)
    return mode


def _case_definitions() -> dict[str, dict[str, Any]]:
    return {
        "normal_bending_underdesign": {
            "state": _base_state(
                b=300.0,
                D=600.0,
                bot1_count=4,
                bot2_count=0,
                db_bot_1=16,
                db_bot_2=16,
                bot_row_count=1,
            ),
            "mode_config": _mode_config("balanced"),
            "context": {},
        },
        "bending_overdesign_cleanup": {
            "state": _base_state(
                b=300.0,
                D=600.0,
                bot1_count=8,
                bot2_count=0,
                db_bot_1=20,
                db_bot_2=20,
                bot_row_count=1,
            ),
            "mode_config": _mode_config("low_reo"),
            "context": {},
        },
        "spacing_limited": {
            "state": _base_state(
                b=240.0,
                D=550.0,
                cover_side=55.0,
                bot1_count=4,
                bot2_count=0,
                db_bot_1=20,
                db_bot_2=20,
                bot_row_count=1,
            ),
            "mode_config": _mode_config("balanced"),
            "context": {},
        },
        "two_layer_arrangement": {
            "state": _base_state(
                b=300.0,
                D=600.0,
                bot1_count=6,
                bot2_count=2,
                db_bot_1=16,
                db_bot_2=16,
                bot_row_count=2,
            ),
            "mode_config": _mode_config("balanced"),
            "context": {},
        },
        "geometry_constrained": {
            "state": _base_state(
                b=180.0,
                bw=180.0,
                D=450.0,
                cover_side=50.0,
                bot1_count=3,
                bot2_count=0,
                db_bot_1=20,
                db_bot_2=20,
                bot_row_count=1,
            ),
            "mode_config": _mode_config("balanced"),
            "context": {},
        },
    }


def _input_summary(module: Any, state: dict[str, Any], mode_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "geometry": {
            "b": float(state.get("b", 0.0) or 0.0),
            "D": float(state.get("D", 0.0) or 0.0),
            "bw": float(state.get("bw", state.get("b", 0.0)) or 0.0),
        },
        "reo_constraints": {
            "cover_side": float(state.get("cover_side", 40.0) or 40.0),
            "cover_bot": float(state.get("cover_bot", 40.0) or 40.0),
            "rowgap_bot": float(state.get("rowgap_bot", 60.0) or 60.0),
            "current_bot1_count": int(state.get("bot1_count", 0) or 0),
            "current_bot2_count": int(state.get("bot2_count", 0) or 0),
            "current_db_bot_1": int(state.get("db_bot_1", 0) or 0),
            "current_db_bot_2": int(state.get("db_bot_2", state.get("db_bot_1", 0)) or 0),
            "current_bot_row_count": int(state.get("bot_row_count", 1) or 1),
        },
        "available_bar_sizes": list(getattr(module, "REO_BAR_DIAS", [])),
        "candidate_limit_default": int(getattr(module, "AUTO_DESIGN_MAX_STAGE_CANDIDATES", 0) or 0),
        "mode": {
            "search_strategy": str(mode_config.get("search_strategy") or ""),
            "target_util_min": mode_config.get("target_util_min"),
            "target_util_max": mode_config.get("target_util_max"),
        },
    }


def _arrangement_signature(arrangement: dict[str, Any]) -> str:
    return (
        f"{int(arrangement.get('bot1_count', 0) or 0)}-"
        f"{int(arrangement.get('bot2_count', 0) or 0)}-"
        f"{int(arrangement.get('db_bot_1', 0) or 0)}-"
        f"{int(arrangement.get('db_bot_2', arrangement.get('db_bot_1', 0)) or 0)}"
    )


def _arrangement_descriptor(module: Any, arrangement: dict[str, Any]) -> dict[str, Any]:
    descriptor = {
        "signature": _arrangement_signature(arrangement),
        "arrangement": {
            "bot1_layout_mode": str(arrangement.get("bot1_layout_mode") or ""),
            "bot1_count": int(arrangement.get("bot1_count", 0) or 0),
            "db_bot_1": int(arrangement.get("db_bot_1", 0) or 0),
            "bot2_layout_mode": str(arrangement.get("bot2_layout_mode") or ""),
            "bot2_count": int(arrangement.get("bot2_count", 0) or 0),
            "db_bot_2": int(arrangement.get("db_bot_2", arrangement.get("db_bot_1", 0)) or 0),
        },
    }
    updates = module._bottom_arrangement_to_shared_updates(dict(arrangement))
    descriptor["layer_count"] = 2 if descriptor["arrangement"]["bot2_count"] > 0 else 1
    descriptor["bar_counts"] = {
        "row_1": descriptor["arrangement"]["bot1_count"],
        "row_2": descriptor["arrangement"]["bot2_count"],
        "total": descriptor["arrangement"]["bot1_count"] + descriptor["arrangement"]["bot2_count"],
    }
    descriptor["bar_sizes"] = {
        "row_1": descriptor["arrangement"]["db_bot_1"],
        "row_2": descriptor["arrangement"]["db_bot_2"],
    }
    descriptor["spacing_spec"] = {
        key: updates.get(key)
        for key in (
            "bot_row_count",
            "bot_row_1_bars",
            "bot_row_1_dia",
            "bot_row_1_mode",
            "bot_row_1_spacing",
            "bot_row_2_bars",
            "bot_row_2_dia",
            "bot_row_2_mode",
            "bot_row_2_spacing",
        )
        if key in updates
    }
    descriptor["label"] = module._practical_bottom_reo_label(
        descriptor["arrangement"]["bot1_count"],
        descriptor["arrangement"]["bot2_count"],
        descriptor["arrangement"]["db_bot_1"],
    )
    descriptor["descriptor_hash"] = _stable_hash(descriptor)
    return descriptor


def _forbidden_keys(value: Any, *, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_s = str(key)
            path = f"{prefix}.{key_s}" if prefix else key_s
            if key_s in FORBIDDEN_DESCRIPTOR_KEYS:
                found.append(path)
            found.extend(_forbidden_keys(item, prefix=path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_forbidden_keys(item, prefix=f"{prefix}[{index}]"))
    return found


def _snapshot_case(module: Any, case_name: str, definition: dict[str, Any]) -> dict[str, Any]:
    state = dict(definition["state"])
    mode_config = dict(definition["mode_config"])
    base_context = dict(definition.get("context") or {})
    band_results: list[dict[str, Any]] = []
    combined_descriptors: list[dict[str, Any]] = []
    for band in (0, 1):
        context = dict(base_context)
        arrangements = module._generate_local_bottom_arrangements(
            state,
            mode_config,
            band=band,
            context=context,
        )
        descriptors = [_arrangement_descriptor(module, dict(item)) for item in arrangements]
        band_results.append({
            "band": band,
            "arrangement_count": len(descriptors),
            "arrangement_order": [item["signature"] for item in descriptors],
            "arrangement_pool_hash": _stable_hash(descriptors),
            "arrangements": descriptors,
            "rejected_impossible_arrangements": [],
            "rejected_impossible_arrangements_currently_produced": False,
        })
        combined_descriptors.extend(descriptors)
    forbidden = _forbidden_keys(band_results)
    return {
        "case": case_name,
        "input": _input_summary(module, state, mode_config),
        "band_results": band_results,
        "combined_arrangement_order": [item["signature"] for item in combined_descriptors],
        "combined_arrangement_pool_hash": _stable_hash(combined_descriptors),
        "proof_no_evaluator_filter_ranking_selection": {
            "status": "PASS" if not forbidden else "FAIL",
            "forbidden_fields_present": forbidden,
            "evaluator_outputs_included": False,
            "filter_outputs_included": False,
            "ranking_outputs_included": False,
            "selection_outputs_included": False,
        },
    }


def _validate(snapshot: dict[str, Any]) -> tuple[str, list[str]]:
    failures: list[str] = []
    cases = {item["case"]: item for item in snapshot.get("cases", [])}
    required = {
        "normal_bending_underdesign",
        "bending_overdesign_cleanup",
        "spacing_limited",
        "two_layer_arrangement",
        "geometry_constrained",
    }
    missing = sorted(required - set(cases))
    if missing:
        failures.append(f"missing required cases: {missing}")
    for name, case in cases.items():
        forbidden = case.get("proof_no_evaluator_filter_ranking_selection", {}).get("forbidden_fields_present") or []
        if forbidden:
            failures.append(f"{name}: forbidden evaluator/filter/ranking/selection fields present: {forbidden[:8]}")
        if not case.get("combined_arrangement_pool_hash"):
            failures.append(f"{name}: missing combined arrangement pool hash")
    if cases.get("normal_bending_underdesign"):
        total = sum(int(band.get("arrangement_count") or 0) for band in cases["normal_bending_underdesign"]["band_results"])
        if total <= 0:
            failures.append("normal_bending_underdesign: expected at least one arrangement")
    if cases.get("bending_overdesign_cleanup"):
        total = sum(int(band.get("arrangement_count") or 0) for band in cases["bending_overdesign_cleanup"]["band_results"])
        if total <= 0:
            failures.append("bending_overdesign_cleanup: expected at least one arrangement")
    if cases.get("spacing_limited"):
        total = sum(int(band.get("arrangement_count") or 0) for band in cases["spacing_limited"]["band_results"])
        if total <= 0:
            failures.append("spacing_limited: expected at least one arrangement")
    if cases.get("two_layer_arrangement"):
        has_two_layer = any(
            descriptor.get("layer_count") == 2
            for band in cases["two_layer_arrangement"]["band_results"]
            for descriptor in band.get("arrangements", [])
        )
        if not has_two_layer:
            failures.append("two_layer_arrangement: expected at least one two-layer descriptor")
    if cases.get("geometry_constrained"):
        total = sum(int(band.get("arrangement_count") or 0) for band in cases["geometry_constrained"]["band_results"])
        if total <= 0:
            failures.append("geometry_constrained: expected at least one arrangement")
    return ("FAIL" if failures else "PASS"), failures


def main() -> int:
    import inputs_page_app_contract_bridge as module

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    snapshot = {
        "stage": "bottom_reo_arrangement_pool_snapshot",
        "timestamp": timestamp,
        "scope": "arrangement_spec_generation_only",
        "product_behavior_changed": False,
        "included_surfaces": [
            "input_geometry_and_reo_constraints",
            "available_bar_sizes",
            "generated_arrangement_order",
            "bar_counts",
            "layer_counts",
            "spacing_spec_values",
            "arrangement_descriptors",
            "arrangement_pool_hash",
        ],
        "excluded_surfaces": [
            "evaluator_outputs",
            "filter_results",
            "ranking_results",
            "selector_results",
            "selected_candidate",
            "CTA",
            "publication",
        ],
        "cases": [
            _snapshot_case(module, name, definition)
            for name, definition in _case_definitions().items()
        ],
    }
    result, failures = _validate(snapshot)
    snapshot["result"] = result
    snapshot["failures"] = failures
    snapshot["snapshot_hash"] = _stable_hash(snapshot.get("cases"))
    artifact = ARTIFACT_DIR / f"bottom_reo_arrangement_pool_snapshot_{timestamp}.json"
    artifact.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps({"result": result, "artifact": str(artifact), "failures": failures}, indent=2))
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
