"""Browser/live second same-session no-change rerun profile.

Measurement-only verifier. The first manual rerun can populate publication and
render fingerprints that were missing during the initial page load. This proof
clicks Streamlit's Rerun control twice in the same browser session and
classifies only the second no-change rerun as an implementation candidate.
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

from tools.verification.design_guide_same_session_no_change_rerun_profile import (  # noqa: E402
    DEFAULT_RECIPE,
    _capture as _single_capture,
    _click_streamlit_rerun,
    _latest,
    _query,
    _stable_hash,
    _summarise_state,
    _visible_probe,
    _wait_for_full_publication_state,
    _wait_for_rerun_seq_change,
    _wait_for_streamlit_idle,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)
from playwright.sync_api import sync_playwright  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _authority_tuple(summary: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(
        summary.get(key)
        for key in (
            "final_publication_hash",
            "final_publication_display_hash",
            "final_publication_cta_hash",
            "button_contract_hash",
            "apply_payload_hash",
        )
    )


def _capture(base_url: str, *, recipe: str, headed: bool, timeout_s: float) -> dict[str, Any]:
    url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_s * 1000))
        idle_initial = _wait_for_streamlit_idle(page, timeout_s=timeout_s)
        initial_state, initial_samples = _wait_for_full_publication_state(page, timeout_s=timeout_s)
        initial_summary = _summarise_state(initial_state)
        initial_visible = _visible_probe(page)

        first_click = _click_streamlit_rerun(page)
        first_state: dict[str, Any] = {}
        first_samples: list[dict[str, Any]] = []
        first_idle: dict[str, Any] = {}
        if first_click.get("clicked"):
            first_state, first_samples = _wait_for_rerun_seq_change(
                page,
                initial_summary.get("rerun_seq"),
                timeout_s=timeout_s,
            )
            first_idle = _wait_for_streamlit_idle(page, timeout_s=min(12.0, timeout_s))
        first_summary = _summarise_state(first_state) if first_state else {}
        first_visible = _visible_probe(page)

        second_click = _click_streamlit_rerun(page)
        second_state: dict[str, Any] = {}
        second_samples: list[dict[str, Any]] = []
        second_idle: dict[str, Any] = {}
        if second_click.get("clicked"):
            second_state, second_samples = _wait_for_rerun_seq_change(
                page,
                first_summary.get("rerun_seq"),
                timeout_s=timeout_s,
            )
            second_idle = _wait_for_streamlit_idle(page, timeout_s=min(12.0, timeout_s))
        second_summary = _summarise_state(second_state) if second_state else {}
        second_visible = _visible_probe(page)
        browser.close()

    return {
        "url": url,
        "recipe": recipe,
        "initial": {"state": initial_summary, "visible": initial_visible},
        "first": {"state": first_summary, "visible": first_visible},
        "second": {"state": second_summary, "visible": second_visible},
        "clicks": {"first": first_click, "second": second_click},
        "idle": {"initial": idle_initial, "first": first_idle, "second": second_idle},
        "poll_samples": {
            "initial": initial_samples,
            "first": first_samples,
            "second": second_samples,
        },
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    initial = dict((capture.get("initial") or {}).get("state") or {})
    first = dict((capture.get("first") or {}).get("state") or {})
    second = dict((capture.get("second") or {}).get("state") or {})
    clicks = dict(capture.get("clicks") or {})
    first_click = dict(clicks.get("first") or {})
    second_click = dict(clicks.get("second") or {})
    first_changed = initial.get("rerun_seq") is not None and first.get("rerun_seq") not in (
        None,
        initial.get("rerun_seq"),
    )
    second_changed = first.get("rerun_seq") is not None and second.get("rerun_seq") not in (
        None,
        first.get("rerun_seq"),
    )
    stable_second_authority = _authority_tuple(first) == _authority_tuple(second)
    eligible = list(second.get("stable_render_reuse_eligible_surfaces") or [])
    missing_previous = list(second.get("stable_render_missing_previous_surfaces") or [])
    candidate_count = int((second.get("candidate_evaluation") or {}).get("count") or 0)
    card_rebuilds = int(second.get("card_render_model_rebuild_count") or 0)
    publication_rebuilds = int(second.get("publication_rebuild_count") or 0)
    likely_sources: list[str] = []
    if not first_click.get("clicked"):
        likely_sources.append("first_rerun_control_not_clicked")
    if not second_click.get("clicked"):
        likely_sources.append("second_rerun_control_not_clicked")
    if second_changed and stable_second_authority and eligible:
        likely_sources.append("second_same_session_stable_render_reuse_eligible_but_rendered")
    if second_changed and stable_second_authority and candidate_count:
        likely_sources.append("second_same_session_candidate_evaluation_with_stable_authority")
    if second_changed and stable_second_authority and card_rebuilds:
        likely_sources.append("second_same_session_card_render_model_rebuild_with_stable_authority")
    if second_changed and stable_second_authority and publication_rebuilds:
        likely_sources.append("second_same_session_publication_rebuild_with_stable_authority")
    if missing_previous:
        likely_sources.append("second_same_session_missing_previous_render_fingerprint")
    if not likely_sources and second_changed:
        likely_sources.append("second_same_session_no_major_rebuild_source_detected")
    elif not likely_sources:
        likely_sources.append("second_same_session_rerun_not_proven")

    if "second_same_session_stable_render_reuse_eligible_but_rendered" in likely_sources:
        next_slice = "Implement or verify guarded reuse only for the second-rerun eligible surfaces."
    elif "second_same_session_no_major_rebuild_source_detected" in likely_sources:
        next_slice = "No same-session no-change render reuse implementation target remains; return to broad profile ranking."
    else:
        next_slice = "Resolve the listed same-session proof blocker before implementing render reuse."
    status = "PASS" if first_click.get("clicked") and second_click.get("clicked") and second_changed else "PARTIAL"
    return {
        "status": status,
        "first_clicked": bool(first_click.get("clicked")),
        "second_clicked": bool(second_click.get("clicked")),
        "first_rerun_seq_changed": bool(first_changed),
        "second_rerun_seq_changed": bool(second_changed),
        "stable_second_authority_hashes": bool(stable_second_authority),
        "second_eligible_surfaces": eligible,
        "second_missing_previous_surfaces": missing_previous,
        "candidate_evaluation_count_second": candidate_count,
        "card_render_model_rebuild_count_second": card_rebuilds,
        "publication_rebuild_count_second": publication_rebuilds,
        "likely_sources": likely_sources,
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    return "\n".join(
        [
            "# Design Guide Second Same-Session No-Change Rerun Profile",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
            f"- First rerun clicked: `{cls.get('first_clicked')}`",
            f"- Second rerun clicked: `{cls.get('second_clicked')}`",
            f"- Second rerun seq changed: `{cls.get('second_rerun_seq_changed')}`",
            f"- Stable second authority hashes: `{cls.get('stable_second_authority_hashes')}`",
            f"- Eligible surfaces after second rerun: `{', '.join(cls.get('second_eligible_surfaces') or [])}`",
            f"- Likely sources: `{', '.join(cls.get('likely_sources') or [])}`",
            "",
            "## Next Safe Slice",
            "",
            str(cls.get("recommended_next_slice") or ""),
            "",
            "## State Summary",
            "",
            "```json",
            json.dumps(
                {
                    "initial": (payload.get("capture") or {}).get("initial", {}).get("state"),
                    "first": (payload.get("capture") or {}).get("first", {}).get("state"),
                    "second": (payload.get("capture") or {}).get("second", {}).get("state"),
                    "clicks": (payload.get("capture") or {}).get("clicks"),
                },
                indent=2,
                sort_keys=True,
            )[:16000],
            "```",
            "",
        ]
    )


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_second_same_session_no_change_rerun_profile_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_second_same_session_no_change_rerun_profile_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8642)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_SECOND_SAME_SESSION_RERUN_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--timeout-s", type=float, default=75.0)
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
        try:
            capture = _capture(
                base_url,
                recipe=str(args.recipe),
                headed=bool(args.headed),
                timeout_s=float(args.timeout_s),
            )
            classification = _classify(capture)
        except Exception as exc:
            capture = {
                "url": _query(base_url, {"page": "inputs", "browser_recipe": str(args.recipe)}),
                "recipe": str(args.recipe),
                "capture_failed": True,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            classification = {
                "status": "PARTIAL",
                "first_clicked": False,
                "second_clicked": False,
                "first_rerun_seq_changed": False,
                "second_rerun_seq_changed": False,
                "stable_second_authority_hashes": False,
                "second_eligible_surfaces": [],
                "second_missing_previous_surfaces": [],
                "candidate_evaluation_count_second": 0,
                "card_render_model_rebuild_count_second": 0,
                "publication_rebuild_count_second": 0,
                "likely_sources": ["second_same_session_capture_failed"],
                "recommended_next_slice": "Fix the second same-session browser proof before implementing render reuse.",
            }
        payload: dict[str, Any] = {
            "schema": "design_guide_second_same_session_no_change_rerun_profile.v1",
            "created_at": created_at,
            "status": classification["status"],
            "classification": classification,
            "capture": capture,
            "latest": {
                "same_session_no_change_rerun_profile": _latest("design_guide_same_session_no_change_rerun_profile"),
                "stable_visible_panel_render_reuse_implementation": _latest(
                    "design_guide_stable_visible_panel_render_reuse_implementation"
                ),
                "stable_publication_summary_render_reuse_live_impact": _latest(
                    "design_guide_stable_publication_summary_render_reuse_live_impact"
                ),
                "independence_lock": _latest("design_guide_independence_lock"),
                "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
                "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
                "zero_authority_lock": _latest("design_brain_inputs_page_zero_authority_inventory_lock"),
            },
            "snapshot_hash": _stable_hash({"capture": capture, "classification": classification}),
            "product_behaviour_changed": False,
            "behaviour_scope": {
                "layout_changed": False,
                "rendering_changed": False,
                "publication_changed": False,
                "cta_apply_changed": False,
                "family_runtime_changed": False,
                "visible_wording_changed": False,
                "engineering_behaviour_changed": False,
            },
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
