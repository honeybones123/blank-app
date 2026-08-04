"""Verify trace-only stable render-reuse diagnostics.

This snapshot proves the Inputs summary panel and Design Guide panel record
stable-fingerprint reuse eligibility without changing render behaviour. It is
not a bypass and must not skip any visible render path.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_block(source: str, name: str) -> str:
    match = re.search(rf"^def {re.escape(name)}\(", source, re.MULTILINE)
    if not match:
        return ""
    next_match = re.search(r"^def\s+\w+\(", source[match.end() :], re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start() : end]


def _nested_function_block(source: str, name: str) -> str:
    match = re.search(rf"^\s{{4}}def {re.escape(name)}\(", source, re.MULTILINE)
    if not match:
        return ""
    next_match = re.search(r"^\s{4}def\s+\w+\(", source[match.end() :], re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start() : end]


def _latest(prefix: str) -> dict[str, Any]:
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


def _latest_profile_trace_rows() -> dict[str, Any]:
    latest_profile = _latest("design_guide_browser_live_smoothness_profile")
    scenarios = list((latest_profile.get("payload") or {}).get("scenarios") or [])
    rows: dict[str, Any] = {}
    for row in scenarios:
        counters = dict(row.get("counters") or {})
        trace = dict(counters.get("stable_render_reuse_trace") or {})
        if trace:
            rows[str(row.get("scenario_id") or "")] = trace
    return {
        "status": latest_profile.get("status"),
        "path": latest_profile.get("path"),
        "trace_rows": rows,
    }


def _capture() -> dict[str, Any]:
    inputs = _read(ROOT / "inputs_page.py")
    app = _read(ROOT / "app.py")
    profile = _read(ROOT / "tools" / "verification" / "design_guide_browser_live_smoothness_profile.py")
    helper = _function_block(inputs, "_record_inputs_stable_render_reuse_trace")
    summary = _nested_function_block(inputs, "_render_current_inputs_summary")
    design_guide = _nested_function_block(inputs, "_render_fresh_design_guide_panel")
    source_checks = {
        "helper_exists": bool(helper),
        "helper_trace_only": '"trace_only": True' in helper and '"render_skipped": False' in helper,
        "helper_records_no_product_change": '"product_behavior_changed": False' in helper,
        "helper_uses_stable_fingerprint": "stable_fingerprint_for_payload" in helper,
        "helper_has_guard_reasons": all(
            token in helper
            for token in [
                "debug_mode_enabled",
                "post_click_apply_in_flight",
                "pending_apply_refresh",
                "stale_or_changed_render_fingerprint_hash",
            ]
        ),
        "summary_trace_before_render_mark": (
            "_record_inputs_stable_render_reuse_trace(" in summary
            and summary.find("_record_inputs_stable_render_reuse_trace(")
            < summary.find('render_timing_mark("inputs_page.summary_render.start"')
        ),
        "design_guide_trace_before_render_mark": (
            "_record_inputs_stable_render_reuse_trace(" in design_guide
            and 'render_timing_mark(\n            "inputs_page.design_guide_build.start"' in design_guide
            and design_guide.find("_record_inputs_stable_render_reuse_trace(")
            < design_guide.find('render_timing_mark(\n            "inputs_page.design_guide_build.start"')
        ),
        "summary_trace_has_summary_surface": '"inputs_summary_panel"' in summary,
        "design_guide_trace_has_design_guide_surface": '"design_guide_panel"' in design_guide,
        "browser_probe_exposes_trace": "inputs_stable_render_reuse_trace" in app,
        "smoothness_profile_reads_trace": "stable_render_reuse_trace" in profile,
        "no_render_skip_branch_added": "render_skipped = True" not in inputs
        and "if row.get(\"reuse_eligible\")" not in inputs
        and "if trace.get(\"reuse_eligible\")" not in inputs,
    }
    return {
        "source_checks": source_checks,
        "latest_profile": _latest_profile_trace_rows(),
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    checks = dict(capture.get("source_checks") or {})
    required = [
        "helper_exists",
        "helper_trace_only",
        "helper_records_no_product_change",
        "helper_uses_stable_fingerprint",
        "helper_has_guard_reasons",
        "summary_trace_before_render_mark",
        "design_guide_trace_before_render_mark",
        "summary_trace_has_summary_surface",
        "design_guide_trace_has_design_guide_surface",
        "browser_probe_exposes_trace",
        "smoothness_profile_reads_trace",
        "no_render_skip_branch_added",
    ]
    missing = [key for key in required if not checks.get(key)]
    return {
        "status": "PASS" if not missing else "FAIL",
        "missing_checks": missing,
        "trace_only": not missing,
        "ready_for_live_trace_profile": not missing,
        "ready_for_render_bypass": False,
        "next_slice": (
            "Run browser/live smoothness and rerun-source profiles. If stable no-change reruns show "
            "TRACE_REUSE_ELIGIBLE while render still happens, create a readiness proof for the exact "
            "surface before implementing any guarded reuse."
            if not missing
            else "Fix missing trace-only wiring checks before live profiling."
        ),
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    return "\n".join(
        [
            "# Design Guide Stable Render Reuse Missed Trace Snapshot",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
            f"- Trace only: `{cls.get('trace_only')}`",
            f"- Ready for live trace profile: `{cls.get('ready_for_live_trace_profile')}`",
            f"- Ready for render bypass: `{cls.get('ready_for_render_bypass')}`",
            "",
            "## Source Checks",
            "",
            "```json",
            json.dumps(payload.get("source_checks") or {}, indent=2, sort_keys=True),
            "```",
            "",
            "## Latest Profile Trace Rows",
            "",
            "```json",
            json.dumps((payload.get("latest_profile") or {}).get("trace_rows") or {}, indent=2, sort_keys=True)[:12000],
            "```",
            "",
            "## Next Slice",
            "",
            str(cls.get("next_slice") or ""),
            "",
        ]
    )


def main() -> int:
    capture = _capture()
    classification = _classify(capture)
    stamp = _stamp()
    payload = {
        "schema": "design_guide_stable_render_reuse_missed_trace.v1",
        "timestamp": stamp,
        "status": classification["status"],
        "product_behaviour_changed": False,
        **capture,
        "classification": classification,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_guide_stable_render_reuse_missed_trace_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_stable_render_reuse_missed_trace_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_stable_render_reuse_missed_trace {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
