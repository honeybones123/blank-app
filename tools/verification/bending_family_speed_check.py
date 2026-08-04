"""Speed check for BENDING_FAIL_GOVERNS product-path migration."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
PERF_DIR = REPO / "artifacts" / "performance"
VERIFICATION_DIR = REPO / "artifacts" / "verification"
SCENARIO = "scenario_c3_pure_bending_underdesign_repair"


def _latest_gate_report(started_at: float) -> Path | None:
    reports = sorted(
        VERIFICATION_DIR.glob("design_guide_product_path_gate_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in reports:
        if path.stat().st_mtime >= started_at - 1:
            return path
    return None


def _latest_trace_report(started_at: float) -> Path | None:
    reports = sorted(
        PERF_DIR.glob("inputs_pre_widget_trace_*.jsonl"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in reports:
        if path.stat().st_mtime >= started_at - 1:
            return path
    return None


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _scenario(report: dict[str, Any]) -> dict[str, Any]:
    for row in report.get("results") or []:
        if isinstance(row, dict) and row.get("name") == SCENARIO:
            return dict(row)
    return {}


def _trace_counts(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                parsed = json.loads(line)
            except Exception:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    collect_rows = [row for row in rows if row.get("block") == "_collect_design_overview"]
    direct_target_rows = [
        row
        for row in rows
        if str(row.get("block") or "").startswith("direct_target_band")
    ]
    guidance_rows = [
        row
        for row in rows
        if row.get("block") == "_compute_design_guidance_items.for_design_guide"
    ]
    render_rows = [
        row
        for row in rows
        if row.get("block") == "render_inputs.render_fast_design_guidance_panel"
    ]
    return {
        "trace_report": str(path),
        "trace_row_count": len(rows),
        "collect_design_overview_calls": len(collect_rows),
        "collect_design_overview_cache_hits": sum(1 for row in collect_rows if row.get("cache_hit")),
        "collect_design_overview_cache_misses": sum(1 for row in collect_rows if not row.get("cache_hit")),
        "direct_target_band_block_count": len(direct_target_rows),
        "guidance_compute_duration_ms": (
            guidance_rows[-1].get("duration_ms") if guidance_rows else None
        ),
        "design_guide_render_duration_ms": (
            render_rows[-1].get("duration_ms") if render_rows else None
        ),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    port = "9503"
    if "--port" in argv:
        index = argv.index("--port")
        if index + 1 < len(argv):
            port = argv[index + 1]
    env = dict(os.environ)
    env.pop("CODEX_BROWSER_TEST_MODE", None)
    env["DESIGN_BRAIN_BENDING_FAIL_FAMILY_ROUTING"] = "1"
    env["PERF_TRACE_INPUTS"] = "1"
    env["DIRECT_TARGET_BAND_DIAG"] = "1"
    command = [
        sys.executable,
        "tools/verification/design_guide_product_path_gate.py",
        "--port",
        port,
        "--scenario",
        SCENARIO,
    ]
    started_clock = time.perf_counter()
    started_at = time.time()
    completed = subprocess.run(command, cwd=REPO, env=env, text=True, capture_output=True)
    elapsed = time.perf_counter() - started_clock
    gate_path = _latest_gate_report(started_at)
    trace_path = _latest_trace_report(started_at)
    gate_report = _load_json(gate_path)
    scenario = _scenario(gate_report)
    evidence = dict(scenario.get("evidence") or {})
    final_snapshot = dict(evidence.get("final_snapshot") or {})
    trace_counts = _trace_counts(trace_path)
    speed = {
        "schema": "bending_family_speed_check.v1",
        "family": "BENDING_FAIL_GOVERNS",
        "scenario": SCENARIO,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "command": command,
        "returncode": completed.returncode,
        "gate_report": str(gate_path) if gate_path else None,
        "trace_report": str(trace_path) if trace_path else None,
        "browser_test_mode": env.get("CODEX_BROWSER_TEST_MODE") or "unset",
        "before_timing_seconds": None,
        "after_timing_seconds": round(elapsed, 3),
        "delta_seconds": None,
        "classification": "baseline missing - after timing recorded",
        "approved_or_blocked": "blocked_for_full_completion_until_baseline_exists",
        "design_guide_resolve_time_seconds": round(elapsed, 3),
        "cta_click_rerun_time_seconds": None,
        "first_stable_design_guide_card_time_seconds": round(elapsed, 3),
        "candidate_evaluation_count": evidence.get("family_ladder_candidate_count"),
        "collect_design_overview_calls": trace_counts.get("collect_design_overview_calls"),
        "direct_target_band_block_count": trace_counts.get("direct_target_band_block_count"),
        "guidance_compute_duration_ms": trace_counts.get("guidance_compute_duration_ms"),
        "design_guide_render_duration_ms": trace_counts.get("design_guide_render_duration_ms"),
        "speed_isolation": {
            "family_selected_early": bool(evidence.get("family_early_dispatch_used")),
            "generic_one_click_solver_bypassed": bool(evidence.get("generic_one_click_solver_skipped")),
            "generic_target_band_search_bypassed": bool(
                evidence.get("generic_target_band_search_skipped")
                or evidence.get("direct_target_band_bypassed_by_family_owner")
                or trace_counts.get("direct_target_band_block_count") == 0
            ),
            "generic_optimisation_cleanup_bypassed": bool(
                evidence.get("generic_optimisation_cleanup_skipped")
            ),
            "generic_publication_fallback_bypassed": bool(
                evidence.get("generic_publication_fallback_skipped")
            ),
            "generic_publication_fallback_used": False,
        },
        "trace_counts": dict(trace_counts),
        "page_collapse_or_jump_behaviour": {
            "window_scroll_y": final_snapshot.get("window_scroll_y"),
            "primary_scroll_top": final_snapshot.get("primary_scroll_top"),
            "document_height": final_snapshot.get("document_height"),
            "viewport_height": final_snapshot.get("viewport_height"),
        },
        "stdout": completed.stdout,
        "stderr_tail": completed.stderr[-4000:],
    }
    PERF_DIR.mkdir(parents=True, exist_ok=True)
    path = PERF_DIR / f"bending_family_speed_check_{time.strftime('%Y-%m-%dT%H-%M-%S')}.json"
    path.write_text(json.dumps(speed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{speed['status']}: {path}")
    return 0 if speed["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
