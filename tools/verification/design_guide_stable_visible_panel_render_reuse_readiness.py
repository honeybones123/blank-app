"""Readiness proof for stable visible-panel render-data reuse.

This verifier does not change product code. It proves that same-session
no-input reruns can use an authority/result based panel reuse key for the
summary and Design Guide panels, instead of transient pre-render session
fingerprints that drift after a stable manual rerun.
"""

from __future__ import annotations

import argparse
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

from tools.verification.design_guide_same_session_render_fingerprint_drift_audit import (  # noqa: E402
    DEFAULT_RECIPE,
    _capture,
    _latest,
    _parse_trace_payload,
    _surface_drift,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TRANSIENT_FIELDS = {
    "state_fingerprint_hash",
    "panel_baseline_fingerprint_hash",
    "design_guide_needs_refresh",
}

POST_RENDER_HYDRATION_FIELDS = {
    "final_publication_hash",
    "final_publication_display_hash",
    "final_publication_cta_hash",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _trace_rows(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(surface): dict(row)
        for surface, row in dict(summary.get("stable_render_reuse_trace") or {}).items()
        if isinstance(row, dict)
    }


def _stable_surface_payload(
    surface: str,
    summary: dict[str, Any],
    trace_payload: dict[str, Any],
) -> dict[str, Any]:
    if surface == "inputs_summary_panel":
        return {
            "surface": surface,
            "results_version": trace_payload.get("results_version"),
            "result_cache_hash": trace_payload.get("result_cache_hash"),
            "final_publication_hash": summary.get("final_publication_hash"),
            "final_publication_display_hash": summary.get("final_publication_display_hash"),
            "show_landing": trace_payload.get("show_landing"),
        }
    if surface == "design_guide_panel":
        return {
            "surface": surface,
            "results_version": trace_payload.get("results_version"),
            "final_publication_hash": summary.get("final_publication_hash"),
            "final_publication_display_hash": summary.get("final_publication_display_hash"),
            "final_publication_cta_hash": summary.get("final_publication_cta_hash"),
            "button_contract_hash": summary.get("button_contract_hash"),
            "apply_payload_hash": summary.get("apply_payload_hash"),
            "show_design_guide_for_current_inputs": trace_payload.get("show_design_guide_for_current_inputs"),
        }
    return {"surface": surface}


def _stable_surface_payloads(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = _trace_rows(summary)
    payloads = {}
    for surface, row in rows.items():
        trace_payload = _parse_trace_payload(row)
        payloads[surface] = _stable_surface_payload(surface, summary, trace_payload)
    return payloads


def _guard_decision(
    *,
    previous_hash: str | None,
    current_hash: str | None,
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
    if not current_hash:
        reasons.append("missing_current_reuse_hash")
    if not previous_hash:
        reasons.append("missing_previous_reuse_hash")
    if previous_hash and current_hash and previous_hash != current_hash:
        reasons.append("stale_or_changed_reuse_hash")
    return {
        "decision": "REUSE_READY" if not reasons else "REBUILD_REQUIRED",
        "reasons": reasons,
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    before = dict((capture.get("before") or {}).get("summary") or {})
    after = dict((capture.get("after") or {}).get("summary") or {})
    surface_drift = _surface_drift(before, after)
    before_payloads = _stable_surface_payloads(before)
    after_payloads = _stable_surface_payloads(after)
    surfaces = sorted(set(before_payloads) | set(after_payloads))
    proposed = {}
    for surface in surfaces:
        before_payload = before_payloads.get(surface) or {}
        after_payload = after_payloads.get(surface) or {}
        before_hash = _stable_hash(before_payload) if before_payload else None
        after_hash = _stable_hash(after_payload) if after_payload else None
        changed_trace_fields = sorted(
            ((surface_drift.get(surface) or {}).get("changed_fields") or {}).keys()
        )
        proposed[surface] = {
            "before_payload": before_payload,
            "after_payload": after_payload,
            "before_hash": before_hash,
            "after_hash": after_hash,
            "hash_stable": bool(before_hash and before_hash == after_hash),
            "changed_trace_fields": changed_trace_fields,
            "changed_trace_fields_are_transient_only": bool(
                changed_trace_fields and set(changed_trace_fields) <= TRANSIENT_FIELDS
            ),
            "changed_trace_fields_are_empty_or_transient_only": bool(
                not changed_trace_fields or set(changed_trace_fields) <= TRANSIENT_FIELDS
            ),
            "changed_trace_fields_are_empty_transient_or_post_render_hydration": bool(
                not changed_trace_fields
                or set(changed_trace_fields) <= (TRANSIENT_FIELDS | POST_RENDER_HYDRATION_FIELDS)
            ),
            "stable_case": _guard_decision(previous_hash=before_hash, current_hash=after_hash),
            "changed_hash_case": _guard_decision(previous_hash=before_hash, current_hash="changed"),
            "missing_current_case": _guard_decision(previous_hash=before_hash, current_hash=None),
            "missing_previous_case": _guard_decision(previous_hash=None, current_hash=after_hash),
            "debug_case": _guard_decision(previous_hash=before_hash, current_hash=after_hash, debug_mode=True),
            "apply_in_flight_case": _guard_decision(
                previous_hash=before_hash,
                current_hash=after_hash,
                apply_in_flight=True,
            ),
            "pending_apply_refresh_case": _guard_decision(
                previous_hash=before_hash,
                current_hash=after_hash,
                pending_apply_refresh=True,
            ),
        }
    ready_surfaces = [
        surface
        for surface, row in proposed.items()
        if row["hash_stable"]
        and row["changed_trace_fields_are_empty_transient_or_post_render_hydration"]
        and row["stable_case"]["decision"] == "REUSE_READY"
        and row["changed_hash_case"]["decision"] == "REBUILD_REQUIRED"
        and row["missing_current_case"]["decision"] == "REBUILD_REQUIRED"
        and row["missing_previous_case"]["decision"] == "REBUILD_REQUIRED"
        and row["debug_case"]["decision"] == "REBUILD_REQUIRED"
        and row["apply_in_flight_case"]["decision"] == "REBUILD_REQUIRED"
        and row["pending_apply_refresh_case"]["decision"] == "REBUILD_REQUIRED"
    ]
    required_surfaces = {"inputs_summary_panel", "design_guide_panel"}
    after_candidate_count = int((after.get("candidate_evaluation") or {}).get("count") or 0)
    after_card_rebuilds = int(after.get("card_render_model_rebuild_count") or 0)
    after_publication_rebuilds = int(after.get("publication_rebuild_count") or 0)
    stable_authority = all(
        before.get(key) == after.get(key)
        for key in (
            "final_publication_hash",
            "final_publication_display_hash",
            "final_publication_cta_hash",
            "button_contract_hash",
            "apply_payload_hash",
        )
        if before.get(key) or after.get(key)
    )
    status = "PASS" if required_surfaces <= set(ready_surfaces) and stable_authority else "PARTIAL"
    return {
        "status": status,
        "stable_authority_hashes": bool(stable_authority),
        "ready_surfaces": ready_surfaces,
        "missing_ready_surfaces": sorted(required_surfaces - set(ready_surfaces)),
        "candidate_evaluation_count_after": after_candidate_count,
        "card_render_model_rebuild_count_after": after_card_rebuilds,
        "publication_rebuild_count_after": after_publication_rebuilds,
        "proposed_surface_reuse": proposed,
        "ready_for_implementation": status == "PASS",
        "recommended_next_slice": (
            "Implement narrow non-debug stable render-data reuse for inputs_summary_panel and design_guide_panel."
            if status == "PASS"
            else "Do not implement render reuse until all required surfaces have stable authority/result reuse hashes."
        ),
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    return "\n".join(
        [
            "# Stable Visible Panel Render Reuse Readiness",
            "",
            f"Status: `{payload.get('status')}`",
            "",
            "## Executive Summary",
            "",
            f"- Stable authority hashes: `{cls.get('stable_authority_hashes')}`",
            f"- Ready surfaces: `{', '.join(cls.get('ready_surfaces') or [])}`",
            f"- Missing ready surfaces: `{', '.join(cls.get('missing_ready_surfaces') or [])}`",
            f"- Candidate eval count after: `{cls.get('candidate_evaluation_count_after')}`",
            f"- Card render-model rebuild count after: `{cls.get('card_render_model_rebuild_count_after')}`",
            f"- Publication rebuild count after: `{cls.get('publication_rebuild_count_after')}`",
            f"- Ready for implementation: `{cls.get('ready_for_implementation')}`",
            "",
            "## Proposed Surface Reuse",
            "",
            "```json",
            json.dumps(cls.get("proposed_surface_reuse") or {}, indent=2, sort_keys=True, default=str),
            "```",
            "",
            "## Recommendation",
            "",
            str(cls.get("recommended_next_slice") or ""),
            "",
        ]
    )


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_stable_visible_panel_render_reuse_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_stable_visible_panel_render_reuse_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8642)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_STABLE_PANEL_REUSE_URL"))
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
        payload = {
            "schema": "design_guide_stable_visible_panel_render_reuse_readiness.v1",
            "created_at": created_at,
            "status": classification["status"],
            "classification": classification,
            "capture": {
                "url": capture.get("url"),
                "recipe": capture.get("recipe"),
                "before": {
                    "summary": {
                        key: (capture.get("before") or {}).get("summary", {}).get(key)
                        for key in (
                            "final_publication_hash",
                            "final_publication_display_hash",
                            "final_publication_cta_hash",
                            "button_contract_hash",
                            "apply_payload_hash",
                        )
                    }
                },
                "after": {
                    "summary": {
                        key: (capture.get("after") or {}).get("summary", {}).get(key)
                        for key in (
                            "final_publication_hash",
                            "final_publication_display_hash",
                            "final_publication_cta_hash",
                            "button_contract_hash",
                            "apply_payload_hash",
                        )
                    }
                },
            },
            "latest": {
                "same_session_render_fingerprint_drift": _latest(
                    "design_guide_same_session_render_fingerprint_drift"
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
