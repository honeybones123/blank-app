"""BENDING_FAIL_GOVERNS live ladder implementation snapshot.

This verifier compares the live BENDING_FAIL_GOVERNS repair ladder implementation
surface against the contract-defined internal ladder order. It is proof-only:
it does not move code, mutate product state, publish recommendations, drive CTA,
render UI, or execute apply/one-click routing.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from hashlib import sha256
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.families.bending_fail import BendingFailFamily  # noqa: E402
from design_brain.families.bending_fail_governs.contract import (  # noqa: E402
    CONTRACT_PATH,
    depth_width_rule,
    family_identity,
    internal_strategy_lanes,
    load_bending_fail_governs_contract,
    utilisation_definitions,
)


CONTRACT_LANE_ALIASES = {
    "geometry_sanity": "GEOMETRY_SANITY",
    "depth_increase": "DEPTH_INCREASE",
    "single_layer_bottom_reinforcement": "SINGLE_LAYER_BOTTOM_REO",
    "larger_bars": "LARGER_BAR",
    "width_increase": "WIDTH_INCREASE",
    "multi_layer_reinforcement": "MULTI_LAYER_REO",
    "exact_stop": "EXACT_STOP",
    "no_valid_strategy": "NO_VALID_STRATEGY",
}

EXPECTED_LADDER_ORDER = (
    "GEOMETRY_SANITY",
    "DEPTH_INCREASE",
    "SINGLE_LAYER_BOTTOM_REO",
    "LARGER_BAR",
    "WIDTH_INCREASE",
    "MULTI_LAYER_REO",
    "EXACT_STOP",
    "NO_VALID_STRATEGY",
)

FORBIDDEN_PROOF_KEYS = {
    "apply_routing",
    "button_label",
    "cta_enabled",
    "cta_rendering",
    "debug",
    "html",
    "one_click",
    "one_click_fallback",
    "publication",
    "published_item",
    "render",
    "session",
    "source_precedence",
    "ui",
    "visible_wording",
}


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def _fixture_state() -> dict[str, Any]:
    return {
        "b": 300.0,
        "D": 350.0,
        "bot1_count": 2,
        "db_bot_1": 10,
        "bot_row_1_bars": 2,
        "bot_row_1_dia": 10,
        "cover_side": 40.0,
        "lig_d": 0,
    }


def _run_tool(script: str) -> dict[str, Any]:
    command = [sys.executable, str(ROOT / script)]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=420)
    artifact: str | None = None
    report: str | None = None
    parsed: dict[str, Any] = {}
    text = str(completed.stdout or "").strip()
    for start in [index for index, char in enumerate(text) if char == "{"]:
        try:
            candidate = json.loads(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            parsed = candidate
            break
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("PASS:") or stripped.startswith("FAIL:"):
            artifact = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("REPORT:") or stripped.startswith("Report:"):
            report = stripped.split(":", 1)[1].strip()
    artifact = str(parsed.get("artifact") or artifact or "")
    report = str(parsed.get("report") or report or "")
    payload: dict[str, Any] = {}
    if artifact:
        path = Path(artifact)
        if not path.is_absolute():
            path = ROOT / path
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            artifact = str(path)
    return {
        "script": script,
        "command": command,
        "returncode": completed.returncode,
        "status": payload.get("status") or parsed.get("status") or ("PASS" if completed.returncode == 0 else "FAIL"),
        "artifact": artifact or None,
        "report": report or payload.get("report"),
        "stdout_tail": str(completed.stdout or "")[-2000:],
        "stderr_tail": str(completed.stderr or "")[-2000:],
        "payload": payload,
    }


def _spec_snapshot(spec: dict[str, Any]) -> dict[str, Any]:
    updates = dict(spec.get("updates") or {})
    return {
        "ladder_index": spec.get("ladder_index"),
        "contract_step": spec.get("contract_step"),
        "stage_name": spec.get("stage_name"),
        "strategy": spec.get("strategy"),
        "updates": updates,
        "update_keys": sorted(str(key) for key in updates.keys()),
        "escalation": spec.get("escalation"),
        "candidate_family_id": spec.get("candidate_family_id"),
        "b": spec.get("b"),
        "D": spec.get("D"),
        "bottom_bar_count": spec.get("bottom_bar_count"),
        "bar_diameter": spec.get("bar_diameter"),
        "split_row": spec.get("split_row"),
        "clear_spacing": spec.get("clear_spacing"),
        "label": spec.get("label"),
    }


def _known_bad_snapshot(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage_name": record.get("stage_name"),
        "strategy": record.get("strategy"),
        "b": record.get("b"),
        "D": record.get("D"),
        "bottom_bar_count": record.get("bottom_bar_count"),
        "bar_diameter": record.get("bar_diameter"),
        "split_row": record.get("split_row"),
        "clear_spacing": record.get("clear_spacing"),
        "reason": record.get("reason"),
    }


def _infer_lane(spec: dict[str, Any]) -> str:
    stage = str(spec.get("stage_name") or "")
    strategy = str(spec.get("strategy") or "").lower()
    updates = dict(spec.get("updates") or {})
    if stage == "stage_1_reo_only_same_geometry":
        if "split bottom reinforcement" in strategy or bool(spec.get("split_row")):
            return "MULTI_LAYER_REO"
        if "diameter" in strategy or "db_bot_1" in updates or "bot_row_1_dia" in updates:
            return "LARGER_BAR"
        return "SINGLE_LAYER_BOTTOM_REO"
    if stage == "stage_2_depth_increments_same_width":
        return "DEPTH_INCREASE"
    if stage == "stage_3_width_increments_for_reo_fit":
        return "WIDTH_INCREASE"
    if stage == "stage_4_combined_rescue":
        return "WIDTH_INCREASE"
    return f"UNKNOWN:{stage or 'missing_stage'}"


def _lane_trace(*, geometry_locked: bool, state: dict[str, Any] | None = None, fixture_name: str = "locked_fixture") -> dict[str, Any]:
    family = BendingFailFamily()
    result = family.contracted_repair_ladder_specs(dict(state or _fixture_state()), geometry_locked=geometry_locked)
    specs = [_spec_snapshot(dict(spec)) for spec in result.get("specs") or []]
    known_bad = [_known_bad_snapshot(dict(record)) for record in result.get("known_bad_candidates_skipped") or []]
    rows: list[dict[str, Any]] = []
    for spec in specs:
        lane = _infer_lane(spec)
        rows.append(
            {
                "candidate_index": spec.get("ladder_index"),
                "inferred_lane": lane,
                "contract_order_index": EXPECTED_LADDER_ORDER.index(lane) if lane in EXPECTED_LADDER_ORDER else None,
                "stage_name": spec.get("stage_name"),
                "strategy": spec.get("strategy"),
                "updates": spec.get("updates"),
                "evidence": {
                    "b": spec.get("b"),
                    "D": spec.get("D"),
                    "D_over_b": (
                        round(float(spec.get("D")) / float(spec.get("b")), 6)
                        if spec.get("D") and spec.get("b")
                        else None
                    ),
                    "bottom_bar_count": spec.get("bottom_bar_count"),
                    "bar_diameter": spec.get("bar_diameter"),
                    "split_row": spec.get("split_row"),
                    "clear_spacing": spec.get("clear_spacing"),
                },
            }
        )
    lane_sequence = [row["inferred_lane"] for row in rows]
    unique_lane_sequence = list(dict.fromkeys(lane_sequence))
    ordered_indexes = [
        int(row["contract_order_index"])
        for row in rows
        if row.get("contract_order_index") is not None
    ]
    lane_order_violations: list[dict[str, Any]] = []
    max_seen = -1
    for row in rows:
        order_index = row.get("contract_order_index")
        if order_index is None:
            continue
        if int(order_index) < max_seen:
            lane_order_violations.append(
                {
                    "candidate_index": row.get("candidate_index"),
                    "lane": row.get("inferred_lane"),
                    "contract_order_index": order_index,
                    "prior_max_contract_order_index": max_seen,
                    "stage_name": row.get("stage_name"),
                    "strategy": row.get("strategy"),
                }
            )
        max_seen = max(max_seen, int(order_index))
    width_before_depth = any(
        row.get("inferred_lane") == "WIDTH_INCREASE"
        for row in rows[: next((i for i, row in enumerate(rows) if row.get("inferred_lane") == "DEPTH_INCREASE"), len(rows))]
    )
    multi_before_width = any(
        row.get("inferred_lane") == "MULTI_LAYER_REO"
        for row in rows[: next((i for i, row in enumerate(rows) if row.get("inferred_lane") == "WIDTH_INCREASE"), len(rows))]
    )
    geometry_recheck_rows = [
        row
        for row in rows
        if row.get("inferred_lane") in {"DEPTH_INCREASE", "WIDTH_INCREASE"}
        and {
            "bot_row_1_bars",
            "bot_row_2_bars",
            "db_bot_1",
            "bot1_count",
            "bot2_count",
        }.intersection(set((row.get("updates") or {}).keys()))
    ]
    representative_cases = {
        "bending_fail_solved_by_depth_increase": next(
            (row for row in rows if row.get("inferred_lane") == "DEPTH_INCREASE"),
            None,
        ),
        "bending_fail_solved_by_single_layer_bottom_reo": next(
            (row for row in rows if row.get("inferred_lane") == "SINGLE_LAYER_BOTTOM_REO"),
            None,
        ),
        "bending_fail_requiring_larger_bars": next(
            (row for row in rows if row.get("inferred_lane") == "LARGER_BAR"),
            None,
        ),
        "bending_fail_requiring_width_increase": next(
            (row for row in rows if row.get("inferred_lane") == "WIDTH_INCREASE"),
            None,
        ),
        "bending_fail_requiring_multi_layer_reo": next(
            (row for row in rows if row.get("inferred_lane") == "MULTI_LAYER_REO"),
            None,
        ),
        "no_valid_strategy_or_blocked": {
            "stop_reason": result.get("stop_reason_if_no_candidate"),
            "known_bad_count": len(known_bad),
            "blocker_reasons": sorted({str(record.get("reason") or "") for record in known_bad if record.get("reason")}),
        },
    }
    trace = {
        "fixture_name": fixture_name,
        "geometry_locked": geometry_locked,
        "live_selected_family": "BENDING_FAIL_GOVERNS",
        "contract_family_id": str(family_identity().get("family_id") or ""),
        "live_ladder_trace": rows,
        "live_ladder_trace_hash": _stable_hash(rows),
        "inferred_live_strategy_lane_sequence": lane_sequence,
        "inferred_unique_lane_sequence": unique_lane_sequence,
        "selected_recommendation_lane": "not_materialized_by_ladder_spec_surface",
        "accepted_lane_evidence": rows,
        "rejected_lane_evidence": known_bad,
        "final_bending_utilisation": "not_materialized_by_ladder_spec_surface",
        "target_band_status": "target band contract present; evaluated status not materialized by ladder spec surface",
        "exact_stop_status": "not_materialized_by_ladder_spec_surface",
        "no_valid_strategy_status": result.get("stop_reason_if_no_candidate"),
        "representative_coverage": representative_cases,
        "unknown_lanes": [lane for lane in lane_sequence if lane not in EXPECTED_LADDER_ORDER],
        "lane_order_violations": lane_order_violations,
        "width_used_before_depth": width_before_depth,
        "multi_layer_used_before_width": multi_before_width,
        "geometry_change_rechecks_reo": bool(geometry_recheck_rows),
        "geometry_recheck_rows": geometry_recheck_rows,
        "ordered_contract_indexes": ordered_indexes,
        "ladder_compliance_hash": _stable_hash(
            {
                "geometry_locked": geometry_locked,
                "contract_order": EXPECTED_LADDER_ORDER,
                "lane_sequence": lane_sequence,
                "rows": rows,
                "known_bad": known_bad,
                "stop_reason": result.get("stop_reason_if_no_candidate"),
            }
        ),
    }
    return trace


def _latest_scenario_chain(lock_payload: dict[str, Any], scenario: str) -> dict[str, Any]:
    scenarios = lock_payload.get("scenarios")
    if isinstance(scenarios, dict):
        return dict(scenarios.get(scenario) or {})
    return {}


def _walk_forbidden(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_PROOF_KEYS:
                found.add(key_text)
            found.update(_walk_forbidden(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_walk_forbidden(child))
    return found


def _assert_snapshot(snapshot: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if snapshot.get("live_selected_family") != "BENDING_FAIL_GOVERNS":
        failures.append("live_family_not_bending_fail_governs")
    if snapshot.get("contract_family_id") != "BENDING_FAIL_GOVERNS":
        failures.append("contract_family_not_bending_fail_governs")
    if tuple(snapshot.get("contract_ladder_order") or ()) != EXPECTED_LADDER_ORDER:
        failures.append("contract_ladder_order_mismatch")
    target_band = dict(snapshot.get("target_band") or {})
    if target_band.get("lower") != 0.85 or target_band.get("upper") != 1.0:
        failures.append("target_band_not_0_85_to_1_00")
    ratio_rule = dict(snapshot.get("depth_width_rule") or {})
    if float(ratio_rule.get("maximum_preferred_ratio") or 0.0) != 2.0:
        failures.append("depth_width_ratio_rule_missing_or_not_2_0")
    for trace_name in ("geometry_unlocked_trace", "geometry_locked_trace"):
        trace = dict(snapshot.get(trace_name) or {})
        if trace.get("unknown_lanes"):
            failures.append(f"{trace_name}:unknown_lanes:{','.join(trace.get('unknown_lanes') or [])}")
        if trace.get("lane_order_violations"):
            failures.append(f"{trace_name}:contract_order_violation")
        if trace_name == "geometry_unlocked_trace" and trace.get("width_used_before_depth"):
            failures.append("geometry_unlocked_trace:width_used_before_depth")
        if trace_name == "geometry_unlocked_trace" and trace.get("multi_layer_used_before_width"):
            failures.append("geometry_unlocked_trace:multi_layer_used_before_width")
        if trace_name == "geometry_unlocked_trace" and not trace.get("geometry_change_rechecks_reo"):
            failures.append("geometry_unlocked_trace:geometry_change_does_not_recheck_reo")
    coverage_sources = [dict(snapshot.get("geometry_unlocked_trace") or {})] + [
        dict(value)
        for value in (
            (snapshot.get("coverage_traces") or {})
            or ((snapshot.get("ladder_proof_surface") or {}).get("coverage_traces") or {})
        ).values()
        if isinstance(value, dict)
    ]
    coverage_names = (
        "bending_fail_solved_by_depth_increase",
        "bending_fail_solved_by_single_layer_bottom_reo",
        "bending_fail_requiring_larger_bars",
        "bending_fail_requiring_width_increase",
        "bending_fail_requiring_multi_layer_reo",
        "no_valid_strategy_or_blocked",
    )
    for name in coverage_names:
        if not any((trace.get("representative_coverage") or {}).get(name) not in (None, {}, []) for trace in coverage_sources):
            failures.append(f"missing_coverage:{name}")
    if snapshot.get("bottom_reo_lock_status") != "PASS":
        failures.append("bottom_reo_lock_verifier_failed")
    if not snapshot.get("cta_intent_proof_hash"):
        failures.append("missing_cta_intent_proof_hash")
    forbidden = sorted(_walk_forbidden(snapshot.get("ladder_proof_surface") or {}))
    if forbidden:
        failures.append("forbidden_shared_fields_in_ladder_proof:" + ",".join(forbidden))
    return failures


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# BENDING_FAIL_GOVERNS Ladder Implementation Snapshot",
        "",
        f"Status: {snapshot.get('status')}",
        "",
        "## Scope",
        "",
        "Snapshot/proof only. No product behaviour, implementation logic, CTA rendering, publication, apply routing, one-click, visible wording, UI/session/debug, or ladder code was changed.",
        "",
        "## Contract",
        "",
        f"- contract: `{snapshot.get('contract_path')}`",
        f"- contract family: `{snapshot.get('contract_family_id')}`",
        f"- contract ladder order: `{snapshot.get('contract_ladder_order')}`",
        f"- target band: `{snapshot.get('target_band')}`",
        f"- depth/width rule: `{snapshot.get('depth_width_rule')}`",
        "",
        "## Live Product/Proof Inputs",
        "",
        f"- live selected family: `{snapshot.get('live_selected_family')}`",
        f"- bottom reo lock status: `{snapshot.get('bottom_reo_lock_status')}`",
        f"- CTA intent proof hash: `{snapshot.get('cta_intent_proof_hash')}`",
        "",
        "## Live Ladder Traces",
        "",
    ]
    for trace_name in ("geometry_unlocked_trace", "geometry_locked_trace"):
        trace = dict(snapshot.get(trace_name) or {})
        lines.extend(
            [
                f"### {trace_name}",
                "",
                f"- lane sequence: `{trace.get('inferred_live_strategy_lane_sequence')}`",
                f"- unique sequence: `{trace.get('inferred_unique_lane_sequence')}`",
                f"- lane order violations: `{trace.get('lane_order_violations')}`",
                f"- width used before depth: `{trace.get('width_used_before_depth')}`",
                f"- multi-layer used before width: `{trace.get('multi_layer_used_before_width')}`",
                f"- geometry change rechecks reo: `{trace.get('geometry_change_rechecks_reo')}`",
                f"- ladder compliance hash: `{trace.get('ladder_compliance_hash')}`",
                "",
            ]
        )
    lines.extend(["## Failures", ""])
    lines.extend([f"- {failure}" for failure in snapshot.get("failures") or []] or ["- none"])
    lines.extend(
        [
            "",
            "## Decision",
            "",
            (
                "PASS: live implementation ladder surface follows the contract-defined ladder order."
                if snapshot.get("status") == "PASS"
                else "FAIL: live implementation ladder surface does not currently prove compliance with the contract-defined ladder order. Do not move or delete ladder implementation logic until this drift is resolved by an explicit contract/product decision."
            ),
            "",
            "## Artifacts",
            "",
            f"- JSON: `{snapshot.get('artifact_path')}`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"bending_fail_governs_ladder_implementation_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_ladder_implementation_{stamp}.md"

    contract = load_bending_fail_governs_contract()
    target = dict((contract.get("family_objective") or {}).get("target_band") or {})
    contract_lanes = [
        {
            "lane_index": lane.get("lane_index"),
            "lane_id": lane.get("lane_id"),
            "contract_lane": CONTRACT_LANE_ALIASES.get(str(lane.get("lane_id") or ""), "UNKNOWN"),
            "title": lane.get("title"),
        }
        for lane in internal_strategy_lanes()
    ]
    product = _run_tool("tools/verification/bending_fail_governs_repair_regression.py")
    bottom_lock = _run_tool("tools/verification/bending_bottom_reo_recommendation_lock_verifier.py")
    normal_chain = _latest_scenario_chain(dict(bottom_lock.get("payload") or {}), "normal_bending_underdesign")

    geometry_unlocked_trace = _lane_trace(geometry_locked=False, fixture_name="default_spacing_limited")
    geometry_locked_trace = _lane_trace(geometry_locked=True, fixture_name="default_geometry_locked")
    coverage_traces = {
        "single_layer_spacing_open": _lane_trace(
            geometry_locked=False,
            fixture_name="single_layer_spacing_open",
            state={
                **_fixture_state(),
                "b": 600.0,
            },
        ),
    }
    live_selected_family = (
        (product.get("payload") or {}).get("selected_family_id")
        or geometry_unlocked_trace.get("live_selected_family")
    )
    cta_intent_proof_hash = normal_chain.get("cta_action_intent_proof_hash")
    ladder_proof_surface = {
        "contract_lanes": contract_lanes,
        "geometry_unlocked_trace": geometry_unlocked_trace,
        "geometry_locked_trace": geometry_locked_trace,
        "coverage_traces": coverage_traces,
        "coverage_traces": coverage_traces,
        "cta_intent_proof_hash": cta_intent_proof_hash,
    }
    snapshot = {
        "schema": "bending_fail_governs_ladder_implementation_snapshot.v1",
        "status": "PENDING",
        "generated_at": stamp,
        "artifact_path": str(artifact_path),
        "report_path": str(report_path),
        "contract_path": str(CONTRACT_PATH),
        "contract_family_id": str(family_identity().get("family_id") or ""),
        "live_selected_family": live_selected_family,
        "contract_ladder_order": list(EXPECTED_LADDER_ORDER),
        "contract_lanes": contract_lanes,
        "target_band": {
            "lower": float(target.get("lower") or 0.0),
            "upper": float(target.get("upper") or 0.0),
            "source": "contract.family_objective.target_band",
        },
        "utilisation_definitions": utilisation_definitions(),
        "depth_width_rule": depth_width_rule(),
        "geometry_unlocked_trace": geometry_unlocked_trace,
        "geometry_locked_trace": geometry_locked_trace,
        "selected_recommendation_lane": geometry_unlocked_trace.get("selected_recommendation_lane"),
        "accepted_lane_evidence": geometry_unlocked_trace.get("accepted_lane_evidence"),
        "rejected_lane_evidence": geometry_unlocked_trace.get("rejected_lane_evidence"),
        "final_bending_utilisation": geometry_unlocked_trace.get("final_bending_utilisation"),
        "target_band_status": geometry_unlocked_trace.get("target_band_status"),
        "exact_stop_no_valid_strategy_status": {
            "exact_stop": geometry_unlocked_trace.get("exact_stop_status"),
            "no_valid_strategy": geometry_unlocked_trace.get("no_valid_strategy_status"),
        },
        "cta_intent_proof_hash": cta_intent_proof_hash,
        "bottom_reo_lock_status": bottom_lock.get("status"),
        "bottom_reo_lock_artifact": bottom_lock.get("artifact"),
        "product_path_status": product.get("status"),
        "product_path_artifact": product.get("artifact"),
        "ladder_proof_surface": ladder_proof_surface,
        "shared_exclusions_asserted_absent": sorted(FORBIDDEN_PROOF_KEYS),
        "failures": [],
    }
    snapshot["failures"] = _assert_snapshot(snapshot)
    snapshot["status"] = "PASS" if not snapshot["failures"] else "FAIL"
    snapshot["snapshot_hash"] = _stable_hash(
        {
            "contract_ladder_order": snapshot["contract_ladder_order"],
            "geometry_unlocked_trace": geometry_unlocked_trace,
            "geometry_locked_trace": geometry_locked_trace,
            "cta_intent_proof_hash": cta_intent_proof_hash,
            "failures": snapshot["failures"],
        }
    )
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(
        json.dumps(
            {
                "status": snapshot["status"],
                "artifact": str(artifact_path),
                "report": str(report_path),
                "failures": snapshot["failures"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
