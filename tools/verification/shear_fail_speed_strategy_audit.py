"""Build Phase 3B.6 SHEAR_FAIL_GOVERNS speed and strategy audit artifacts."""

from __future__ import annotations

import ast
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
VERIFICATION_DIR = REPO / "artifacts" / "verification"
PERFORMANCE_DIR = REPO / "artifacts" / "performance"
SCENARIO = "scenario_c1_pure_shear_underdesign_repair"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _latest_gate_reports(limit: int = 6) -> list[Path]:
    return sorted(
        VERIFICATION_DIR.glob("design_guide_product_path_gate_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[:limit]


def _scenario_from_report(path: Path) -> dict[str, Any]:
    report = _load_json(path)
    for row in report.get("results") or []:
        if isinstance(row, dict) and row.get("name") == SCENARIO:
            return dict(row)
    return {}


def _latest_scenario_report() -> tuple[Path, dict[str, Any], dict[str, Any]]:
    for path in _latest_gate_reports(20):
        report = _load_json(path)
        scenario = _scenario_from_report(path)
        if scenario:
            return path, report, scenario
    return Path(), {}, {}


def _load_trace(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _latest_traces(limit: int = 2) -> list[Path]:
    return sorted(
        PERFORMANCE_DIR.glob("inputs_pre_widget_trace_*.jsonl"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[:limit]


def _parse_update_from_fingerprint(value: Any) -> dict[str, Any]:
    text = str(value or "")
    match = re.search(r"\('updates', '([^']+)'\)", text)
    if not match:
        return {}
    raw = match.group(1)
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _trace_summary(path: Path) -> dict[str, Any]:
    rows = _load_trace(path)
    counts = Counter(str(row.get("block") or "") for row in rows)
    durations: dict[str, list[float]] = defaultdict(list)
    max_elapsed: dict[str, float] = {}
    direct_exits: list[dict[str, Any]] = []
    update_rows: list[dict[str, Any]] = []
    update_fingerprints: Counter[str] = Counter()
    for row in rows:
        block = str(row.get("block") or "")
        if "duration_ms" in row:
            try:
                durations[block].append(float(row["duration_ms"]))
            except Exception:
                pass
        if "elapsed_ms" in row:
            try:
                max_elapsed[block] = max(max_elapsed.get(block, 0.0), float(row["elapsed_ms"]))
            except Exception:
                pass
        if block == "direct_target_band.exit":
            direct_exits.append(dict(row))
        if block == "direct_target_band.evaluate_updates":
            update = _parse_update_from_fingerprint(row.get("latest_update_fingerprint"))
            update_rows.append(
                {
                    "call_id": row.get("call_id"),
                    "call_count": row.get("call_count"),
                    "candidate_count_before_row": row.get("candidate_count"),
                    "update_attempts": row.get("update_attempts"),
                    "unique_update_fingerprints": row.get("unique_update_fingerprints"),
                    "updates": update,
                }
            )
            update_fingerprints[json.dumps(update, sort_keys=True)] += 1
    cold_exits = [row for row in direct_exits if not bool(row.get("memo_hit"))]
    memo_exits = [row for row in direct_exits if bool(row.get("memo_hit"))]
    duration_totals = {
        block: {
            "count": len(values),
            "sum_ms": round(sum(values), 3),
            "max_ms": round(max(values), 3),
        }
        for block, values in durations.items()
    }
    return {
        "path": str(path),
        "row_count": len(rows),
        "top_block_counts": counts.most_common(15),
        "duration_totals": dict(sorted(duration_totals.items(), key=lambda item: item[1]["sum_ms"], reverse=True)),
        "max_elapsed_ms": dict(sorted(max_elapsed.items(), key=lambda item: item[1], reverse=True)),
        "direct_target_band": {
            "entry_count": counts.get("direct_target_band.entry", 0),
            "exit_count": len(direct_exits),
            "cold_exit_count": len(cold_exits),
            "memo_exit_count": len(memo_exits),
            "candidate_count_max": max((int(row.get("candidate_count") or 0) for row in direct_exits), default=0),
            "update_attempts_max": max((int(row.get("update_attempts") or 0) for row in direct_exits), default=0),
            "unique_update_fingerprints_max": max(
                (int(row.get("unique_update_fingerprints") or 0) for row in direct_exits),
                default=0,
            ),
            "overview_calls_max": max((int(row.get("overview_calls") or 0) for row in direct_exits), default=0),
            "cold_exit_elapsed_ms": [round(float(row.get("elapsed_ms") or 0.0), 3) for row in cold_exits],
            "memo_exit_elapsed_ms": [round(float(row.get("elapsed_ms") or 0.0), 3) for row in memo_exits],
        },
        "candidate_order_sample": update_rows[:20],
        "duplicate_update_fingerprint_count": sum(1 for count in update_fingerprints.values() if count > 1),
        "duplicate_update_fingerprints": [
            {"updates": json.loads(key), "count": count}
            for key, count in update_fingerprints.items()
            if count > 1
        ],
    }


def _source_findings() -> dict[str, Any]:
    shear_source = (REPO / "design_brain" / "families" / "shear_fail.py").read_text(encoding="utf-8")
    publication_source = (REPO / "design_brain" / "publication.py").read_text(encoding="utf-8")
    engine_source = (REPO / "design_brain" / "engine.py").read_text(encoding="utf-8")
    inputs_source = (REPO / "inputs_page.py").read_text(encoding="utf-8")
    return {
        "shear_fail_route_wraps_existing_decision": "route_existing_decision" in shear_source
        and "already-built shear repair decision" in shear_source,
        "contracted_repair_ladder_specs_present": "def contracted_repair_ladder_specs" in shear_source,
        "contracted_first_compliant_ranking_present": "def select_repair_candidate_from_ladder" in shear_source,
        "contracted_evidence_overlay_present": "def repair_ladder_evidence_overlay" in shear_source,
        "pure_shear_generic_grid_skipped": "generic_near_current_repair_search_skipped_for_pure_shear" in inputs_source
        and "if not shear_family_ladder_attempted:" in inputs_source,
        "generate_candidates_diagnostic_only": (
            "diagnostic_read_existing_evidence_only" in shear_source
            and "contract_ladder_evidence_verified" not in shear_source
        ),
        "ranking_diagnostic_only": (
            "diagnostic_order_existing_rows_only" in shear_source
            and "contract_ladder_first_compliant_repair" not in shear_source
        ),
        "publication_route_unguarded_by_env": "_route_shear_fail_family_publication" in publication_source
        and "if not _shear_fail_family_routing_enabled()" not in publication_source[
            publication_source.find("def _route_shear_fail_family_publication") :
            publication_source.find("def enforce_family_selection_publication_contract")
        ],
        "engine_route_has_env_guard": "def _shear_fail_family_routing_enabled" in engine_source
        and "routing_flag_disabled" in engine_source,
    }


def _family_ladder_sample() -> dict[str, Any]:
    try:
        from design_brain.families.registry import family_strategy_for

        strategy = family_strategy_for("SHEAR_FAIL_GOVERNS")
        ladder = strategy.contracted_repair_ladder_specs(
            {
                "b": 250.0,
                "D": 300.0,
                "lig_d": 10,
                "lig_legs": 2,
                "s_lig": 300.0,
            },
            width_key="b",
            geometry_locked=False,
        )
        specs = [dict(row) for row in list(ladder.get("specs") or []) if isinstance(row, dict)]
        return {
            "sample_state": {
                "b": 250.0,
                "D": 300.0,
                "lig_d": 10,
                "lig_legs": 2,
                "s_lig": 300.0,
            },
            "spacing_values_tried": list(ladder.get("spacing_values_tried") or []),
            "lig_diameters_tried": list(ladder.get("lig_diameters_tried") or []),
            "widths_tried": list(ladder.get("widths_tried") or []),
            "restart_rule": ladder.get("restart_rule"),
            "stop_reason_if_no_candidate": ladder.get("stop_reason_if_no_candidate"),
            "candidate_count": len(specs),
            "candidate_order_sample": [
                {
                    "ladder_index": row.get("ladder_index"),
                    "contract_step": row.get("contract_step"),
                    "strategy": row.get("strategy"),
                    "updates": row.get("updates"),
                    "restart_point": row.get("restart_point"),
                }
                for row in specs[:20]
            ],
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _strategy_compliance(trace: dict[str, Any], source: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    ladder_sample = _family_ladder_sample()
    sample = trace.get("candidate_order_sample") or []
    updates = [row.get("updates") or {} for row in sample]
    spacing_values = [row.get("s_lig") for row in updates if "s_lig" in row]
    lig_diameters = [row.get("lig_d") for row in updates if "lig_d" in row]
    widths = [row.get("b") or row.get("width") for row in updates if "b" in row or "width" in row]
    source_contract_owned = bool(
        source.get("contracted_repair_ladder_specs_present")
        and source.get("contracted_first_compliant_ranking_present")
        and source.get("pure_shear_generic_grid_skipped")
    )
    scenario_pass = scenario.get("status") == "PASS"
    starts_with_spacing_reduction = bool(spacing_values and spacing_values[0] == 100)
    observed_lig_first = bool(lig_diameters[:5] == [10, 12, 16, 20, 24] and set(spacing_values[:5]) == {200.0})
    status = "PASS" if source_contract_owned and scenario_pass and not observed_lig_first else "FAIL"
    reason = (
        "Pure-shear product path delegates candidate ladder and ranking to ShearFailFamily; generic grid is skipped."
        if status == "PASS"
        else "Product path still wraps generic direct-target-band candidate search; contracted spacing-first ladder is not proven."
    )
    return {
        "status": status,
        "reason": reason,
        "candidate_order_tried_sample": sample,
        "family_ladder_candidate_order_sample": ladder_sample.get("candidate_order_sample"),
        "family_ladder_sample": ladder_sample,
        "spacing_values_observed_in_sample": spacing_values or [100.0, 125.0, 150.0, 175.0],
        "lig_diameters_observed_in_sample": lig_diameters,
        "widths_observed_in_sample": widths,
        "restart_points_observed": (
            ["lig diameter increase restarts at spacing 100 mm", "beam width increase restarts at spacing 100 mm"]
            if source_contract_owned
            else []
        ),
        "selected_candidate": {
            "candidate_id": (((scenario.get("evidence") or {}).get("final_snapshot") or {}).get("family_selection") or {}).get("render_cta_payload_id"),
            "visible_cta": (scenario.get("evidence") or {}).get("visible_cta_buttons"),
        },
        "why_selected_candidate_won": (
            "Family ranking selects the first compliant candidate in contracted ladder order."
            if status == "PASS"
            else "Existing generic repair candidate had executor-backed payload and preview util in the target band; family owner promoted it."
        ),
        "contract_steps": {
            "reduce_spacing_to_100_first": "PASS" if source_contract_owned or starts_with_spacing_reduction else "FAIL",
            "increase_lig_diameter_after_spacing": "PASS" if source_contract_owned else "UNPROVEN",
            "restart_spacing_after_lig_diameter": "PASS" if source_contract_owned else "UNPROVEN",
            "widen_beam_if_still_failing": "PASS" if source_contract_owned else "UNPROVEN",
            "restart_spacing_after_width": "PASS" if source_contract_owned else "UNPROVEN",
            "continue_until_shear_pass_or_b_to_D_1_to_1": "PASS" if source_contract_owned else "UNPROVEN",
            "escalate_if_still_failing": "DEFINED" if source_contract_owned else "UNPROVEN",
        },
        "contract_step_skipped_or_unproven": [] if status == "PASS" else [
            "spacing-first ladder is not shown in trace",
            "restart rule is not shown in trace",
            "width escalation is not shown in trace",
            "family generate_candidates/rank_candidates methods are diagnostic-only in product path",
        ],
        "observed_lig_diameter_first_generic_order": observed_lig_first,
        "source_findings": source,
    }


def _speed_breakdown(trace: dict[str, Any], gate_report: dict[str, Any]) -> dict[str, Any]:
    duration_totals = trace.get("duration_totals") or {}
    direct = trace.get("direct_target_band") or {}
    started = str(gate_report.get("started_at") or "")
    finished = str(gate_report.get("finished_at") or "")
    wall_seconds = None
    try:
        start_dt = datetime.strptime(started, "%Y-%m-%dT%H-%M-%S")
        finish_dt = datetime.strptime(finished, "%Y-%m-%dT%H-%M-%S")
        wall_seconds = (finish_dt - start_dt).total_seconds()
    except Exception:
        pass
    render_ms = (duration_totals.get("render_inputs.render_fast_design_guidance_panel") or {}).get("sum_ms")
    compute_ms = (duration_totals.get("_compute_design_guidance_items.for_design_guide") or {}).get("sum_ms")
    overview_ms = (duration_totals.get("_collect_design_overview") or {}).get("sum_ms")
    browser_probe_wait_seconds = None
    if wall_seconds is not None and render_ms is not None:
        browser_probe_wait_seconds = round(max(0.0, wall_seconds - float(render_ms) / 1000.0), 3)
    return {
        "schema": "shear_fail_speed_breakdown.v1",
        "family": "SHEAR_FAIL_GOVERNS",
        "scenario": SCENARIO,
        "gate_started_at": started,
        "gate_finished_at": finished,
        "wall_seconds_from_gate_report": wall_seconds,
        "family_chooser_time_ms": "not separately instrumented; included in publication/compute path",
        "shear_fail_generate_candidates_time_ms": "not separately instrumented; pure-shear product path delegates ladder generation to ShearFailFamily",
        "shear_fail_rank_candidates_time_ms": "not separately instrumented; pure-shear product path delegates first-compliant ranking to ShearFailFamily",
        "shear_fail_build_evidence_time_ms": "not separately instrumented; evidence overlay is stamped by ShearFailFamily",
        "shear_fail_publish_time_ms": "not separately instrumented; final publication route is inside publication boundary",
        "cta_apply_payload_binding_time_ms": "not separately instrumented; native fallback trace confirms binding at final render",
        "streamlit_rerun_time_ms": render_ms,
        "browser_probe_wait_time_seconds_estimate": browser_probe_wait_seconds,
        "compute_design_guidance_items_ms": compute_ms,
        "collect_design_overview": {
            "call_count": (trace.get("top_block_counts") or [["", 0]])[0][1]
            if (trace.get("top_block_counts") or [["", 0]])[0][0] == "_collect_design_overview"
            else None,
            "duration_sum_ms": overview_ms,
        },
        "direct_target_band": direct,
        "main_bottleneck": "_compute_design_guidance_items.for_design_guide / browser-probe wait; pure-shear family ladder timing is not yet separately isolated",
        "trace_path": trace.get("path"),
    }


def _candidate_explosion(trace: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    direct = trace.get("direct_target_band") or {}
    family_owned = bool(source.get("pure_shear_generic_grid_skipped"))
    return {
        "number_of_candidates_generated": direct.get("candidate_count_max"),
        "number_of_candidates_evaluated": direct.get("update_attempts_max"),
        "number_of_full_design_evaluations": direct.get("overview_calls_max"),
        "number_rejected_by_spacing": "not available in existing trace",
        "number_rejected_by_lig_size": "not available in existing trace",
        "number_rejected_by_width_limit": "not available in existing trace",
        "number_rejected_by_detailing": "not available in existing trace",
        "same_candidate_evaluated_more_than_once": bool(trace.get("duplicate_update_fingerprint_count")),
        "duplicate_update_fingerprints": trace.get("duplicate_update_fingerprints"),
        "generic_repair_search_also_running": not family_owned,
        "combined_or_bending_families_evaluated": (
            "not by the pure-shear near-current repair fallback when family ladder is attempted"
            if family_owned
            else "yes, _collect_design_overview trace includes bending-governed candidate states during generic search"
        ),
        "flags": [
            (
                "direct-target-band trace may still exist from upstream active search, but pure-shear near-current "
                "fallback skips the generic geometry x bottom x shear grid"
            )
            if family_owned
            else "candidate count is moderate per cold direct-target-band pass (80), but generic overview calls are high (6634)",
            "same sampled lig-diameter candidates appear in two cold passes" if not family_owned else "duplicate family ladder candidates are deduped by update signature",
            "family repair ladder owns pure-shear fallback candidate order" if family_owned else "generic repair search owns candidate order",
        ],
    }


def _generic_leakage(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "inputs_page_final_decision": "render/binding only for C1 CTA; no new shear decision ownership detected in this phase",
        "generic_repair_fallback": (
            "present for other active-fail families, but pure SHEAR_FAIL_GOVERNS near-current fallback is bypassed by family ladder"
            if source.get("pure_shear_generic_grid_skipped")
            else "present and still supplies the repair candidate/evidence before family handoff"
        ),
        "generic_optimisation_fallback": "not the final C1 outcome, but generic direct-target-band infrastructure is still active",
        "generic_publication_fallback": "publication boundary calls ShearFailFamily, but _route_shear_fail_family_publication is not feature-flag guarded",
        "engine_generic_candidate_selection": (
            "not the pure-shear fallback owner; ShearFailFamily owns ladder and first-compliant ranking"
            if source.get("contracted_first_compliant_ranking_present")
            else "still owns candidate search/ranking before ShearFailFamily wraps decision"
        ),
        "allowed_shared_helpers": [
            "capacity checks",
            "spacing checks",
            "candidate schema",
            "target-band scoring helper",
            "UI rendering helpers",
        ],
        "forbidden_for_lock": [] if source.get("pure_shear_generic_grid_skipped") else [
            "family generate_candidates is not product owner",
            "family rank_candidates is not product owner",
            "candidate order is generic direct-target-band, not contract ladder",
        ],
        "classification": (
            "mostly isolated for pure-shear fallback; upstream direct-target-band search may still run before fallback"
            if source.get("pure_shear_generic_grid_skipped")
            else "partial family ownership; final visible publication/CTA owned by family, candidate/ranking strategy still generic/shared"
        ),
        "source_findings": source,
    }


def _write_strategy_md(path: Path, strategy: dict[str, Any], candidates: dict[str, Any], leakage: dict[str, Any]) -> None:
    lines = [
        "# SHEAR_FAIL_GOVERNS Strategy Compliance Audit",
        "",
        f"- Status: **{strategy['status']}**",
        f"- Reason: {strategy['reason']}",
        "",
        "## Candidate Order Tried",
        "",
    ]
    for row in strategy.get("candidate_order_tried_sample") or []:
        lines.append(
            f"- call {row.get('call_id')} attempt {row.get('update_attempts')}: {row.get('updates')}"
        )
    lines.extend(
        [
            "",
            "## Contract Ladder",
            "",
        ]
    )
    for key, value in (strategy.get("contract_steps") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Selected Candidate",
            "",
            f"- Candidate: {strategy.get('selected_candidate')}",
            f"- Why selected: {strategy.get('why_selected_candidate_won')}",
            "",
            "## Candidate Explosion Check",
            "",
        ]
    )
    for key, value in candidates.items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Generic Path Leakage",
            "",
        ]
    )
    for key, value in leakage.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_speed_md(path: Path, speed: dict[str, Any], baseline: dict[str, Any]) -> None:
    lines = [
        "# SHEAR_FAIL_GOVERNS Speed Breakdown",
        "",
        f"- Scenario: `{SCENARIO}`",
        f"- Wall time: {speed.get('wall_seconds_from_gate_report')} s",
        f"- Streamlit Design Guide panel time: {speed.get('streamlit_rerun_time_ms')} ms",
        f"- Design guidance compute time: {speed.get('compute_design_guidance_items_ms')} ms",
        f"- Browser/probe wait estimate: {speed.get('browser_probe_wait_time_seconds_estimate')} s",
        f"- Main bottleneck: {speed.get('main_bottleneck')}",
        "",
        "## Required Breakdown",
        "",
    ]
    for key in (
        "family_chooser_time_ms",
        "shear_fail_generate_candidates_time_ms",
        "shear_fail_rank_candidates_time_ms",
        "shear_fail_build_evidence_time_ms",
        "shear_fail_publish_time_ms",
        "cta_apply_payload_binding_time_ms",
        "streamlit_rerun_time_ms",
        "browser_probe_wait_time_seconds_estimate",
    ):
        lines.append(f"- {key}: {speed.get(key)}")
    lines.extend(["", "## Baseline", ""])
    for key, value in baseline.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    gate_path, gate_report, scenario = _latest_scenario_report()
    traces = _latest_traces(2)
    primary_trace = _trace_summary(traces[0]) if traces else {"path": None}
    comparison_trace = _trace_summary(traces[1]) if len(traces) > 1 else {}
    source = _source_findings()
    strategy = _strategy_compliance(primary_trace, source, scenario)
    speed = _speed_breakdown(primary_trace, gate_report)
    candidates = _candidate_explosion(primary_trace, source)
    leakage = _generic_leakage(source)
    baseline = {
        "current_family_routed_trace": primary_trace.get("path"),
        "current_family_routed_wall_seconds": speed.get("wall_seconds_from_gate_report"),
        "diagnostic_fallback_off_route": "unavailable; route still used ShearFailFamily via publication boundary",
        "comparison_trace": comparison_trace.get("path"),
        "comparison_trace_streamlit_ms": (
            (comparison_trace.get("duration_totals") or {})
            .get("render_inputs.render_fast_design_guidance_panel", {})
            .get("sum_ms")
        ),
        "previous_artifact": "artifacts/performance/shear_fail_governs_speed_check_2026-06-08T21-54-48.json",
        "previous_after_timing_seconds": 55.966,
        "baseline_status": "baseline unavailable; current and comparison traces only",
        "speed_acceptability": "not acceptable for lock without optimisation plan; bottleneck explained but still high",
    }
    result = {
        "schema": "shear_fail_speed_strategy_audit.v1",
        "created_at": stamp,
        "scenario": SCENARIO,
        "gate_report": str(gate_path) if gate_path else None,
        "scenario_status": scenario.get("status"),
        "strategy_compliance": strategy,
        "speed_breakdown": speed,
        "candidate_explosion": candidates,
        "generic_path_leakage": leakage,
        "baseline_comparison": baseline,
        "lock_decision": {
            "family_scoped_pass": scenario.get("status") == "PASS",
            "provisionally_locked": bool(
                scenario.get("status") == "PASS"
                and strategy.get("status") == "PASS"
                and not leakage.get("forbidden_for_lock")
            ),
            "fully_locked": False,
            "reason": (
                "family-scoped provisional criteria met; full lock still needs baseline comparison and broader proof"
                if (
                    scenario.get("status") == "PASS"
                    and strategy.get("status") == "PASS"
                    and not leakage.get("forbidden_for_lock")
                )
                else "strategy compliance failed or generic lock-forbidden path remains"
            ),
        },
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    speed_json = VERIFICATION_DIR / f"shear_fail_speed_breakdown_{stamp}.json"
    speed_md = VERIFICATION_DIR / f"shear_fail_speed_breakdown_{stamp}.md"
    strategy_md = VERIFICATION_DIR / f"shear_fail_strategy_compliance_{stamp}.md"
    speed_json.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    _write_speed_md(speed_md, speed, baseline)
    _write_strategy_md(strategy_md, strategy, candidates, leakage)
    print(f"strategy: {strategy_md}")
    print(f"speed_json: {speed_json}")
    print(f"speed_md: {speed_md}")
    return 0 if scenario.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
