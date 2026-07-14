"""Same-session render fingerprint drift audit for Inputs smoothness.

Proof-only browser/live verifier. It triggers Streamlit's visible Rerun control
without changing inputs and compares the stable-render trace payloads recorded
for visible panels. It identifies which fingerprint fields drift while the
FinalDesignGuidePublication/display/CTA/apply authority hashes remain stable.
"""

from __future__ import annotations

import argparse
import ast
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_same_session_rerun_trigger_ownership_audit import (  # noqa: E402
    _capture,
    _compact,
    _latest,
    _stable_authority,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_RECIPE = "A_bending_under_only"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _parse_trace_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Extract the raw fingerprint_payload from the trace-only string row."""
    raw = str(row.get("render_fingerprint_hash") or "")
    if not raw:
        return {}
    try:
        pairs = ast.literal_eval(raw)
    except Exception:
        return {}
    try:
        mapping = {str(key): value for key, value in pairs}
    except Exception:
        return {}
    payload_text = mapping.get("fingerprint_payload")
    if not isinstance(payload_text, str):
        return {}
    try:
        payload = json.loads(payload_text)
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _trace_rows(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {}
    for surface, row in dict(summary.get("stable_render_reuse_trace") or {}).items():
        if isinstance(row, dict):
            rows[str(surface)] = dict(row)
    return rows


def _payload_diff(before_payload: dict[str, Any], after_payload: dict[str, Any]) -> dict[str, Any]:
    keys = sorted(set(before_payload) | set(after_payload))
    changed = {}
    unchanged = {}
    missing_before = []
    missing_after = []
    for key in keys:
        before_value = before_payload.get(key)
        after_value = after_payload.get(key)
        if key not in before_payload:
            missing_before.append(key)
        if key not in after_payload:
            missing_after.append(key)
        if before_value != after_value:
            changed[key] = {"before": before_value, "after": after_value}
        else:
            unchanged[key] = before_value
    return {
        "changed": changed,
        "unchanged": unchanged,
        "missing_before": missing_before,
        "missing_after": missing_after,
    }


def _surface_drift(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_rows = _trace_rows(before)
    after_rows = _trace_rows(after)
    surfaces = sorted(set(before_rows) | set(after_rows))
    out = {}
    for surface in surfaces:
        before_row = dict(before_rows.get(surface) or {})
        after_row = dict(after_rows.get(surface) or {})
        before_payload = _parse_trace_payload(before_row)
        after_payload = _parse_trace_payload(after_row)
        diff = _payload_diff(before_payload, after_payload)
        out[surface] = {
            "before_decision": before_row.get("decision"),
            "after_decision": after_row.get("decision"),
            "before_reason": before_row.get("reason"),
            "after_reason": after_row.get("reason"),
            "before_reuse_eligible": bool(before_row.get("reuse_eligible")),
            "after_reuse_eligible": bool(after_row.get("reuse_eligible")),
            "before_payload": before_payload,
            "after_payload": after_payload,
            "changed_fields": diff["changed"],
            "unchanged_fields": diff["unchanged"],
            "missing_before": diff["missing_before"],
            "missing_after": diff["missing_after"],
        }
    return out


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    before = dict((capture.get("before") or {}).get("summary") or {})
    after = dict((capture.get("after") or {}).get("summary") or {})
    click = dict(capture.get("click") or {})
    stable_authority = _stable_authority(before, after)
    rerun_changed = before.get("rerun_seq") is not None and after.get("rerun_seq") not in (
        None,
        before.get("rerun_seq"),
    )
    surface_drift = _surface_drift(before, after)
    changed_by_surface = {
        surface: sorted(row.get("changed_fields") or {})
        for surface, row in surface_drift.items()
        if row.get("changed_fields")
    }
    all_changed = sorted({key for keys in changed_by_surface.values() for key in keys})
    authority_fields = {
        "final_publication_authority_hash",
        "final_publication_display_hash",
        "final_publication_cta_hash",
        "result_cache_hash",
        "results_version",
        "show_landing",
        "show_design_guide_for_current_inputs",
    }
    transient_fields = {
        "state_fingerprint_hash",
        "panel_baseline_fingerprint_hash",
        "design_guide_needs_refresh",
    }
    changed_authority_fields = sorted(set(all_changed) & authority_fields)
    changed_transient_fields = sorted(set(all_changed) & transient_fields)
    unclassified_changed_fields = sorted(set(all_changed) - authority_fields - transient_fields)
    candidate_count = int((after.get("candidate_evaluation") or {}).get("count") or 0)
    publication_rebuilds = int(after.get("publication_rebuild_count") or 0)
    card_rebuilds = int(after.get("card_render_model_rebuild_count") or 0)
    ready_for_render_reuse = bool(
        click.get("clicked")
        and rerun_changed
        and stable_authority
        and changed_transient_fields
        and not changed_authority_fields
        and not unclassified_changed_fields
        and candidate_count == 0
        and card_rebuilds == 0
    )
    likely_sources = []
    if not click.get("clicked"):
        likely_sources.append("streamlit_rerun_control_not_clicked")
    if not stable_authority:
        likely_sources.append("authority_hash_changed")
    if changed_authority_fields:
        likely_sources.append("authority_or_visible_output_fingerprint_field_changed")
    if unclassified_changed_fields:
        likely_sources.append("unclassified_render_fingerprint_field_changed")
    if changed_transient_fields:
        likely_sources.append("transient_pre_render_session_fingerprint_drift")
    if publication_rebuilds:
        likely_sources.append("publication_debug_stamp_rebuild_after_stable_manual_rerun")
    if candidate_count:
        likely_sources.append("candidate_evaluation_after_stable_manual_rerun")
    if card_rebuilds:
        likely_sources.append("card_render_model_rebuild_after_stable_manual_rerun")
    if ready_for_render_reuse:
        recommended = (
            "Create guarded stable-render reuse readiness for trace-required surfaces using authority/result "
            "hashes, while excluding transient pre-render state_fingerprint/panel_baseline/refresh flags."
        )
    elif "authority_or_visible_output_fingerprint_field_changed" in likely_sources:
        recommended = "Do not add render reuse; first prove why authority/visible-output fields changed."
    elif "unclassified_render_fingerprint_field_changed" in likely_sources:
        recommended = "Classify the unrecognised fingerprint fields before adding render reuse."
    else:
        recommended = "Continue publication debug-stamp readiness work before implementing render reuse."
    return {
        "status": "PASS" if click.get("clicked") and rerun_changed and stable_authority else "PARTIAL",
        "clicked_rerun": bool(click.get("clicked")),
        "rerun_seq_changed": bool(rerun_changed),
        "stable_authority_hashes": bool(stable_authority),
        "candidate_evaluation_count_after": candidate_count,
        "publication_rebuild_count_after": publication_rebuilds,
        "card_render_model_rebuild_count_after": card_rebuilds,
        "changed_fields_by_surface": changed_by_surface,
        "changed_authority_or_visible_fields": changed_authority_fields,
        "changed_transient_fields": changed_transient_fields,
        "unclassified_changed_fields": unclassified_changed_fields,
        "ready_for_render_reuse_readiness_slice": ready_for_render_reuse,
        "likely_sources": likely_sources,
        "recommended_next_slice": recommended,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Same-Session Render Fingerprint Drift Audit",
        "",
        f"Status: `{payload.get('status')}`",
        "",
        "## Executive Summary",
        "",
        f"- Stable authority hashes: `{cls.get('stable_authority_hashes')}`",
        f"- Candidate eval count after: `{cls.get('candidate_evaluation_count_after')}`",
        f"- Publication rebuild count after: `{cls.get('publication_rebuild_count_after')}`",
        f"- Card render-model rebuild count after: `{cls.get('card_render_model_rebuild_count_after')}`",
        f"- Changed transient fields: `{', '.join(cls.get('changed_transient_fields') or [])}`",
        f"- Changed authority/visible fields: `{', '.join(cls.get('changed_authority_or_visible_fields') or [])}`",
        f"- Unclassified changed fields: `{', '.join(cls.get('unclassified_changed_fields') or [])}`",
        f"- Ready for render-reuse readiness slice: `{cls.get('ready_for_render_reuse_readiness_slice')}`",
        "",
        "## Changed Fields By Surface",
        "",
        "```json",
        json.dumps(cls.get("changed_fields_by_surface") or {}, indent=2, sort_keys=True),
        "```",
        "",
        "## Recommendation",
        "",
        str(cls.get("recommended_next_slice") or ""),
    ]
    return "\n".join(lines) + "\n"


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_same_session_render_fingerprint_drift_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_same_session_render_fingerprint_drift_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8641)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_SAME_SESSION_RENDER_DRIFT_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--timeout-s", type=float, default=90.0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://localhost:{args.port}")
    created_at = _stamp()
    try:
        if not args.base_url:
            env_before = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            try:
                process = _start_streamlit(args.port)
            finally:
                os.environ.clear()
                os.environ.update(env_before)
            _wait_for_http(base_url, timeout_s=max(30.0, float(args.timeout_s)))
        capture = _capture(
            base_url,
            recipe=str(args.recipe),
            headed=bool(args.headed),
            timeout_s=float(args.timeout_s),
        )
        classification = _classify(capture)
        payload: dict[str, Any] = {
            "schema": "design_guide_same_session_render_fingerprint_drift_audit.v1",
            "created_at": created_at,
            "status": classification["status"],
            "classification": classification,
            "surface_drift": _surface_drift(
                dict((capture.get("before") or {}).get("summary") or {}),
                dict((capture.get("after") or {}).get("summary") or {}),
            ),
            "capture": _compact(capture, depth=5, max_items=35),
            "latest": {
                "same_session_rerun_trigger_ownership": _latest(
                    "design_guide_same_session_rerun_trigger_ownership"
                ),
                "same_session_no_change_rerun_profile": _latest(
                    "design_guide_same_session_no_change_rerun_profile"
                ),
                "same_session_publication_debug_stamp_hash_instability": _latest(
                    "design_guide_same_session_publication_debug_stamp_hash_instability"
                ),
                "independence_lock": _latest("design_guide_independence_lock"),
                "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
                "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
                "zero_authority_lock": _latest("design_brain_inputs_page_zero_authority_inventory_lock"),
            },
            "snapshot_hash": _stable_hash({"classification": classification}),
            "product_behaviour_changed": False,
        }
        json_path, md_path = _write(payload)
        print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
        return 0 if payload["status"] == "PASS" else 1
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
