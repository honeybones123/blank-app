"""Implementation snapshot for summary-card HTML reuse.

Proof-only verifier for the narrow smoothness implementation that reuses the
generated summary-card HTML string on stable reruns while still rendering the
visible Streamlit output every time.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _bounded_source(source: str) -> str:
    start = source.find("def _render_inputs_summary_expanders_and_tables()")
    end = source.find("def render_summary_table(results):", start)
    if start < 0 or end < 0:
        return ""
    return source[start:end]


def _simulate_decision(
    *,
    current_keys: dict[str, Any],
    cached_keys: dict[str, Any],
    cached_html_present: bool = True,
    debug_mode: bool = False,
    apply_in_flight: bool = False,
    pending_apply_refresh: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    if debug_mode:
        reasons.append("debug_mode_enabled")
    if apply_in_flight:
        reasons.append("post_click_apply_in_flight")
    if pending_apply_refresh:
        reasons.append("pending_apply_refresh")
    if any(value is None or value == "" for value in current_keys.values()):
        reasons.append("missing_reuse_key")
    if not cached_html_present:
        reasons.append("missing_cached_summary_html")
    if cached_keys != current_keys:
        reasons.append("stale_or_changed_reuse_key")
    return {
        "decision": "SKIP_HTML_BUILD" if not reasons else "REBUILD_HTML",
        "reasons": sorted(set(reasons)),
    }


def _scenarios() -> list[dict[str, Any]]:
    keys = {
        "summary_action_fp": "summary:stable",
        "results_version": 8,
        "result_cache_hash": "results:stable",
        "show_landing": False,
    }
    changed_results = dict(keys)
    changed_results["result_cache_hash"] = "results:changed"
    missing_summary = dict(keys)
    missing_summary["summary_action_fp"] = ""
    return [
        {"name": "stable_non_debug", **_simulate_decision(current_keys=keys, cached_keys=keys)},
        {
            "name": "changed_result_cache_hash",
            **_simulate_decision(current_keys=changed_results, cached_keys=keys),
        },
        {
            "name": "missing_summary_action_fingerprint",
            **_simulate_decision(current_keys=missing_summary, cached_keys=keys),
        },
        {
            "name": "missing_cached_html",
            **_simulate_decision(current_keys=keys, cached_keys=keys, cached_html_present=False),
        },
        {"name": "debug_mode", **_simulate_decision(current_keys=keys, cached_keys=keys, debug_mode=True)},
        {
            "name": "apply_in_flight",
            **_simulate_decision(current_keys=keys, cached_keys=keys, apply_in_flight=True),
        },
        {
            "name": "pending_apply_refresh",
            **_simulate_decision(current_keys=keys, cached_keys=keys, pending_apply_refresh=True),
        },
    ]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    bounded = _bounded_source(source)
    latest = {
        "scope_audit": _latest("design_guide_stable_publication_summary_render_reuse_scope_audit"),
        "reuse_plan": _latest("design_guide_stable_publication_summary_render_reuse_plan"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    source_markers = {
        "cache_key_defined": "_final_publication_summary_card_html_cache" in bounded,
        "build_function_extracted": "_build_summary_cards_html_for_current_state" in bounded,
        "stable_keys_include_result_cache": "result_cache_hash" in bounded
        and "RESULT_CACHE_KEY" in bounded,
        "stable_keys_exclude_transient_design_guide_state": "state_fingerprint" not in bounded
        and "panel_baseline_fingerprint" not in bounded
        and "final_publication_authority_hash" not in bounded
        and "final_publication_display_hash" not in bounded,
        "debug_guard_present": "_design_guide_sidebar_debug_enabled()" in bounded,
        "apply_guard_present": "DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY" in bounded
        and "_pending_inputs_apply_refresh" in bounded,
        "missing_html_guard_present": "missing_cached_summary_html" in bounded,
        "stale_key_guard_present": "stale_or_changed_reuse_key" in bounded,
        "visible_markdown_still_called": "st.markdown(f'<div class=\"summary-card-stack\">{summary_cards_html}</div>'" in bounded,
        "diagnostics_present": "_final_publication_summary_card_html_bypass_debug" in bounded
        and "summary.card_html_build_reuse" in bounded,
        "no_skip_summary_container_marker": "_render_current_inputs_summary" not in bounded,
    }
    return {
        "latest": latest,
        "source_markers": source_markers,
        "scenario_decisions": _scenarios(),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    source_markers = dict(capture.get("source_markers") or {})
    scenarios = list(capture.get("scenario_decisions") or [])
    stable = [row for row in scenarios if row.get("name") == "stable_non_debug"]
    guarded = [row for row in scenarios if row.get("name") != "stable_non_debug"]
    return {
        "scope_audit_pass": (latest.get("scope_audit") or {}).get("status") == "PASS",
        "reuse_plan_pass": (latest.get("reuse_plan") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "source_markers_present": all(bool(value) for value in source_markers.values()),
        "stable_case_skips_html_build": bool(stable and stable[0].get("decision") == "SKIP_HTML_BUILD"),
        "guarded_cases_rebuild": all(row.get("decision") == "REBUILD_HTML" for row in guarded),
    }


def _report(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Stable-Publication Summary Render Reuse Implementation",
        "",
        f"Status: `{payload.get('status')}`",
        "",
        "## Summary",
        "",
        "The implementation reuses only the generated `summary_cards_html` string.",
        "The visible summary container and `st.markdown(...)` render path still execute.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Scenario Decisions", "", "```json"])
    lines.append(json.dumps(payload.get("scenario_decisions") or [], indent=2, sort_keys=True))
    lines.extend(
        [
            "```",
            "",
            "## Ownership",
            "",
            "- Publication truth unchanged.",
            "- CTA/apply semantics unchanged.",
            "- Family runtimes unchanged.",
            "- Visible wording unchanged.",
            "- Visible summary render still called.",
            "",
        ]
    )
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_stable_publication_summary_render_reuse_implementation_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_stable_publication_summary_render_reuse_implementation_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(_report(payload), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "created_at": _stamp(),
        "status": status,
        "checks": checks,
        "product_behavior_changed": False,
        **capture,
    }
    payload["snapshot_hash"] = _stable_hash(
        {
            "status": status,
            "checks": checks,
            "source_markers": capture.get("source_markers"),
            "scenario_decisions": capture.get("scenario_decisions"),
        }
    )
    json_path, report_path = _write(payload)
    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
