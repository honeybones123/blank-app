"""Post-zero-authority browser/live Inputs smoothness baseline.

Proof-only verifier. This script does not change app behaviour. It runs the
existing browser/live smoothness profiler, then normalizes the result into the
post Design Brain zero-authority baseline shape used to choose the next guarded
reuse/bypass target.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification import design_guide_browser_live_smoothness_profile as live_profile  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest_payload(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda item: item.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}, "status": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "payload": {},
            "status": "UNREADABLE",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "path": str(path), "payload": payload, "status": payload.get("status")}


def _milestone_ms(row: dict[str, Any], name: str) -> Any:
    return ((row.get("milestones") or {}).get(name) or {}).get("elapsed_ms")


def _timing_marker_names(row: dict[str, Any]) -> list[str]:
    timing = dict(row.get("timing") or {})
    names: list[str] = []
    for event in timing.get("events_tail") or []:
        if isinstance(event, dict):
            name = str(event.get("name") or "").strip()
            if name:
                names.append(name)
    return names


def _top_plotly_mutations(row: dict[str, Any]) -> list[dict[str, Any]]:
    churn = dict(row.get("churn") or {})
    out: list[dict[str, Any]] = []
    for item in churn.get("mutation_top_attribution") or []:
        if not isinstance(item, dict):
            continue
        owner = str(item.get("owner") or item.get("family") or "")
        label = str(item.get("label") or "")
        if "plotly" in owner.lower() or "chart" in owner.lower() or "plotly" in label.lower():
            out.append(item)
    return out


def _model_diagram_rebuild_estimate(row: dict[str, Any]) -> dict[str, Any]:
    plotly_rows = _top_plotly_mutations(row)
    records = 0
    added = 0
    removed = 0
    for item in plotly_rows:
        for key, dest in (("records", "records"), ("added", "added"), ("removed", "removed")):
            try:
                value = int(item.get(key) or 0)
            except Exception:
                value = 0
            if dest == "records":
                records += value
            elif dest == "added":
                added += value
            else:
                removed += value
    return {
        "plotly_or_chart_mutation_rows": plotly_rows,
        "plotly_or_chart_mutation_records": records,
        "plotly_or_chart_nodes_added": added,
        "plotly_or_chart_nodes_removed": removed,
        "model_diagram_rebuild_count_estimate": 1 if records or added or removed else 0,
    }


def _scenario_baseline(row: dict[str, Any]) -> dict[str, Any]:
    counters = dict(row.get("counters") or {})
    candidate = dict(counters.get("candidate_evaluation") or {})
    timing = dict(row.get("timing") or {})
    layout = dict(row.get("layout") or {})
    model = _model_diagram_rebuild_estimate(row)
    return {
        "scenario_id": row.get("scenario_id"),
        "action": row.get("action"),
        "skipped": bool(row.get("skipped")),
        "skip_reason": row.get("skip_reason"),
        "rerun_seq": row.get("rerun_seq"),
        "elapsed_ms": row.get("elapsed_ms"),
        "rerun_cause_markers_tail": _timing_marker_names(row),
        "time_to_inputs_heading_ms": _milestone_ms(row, "inputs_heading"),
        "time_to_summary_cards_ms": _milestone_ms(row, "summary_cards"),
        "time_to_model_diagram_panel_ms": None,
        "time_to_batch_design_ms": _milestone_ms(row, "batch_design"),
        "time_to_design_guide_shell_ms": _milestone_ms(row, "design_guide_shell"),
        "time_to_final_design_guide_publication_ms": _milestone_ms(row, "final_design_guide_publication"),
        "time_to_card_render_model_ms": _milestone_ms(row, "card_render_model"),
        "time_to_rendered_design_guide_card_ms": _milestone_ms(row, "rendered_design_guide_card"),
        "summary_rebuild_count": 1 if timing.get("summary_render") else 0,
        "model_diagram_rebuild": model,
        "design_guide_render_model_rebuild_count": counters.get("card_render_model_rebuild_count"),
        "design_guide_render_model_bypass_count": counters.get("card_render_model_bypass_count"),
        "publication_rebuild_count": counters.get("publication_rebuild_count"),
        "publication_stamp_bypass_count": counters.get("publication_stamp_bypass_count"),
        "cta_apply_binding_count": counters.get("cta_apply_binding_count"),
        "session_debug_stamp_count": counters.get("session_debug_stamp_count"),
        "candidate_evaluation_count": candidate.get("count"),
        "candidate_evaluation_cache_misses": candidate.get("cache_misses"),
        "candidate_evaluation_total_ms": candidate.get("total_ms"),
        "final_publication_hash": counters.get("final_publication_hash"),
        "final_publication_display_hash": counters.get("final_publication_display_hash"),
        "final_publication_cta_hash": counters.get("final_publication_cta_hash"),
        "layout_shift_total": layout.get("layout_shift_total"),
        "layout_area_deltas": layout.get("area_deltas"),
        "layout_shift_entries_tail": layout.get("layout_shift_entries_tail"),
        "dom_mutation_count_total": (row.get("churn") or {}).get("mutation_count_total"),
        "dom_last_mutation_batch_size": (row.get("churn") or {}).get("last_mutation_batch_size"),
        "dom_mutation_top_attribution": (row.get("churn") or {}).get("mutation_top_attribution"),
        "raw_snapshot_hash": row.get("snapshot_hash"),
    }


def _aggregate(scenarios: list[dict[str, Any]], hotspots: list[dict[str, Any]]) -> dict[str, Any]:
    measured = [row for row in scenarios if not row.get("skipped")]
    stable = [row for row in measured if row.get("scenario_id") in {"stable_no_input_reload_1", "stable_no_input_reload_2"}]
    reruns = {row.get("rerun_seq") for row in measured if row.get("rerun_seq") is not None}
    stable_summary_rebuilds = sum(int(row.get("summary_rebuild_count") or 0) for row in stable)
    stable_model_rebuilds = sum(
        int(((row.get("model_diagram_rebuild") or {}).get("model_diagram_rebuild_count_estimate") or 0))
        for row in stable
    )
    stable_card_rebuilds = sum(int(row.get("design_guide_render_model_rebuild_count") or 0) for row in stable)
    stable_publication_rebuilds = sum(int(row.get("publication_rebuild_count") or 0) for row in stable)
    return {
        "total_measured_scenarios": len(measured),
        "total_rerun_count": len(reruns),
        "stable_no_change_rerun_count": len(stable),
        "stable_no_change_rebuild_counts": {
            "summary_rebuild_count": stable_summary_rebuilds,
            "model_diagram_rebuild_estimate": stable_model_rebuilds,
            "design_guide_render_model_rebuild_count": stable_card_rebuilds,
            "publication_rebuild_count": stable_publication_rebuilds,
        },
        "highest_measured_hotspot": hotspots[0] if hotspots else None,
        "recommended_first_implementation_target": _recommended_target(hotspots, stable),
    }


def _recommended_target(hotspots: list[dict[str, Any]], stable_rows: list[dict[str, Any]]) -> str:
    stable_model_rebuilds = sum(
        int(((row.get("model_diagram_rebuild") or {}).get("model_diagram_rebuild_count_estimate") or 0))
        for row in stable_rows
    )
    if stable_model_rebuilds:
        return "model/diagram panel render reuse keyed by model/diagram state fingerprint"
    if hotspots:
        top = hotspots[0]
        if top.get("class") == "B":
            return "candidate evaluation/search reuse keyed by existing guidance/input fingerprint"
        if top.get("class") == "C":
            return "Design Guide publication/card render-model reuse keyed by publication/display hash"
        if top.get("class") == "E":
            return "layout/placeholder stability proof before UI changes"
    return "rerun trigger/source profiling before implementing another bypass"


def _markdown(payload: dict[str, Any]) -> str:
    agg = dict(payload.get("aggregate") or {})
    lines = [
        "# Post-Zero-Authority Browser/Live Smoothness Baseline",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Recipe: `{payload.get('recipe')}`",
        f"- Base URL: `{payload.get('base_url')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- New bypasses implemented: `{payload.get('new_bypasses_implemented')}`",
        f"- Zero-authority lock status before baseline: `{((payload.get('locks') or {}).get('zero_authority') or {}).get('status')}`",
        "",
        "## Aggregate",
        "",
        f"- Total rerun count: `{agg.get('total_rerun_count')}`",
        f"- Stable no-change reruns measured: `{agg.get('stable_no_change_rerun_count')}`",
        f"- Stable no-change rebuild counts: `{json.dumps(agg.get('stable_no_change_rebuild_counts'), sort_keys=True)}`",
        f"- Recommended first implementation target: `{agg.get('recommended_first_implementation_target')}`",
        "",
        "## Scenario Baseline",
        "",
        "| Scenario | Rerun | Inputs ms | Summary ms | Batch ms | DG shell ms | Publication ms | Card model ms | DG card ms | Summary rebuilds | Model rebuild est. | Pub rebuilds | Card rebuilds | CTA binds | Session/debug stamps | CLS |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload.get("scenarios") or []:
        model = dict(row.get("model_diagram_rebuild") or {})
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("scenario_id")),
                    str(row.get("rerun_seq")),
                    str(row.get("time_to_inputs_heading_ms")),
                    str(row.get("time_to_summary_cards_ms")),
                    str(row.get("time_to_batch_design_ms")),
                    str(row.get("time_to_design_guide_shell_ms")),
                    str(row.get("time_to_final_design_guide_publication_ms")),
                    str(row.get("time_to_card_render_model_ms")),
                    str(row.get("time_to_rendered_design_guide_card_ms")),
                    str(row.get("summary_rebuild_count")),
                    str(model.get("model_diagram_rebuild_count_estimate")),
                    str(row.get("publication_rebuild_count")),
                    str(row.get("design_guide_render_model_rebuild_count")),
                    str(row.get("cta_apply_binding_count")),
                    str(row.get("session_debug_stamp_count")),
                    str(row.get("layout_shift_total")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Top Hotspots", ""])
    for idx, item in enumerate(payload.get("top_hotspots") or [], start=1):
        lines.append(f"{idx}. `{item.get('class')}` {item.get('name')} score `{item.get('score')}`")
    lines.extend(["", "## Raw Profile", ""])
    raw = payload.get("raw_profile_artifact") or {}
    lines.append(f"- Path: `{raw.get('path')}`")
    lines.append(f"- Status: `{raw.get('status')}`")
    lines.extend(["", "## Notes", ""])
    lines.append("This is baseline-only. It does not implement reuse, caching, bypasses, deletion, or UI changes.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8584)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--recipe", default=live_profile.DEFAULT_RECIPE)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout-s", type=float, default=60.0)
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    created_at = _stamp()
    profile_started = time.time()
    profile_args = [
        "--recipe",
        str(args.recipe),
        "--timeout-s",
        str(args.timeout_s),
    ]
    if args.base_url:
        profile_args.extend(["--base-url", str(args.base_url)])
    else:
        profile_args.extend(["--port", str(args.port)])
    if args.headed:
        profile_args.append("--headed")

    profile_exit = live_profile.main(profile_args)
    raw = _latest_payload("design_guide_browser_live_smoothness_profile")
    raw_payload = dict(raw.get("payload") or {})
    scenarios = [_scenario_baseline(dict(row)) for row in raw_payload.get("scenarios") or []]
    hotspots = list(raw_payload.get("all_hotspot_scores") or raw_payload.get("top_hotspots") or [])
    aggregate = _aggregate(scenarios, hotspots)
    zero_authority = _latest_payload("design_brain_inputs_page_zero_authority_inventory_lock")
    status = "PASS"
    errors: list[str] = []
    if profile_exit != 0:
        status = "FAIL"
        errors.append(f"raw_smoothness_profile_exit_{profile_exit}")
    elif raw.get("status") not in {"PASS", "PARTIAL"}:
        status = "FAIL"
        errors.append(f"raw_smoothness_profile_status_{raw.get('status')}")
    elif not scenarios or not any(not row.get("skipped") for row in scenarios):
        status = "FAIL"
        errors.append("no_measured_browser_scenarios")
    elif raw.get("status") == "PARTIAL":
        status = "PARTIAL"
    if zero_authority.get("status") not in {"PASS", "LOCKED"}:
        status = "PARTIAL" if status == "PASS" else status
        errors.append(f"zero_authority_lock_not_current_pass:{zero_authority.get('status')}")

    payload = {
        "schema": "design_guide_post_zero_authority_browser_live_smoothness_baseline.v1",
        "status": status,
        "created_at": created_at,
        "recipe": args.recipe,
        "base_url": args.base_url or f"http://127.0.0.1:{args.port}",
        "product_behaviour_changed": False,
        "new_bypasses_implemented": False,
        "code_deleted": False,
        "profile_runtime_sec": round(time.time() - profile_started, 3),
        "raw_profile_artifact": {"path": raw.get("path"), "status": raw.get("status")},
        "locks": {
            "zero_authority": {"path": zero_authority.get("path"), "status": zero_authority.get("status")},
        },
        "aggregate": aggregate,
        "scenarios": scenarios,
        "top_hotspots": hotspots[:5],
        "raw_profile_recommended_first_fix": raw_payload.get("recommended_first_fix"),
        "errors": errors,
    }
    json_path = ARTIFACT_DIR / f"design_guide_post_zero_authority_browser_live_smoothness_baseline_{created_at}.json"
    md_path = AUDIT_DIR / f"design_guide_post_zero_authority_browser_live_smoothness_baseline_{created_at}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_post_zero_authority_browser_live_smoothness_baseline {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print(f"recommended_first_target={aggregate.get('recommended_first_implementation_target')}")
    if errors:
        print("errors=" + json.dumps(errors, sort_keys=True))
    return 0 if status in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
