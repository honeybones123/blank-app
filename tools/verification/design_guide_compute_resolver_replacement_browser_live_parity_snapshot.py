"""Browser/live parity for compute resolver replacement trace.

Proof-only. This verifier opens the live Inputs page, captures the browser
state probe, and proves the trace-wired controller compute resolver
replacement matches the still-product-driving page resolver output.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_helpers import (  # noqa: E402
    _browser_state_raw_candidates,
    _load_browser_state,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_RECIPE = "A_bending_under_only"
REQUIRED_ARTIFACTS = {
    "controller_replacement_trace": "design_guide_compute_resolver_controller_replacement_trace",
    "live_trace_static": "design_guide_live_compute_resolver_replacement_trace",
    "replacement_readiness": "design_guide_compute_stage_resolver_replacement_readiness",
    "final_item_selection_readiness": (
        "design_guide_controller_final_item_selection_independence_readiness"
    ),
    "design_guide_independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": (
        "design_guide_compute_resolver_publication_bridge_lock"
    ),
}


def _query(base_url: str, params: dict[str, Any]) -> str:
    return f"{str(base_url).rstrip('/')}/?{urlencode({k: v for k, v in params.items() if v is not None})}"


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None, "passed": False}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = payload.get("status") or payload.get("result") or payload.get("lock_status")
    status_text = str(status or "")
    return {
        "found": True,
        "path": str(path),
        "status": status,
        "passed": status_text == "PASS" or status_text.endswith("locked"),
        "payload": payload,
    }


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _pick_debug(state: dict[str, Any]) -> dict[str, Any]:
    debug: dict[str, Any] = {}
    for key in (
        "guidance_debug",
        "debug_trace",
        "design_guide_debug_bundle",
        "design_guide_debug",
        "guidance_compute_probe",
    ):
        value = state.get(key)
        if isinstance(value, dict):
            debug.update(value)
    design_guide_probe = _as_dict(state.get("design_guide_probe"))
    debug_bundle = _as_dict(design_guide_probe.get("debug_bundle"))
    if debug_bundle:
        debug.update(debug_bundle)
    render_plan_debug = _as_dict(design_guide_probe.get("render_plan_debug"))
    if render_plan_debug:
        debug.setdefault("render_plan_debug", dict(render_plan_debug))
    return debug


def _state_score(state: dict[str, Any]) -> int:
    debug = _pick_debug(state)
    trace = _as_dict(debug.get("design_guide_controller_compute_resolver_replacement_trace_only"))
    score = 0
    if trace:
        score += 100
    if trace.get("effective_selected_item_match") is True:
        score += 30
    if trace.get("selected_item_hash_match") is True:
        score += 20
    if trace.get("render_reason_match") is True:
        score += 20
    if trace.get("state_fingerprint_match") is True:
        score += 20
    if state.get("browser_shared_probe"):
        score += 10
    if state.get("summary_state_probe"):
        score += 10
    return score


def _diagnose_state(state: dict[str, Any], *, score: int) -> dict[str, Any]:
    debug = _pick_debug(state)
    design_guide_probe = _as_dict(state.get("design_guide_probe"))
    return {
        "score": score,
        "top_keys": sorted(str(key) for key in state.keys())[:80],
        "debug_trace_keys": sorted(
            str(key)
            for key in debug.keys()
            if "compute_resolver_replacement" in str(key)
            or "controller_compute" in str(key)
            or "final_publication" in str(key)
        )[:120],
        "trace_present": bool(
            _as_dict(debug.get("design_guide_controller_compute_resolver_replacement_trace_only"))
        ),
        "cache_enrich_error": debug.get(
            "design_guide_controller_compute_resolver_replacement_trace_only_cache_enrich_error"
        ),
        "cache_enrich_skipped": debug.get(
            "design_guide_controller_compute_resolver_replacement_trace_only_cache_enrich_skipped"
        ),
        "cache_enriched": debug.get(
            "design_guide_controller_compute_resolver_replacement_trace_only_cache_enriched"
        ),
        "cache_enrich_source": debug.get(
            "design_guide_controller_compute_resolver_replacement_trace_only_cache_enrich_source"
        ),
        "primary_card_title": design_guide_probe.get("primary_card_title")
        or debug.get("primary_title"),
        "browser_probe_phase": state.get("browser_probe_phase"),
        "page_slug": state.get("page_slug"),
    }


def _load_best_browser_state(
    page, *, timeout_s: float
) -> tuple[dict[str, Any], str | None, list[dict[str, Any]]]:
    deadline = time.time() + max(0.1, float(timeout_s or 1.0))
    best: dict[str, Any] = {}
    best_score = -1
    last_error: str | None = None
    diagnostics: list[dict[str, Any]] = []
    while time.time() < deadline:
        try:
            remaining_ms = max(100, min(2_000, int((deadline - time.time()) * 1000)))
            candidates: list[dict[str, Any]] = []
            for raw in _browser_state_raw_candidates(page, timeout_ms=remaining_ms):
                try:
                    parsed = json.loads(raw)
                except Exception:
                    continue
                if isinstance(parsed, dict):
                    candidates.append(parsed)
            if not candidates:
                fallback = _load_browser_state(
                    page, timeout_s=min(1.0, max(0.1, deadline - time.time()))
                )
                if isinstance(fallback, dict):
                    candidates.append(fallback)
            for candidate in candidates:
                score = _state_score(candidate)
                diagnostics.append(_diagnose_state(candidate, score=score))
                if score > best_score:
                    best = candidate
                    best_score = score
            if best and _state_score(best) >= 150:
                return best, None, diagnostics[-10:]
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(0.3)
    return best, last_error, diagnostics[-10:]


def _visible_dom_snapshot(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            () => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const bodyText = clean(document.body ? document.body.innerText : "");
              const visible = (el) => {
                if (!el || !el.getBoundingClientRect) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none"
                  && style.visibility !== "hidden"
                  && Number(style.opacity || "1") > 0.02
                  && rect.width > 2
                  && rect.height > 2;
              };
              const cards = Array.from(document.querySelectorAll(
                "[data-testid='design-guide-card'], .fast-guidance-item, [data-testid*='design-guide' i], section, div"
              )).filter(visible).map((el) => clean(el.innerText || el.textContent))
                .filter((text) => /Design is|Strengthening required|Design Guide blocker|Repair required|Why action is required|Preview after proposed change/i.test(text))
                .filter((text) => text.length < 4500)
                .slice(0, 5);
              return {
                url: window.location.href,
                design_guide_card_visible: cards.length > 0,
                design_guide_card_text: cards[0] || "",
                loading_shell_visible: /Design Guide\s+Checking design guidance/i.test(bodyText),
                body_has_design_guide: /Design Guide/i.test(bodyText),
              };
            }
            """
        )
    )


def _capture_live_trace(page, *, timeout_s: float) -> dict[str, Any]:
    deadline = time.time() + max(1.0, float(timeout_s or 1.0))
    last_state: dict[str, Any] = {}
    last_dom: dict[str, Any] = {}
    last_error: str | None = None
    last_diagnostics: list[dict[str, Any]] = []
    while time.time() < deadline:
        try:
            last_dom = _visible_dom_snapshot(page)
        except Exception as exc:
            last_dom = {"dom_error": f"{type(exc).__name__}: {exc}"}
        last_state, last_error, last_diagnostics = _load_best_browser_state(page, timeout_s=2.0)
        debug = _pick_debug(last_state)
        trace = _as_dict(debug.get("design_guide_controller_compute_resolver_replacement_trace_only"))
        if trace and not last_dom.get("loading_shell_visible"):
            return {
                "captured": True,
                "state": last_state,
                "debug": debug,
                "trace": trace,
                "dom": last_dom,
                "browser_state_error": None,
                "state_diagnostics": last_diagnostics,
            }
        time.sleep(0.5)
    return {
        "captured": False,
        "state": last_state,
        "debug": _pick_debug(last_state),
        "trace": _as_dict(
            _pick_debug(last_state).get(
                "design_guide_controller_compute_resolver_replacement_trace_only"
            )
        ),
        "dom": last_dom,
        "browser_state_error": last_error,
        "state_diagnostics": last_diagnostics,
    }


def _summarise_capture(capture: dict[str, Any]) -> dict[str, Any]:
    debug = _as_dict(capture.get("debug"))
    trace = _as_dict(capture.get("trace"))
    payload = _as_dict(debug.get("design_guide_controller_compute_resolver_replacement_trace_only_payload"))
    handoff = _as_dict(payload.get("handoff"))
    decision_proof = _as_dict(handoff.get("compute_handoff_rebound_decision_proof"))
    return {
        "captured": bool(capture.get("captured")),
        "browser_state_available": bool(capture.get("state")),
        "browser_state_error": capture.get("browser_state_error"),
        "visible_card": bool(_as_dict(capture.get("dom")).get("design_guide_card_visible")),
        "loading_shell_visible": bool(_as_dict(capture.get("dom")).get("loading_shell_visible")),
        "trace_hash": trace.get("trace_hash"),
        "request_hash": trace.get("request_hash"),
        "controller_hash": trace.get("controller_hash"),
        "final_compute_resolution_hash": trace.get("final_compute_resolution_hash"),
        "legacy_final_compute_resolution_hash": trace.get("legacy_final_compute_resolution_hash"),
        "controller_selected_item_hash": trace.get("controller_selected_item_hash"),
        "legacy_selected_item_hash": trace.get("legacy_selected_item_hash"),
        "selected_item_hash_match": trace.get("selected_item_hash_match"),
        "effective_selected_item_match": trace.get("effective_selected_item_match"),
        "visible_semantics_match": trace.get("visible_semantics_match"),
        "cta_semantics_match": trace.get("cta_semantics_match"),
        "blocker_semantics_match": trace.get("blocker_semantics_match"),
        "controller_visible_semantics_hash": trace.get("controller_visible_semantics_hash"),
        "legacy_visible_semantics_hash": trace.get("legacy_visible_semantics_hash"),
        "controller_cta_semantics_hash": trace.get("controller_cta_semantics_hash"),
        "legacy_cta_semantics_hash": trace.get("legacy_cta_semantics_hash"),
        "controller_blocker_semantics_hash": trace.get("controller_blocker_semantics_hash"),
        "legacy_blocker_semantics_hash": trace.get("legacy_blocker_semantics_hash"),
        "effective_selected_item_semantics": _as_dict(
            trace.get("effective_selected_item_semantics")
        ),
        "selected_item_diff_key_count": trace.get("selected_item_diff_key_count"),
        "selected_item_diff_keys": list(trace.get("selected_item_diff_keys") or []),
        "selected_item_diff_values": _as_dict(trace.get("selected_item_diff_values")),
        "controller_selected_item_summary": _as_dict(
            trace.get("controller_selected_item_summary")
        ),
        "legacy_selected_item_summary": _as_dict(trace.get("legacy_selected_item_summary")),
        "controller_render_reason": trace.get("controller_render_reason"),
        "legacy_render_reason": trace.get("legacy_render_reason"),
        "render_reason_match": trace.get("render_reason_match"),
        "controller_state_fingerprint": trace.get("controller_state_fingerprint"),
        "legacy_state_fingerprint": trace.get("legacy_state_fingerprint"),
        "state_fingerprint_match": trace.get("state_fingerprint_match"),
        "compute_handoff_rebound_decision_hash": trace.get(
            "compute_handoff_rebound_decision_hash"
        ),
        "old_resolver_input_required": trace.get("old_resolver_input_required"),
        "pre_resolver_request_built": trace.get("pre_resolver_request_built"),
        "pre_resolver_trace_hash": trace.get("pre_resolver_trace_hash"),
        "old_resolver_output_consumed_for_request": trace.get(
            "old_resolver_output_consumed_for_request"
        ),
        "trace_only": trace.get("trace_only"),
        "product_driving": trace.get("product_driving"),
        "render_driving": trace.get("render_driving"),
        "apply_driving": trace.get("apply_driving"),
        "session_driving": trace.get("session_driving"),
        "live_wired": debug.get(
            "design_guide_controller_compute_resolver_replacement_trace_only_live_wired"
        ),
        "controller_cutover_used": debug.get(
            "design_guide_compute_resolver_controller_cutover_used"
        ),
        "controller_cutover_fallback_used": debug.get(
            "design_guide_compute_resolver_controller_cutover_fallback_used"
        ),
        "controller_cutover_authority": debug.get(
            "design_guide_compute_resolver_controller_cutover_authority"
        ),
        "controller_cutover_hash": debug.get(
            "design_guide_compute_resolver_controller_cutover_hash"
        ),
        "debug_flags": {
            "product_driving": debug.get(
                "design_guide_controller_compute_resolver_replacement_trace_only_product_driving"
            ),
            "render_driving": debug.get(
                "design_guide_controller_compute_resolver_replacement_trace_only_render_driving"
            ),
            "apply_driving": debug.get(
                "design_guide_controller_compute_resolver_replacement_trace_only_apply_driving"
            ),
            "session_driving": debug.get(
                "design_guide_controller_compute_resolver_replacement_trace_only_session_driving"
            ),
        },
        "missing_blocking_fields": list(decision_proof.get("missing_blocking_fields") or []),
        "field_hash_count": len(dict(decision_proof.get("field_hashes") or {})),
        "state_diagnostics": capture.get("state_diagnostics") or [],
    }


def _write_report(payload: dict[str, Any], md_path: Path) -> None:
    live = dict(payload.get("live_trace") or {})
    lines = [
        "# Design Guide Compute Resolver Replacement Browser Live Parity Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Target URL: `{payload['target_url']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Live Trace",
        "",
        f"- Captured: `{live.get('captured')}`",
        f"- Visible card: `{live.get('visible_card')}`",
        f"- Loading shell visible: `{live.get('loading_shell_visible')}`",
        f"- Selected item hash match: `{live.get('selected_item_hash_match')}`",
        f"- Effective selected item match: `{live.get('effective_selected_item_match')}`",
        f"- Visible semantics match: `{live.get('visible_semantics_match')}`",
        f"- CTA semantics match: `{live.get('cta_semantics_match')}`",
        f"- Blocker semantics match: `{live.get('blocker_semantics_match')}`",
        f"- Selected item diff key count: `{live.get('selected_item_diff_key_count')}`",
        f"- Selected item diff keys: `{live.get('selected_item_diff_keys')}`",
        f"- Render reason match: `{live.get('render_reason_match')}`",
        f"- State fingerprint match: `{live.get('state_fingerprint_match')}`",
        f"- Old resolver input required: `{live.get('old_resolver_input_required')}`",
        f"- Pre-resolver request built: `{live.get('pre_resolver_request_built')}`",
        f"- Old resolver output consumed for request: `{live.get('old_resolver_output_consumed_for_request')}`",
        f"- Controller cutover used: `{live.get('controller_cutover_used')}`",
        f"- Controller cutover fallback used: `{live.get('controller_cutover_fallback_used')}`",
        f"- Missing blocking fields: `{live.get('missing_blocking_fields')}`",
        f"- Field hash count: `{live.get('field_hash_count')}`",
        f"- Trace flags: `{live.get('debug_flags')}`",
        "",
        "## Required Artifacts",
        "",
        "| Gate | Found | Status | Path |",
        "| --- | --- | --- | --- |",
    ]
    for name, artifact in (payload.get("required_artifacts") or {}).items():
        lines.append(
            f"| {name} | {artifact.get('found')} | {artifact.get('status')} | `{artifact.get('path')}` |"
        )
    if payload.get("failures"):
        lines.extend(["", "## Failures", "", "```json", json.dumps(payload["failures"], indent=2), "```"])
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            (
                "If this browser/live parity remains green across broader recipes, the next "
                "slice can introduce a cutover-readiness verifier for replacing the compute "
                "resolver assignment with the controller adapter. Do not delete compute "
                "helpers before that cutover and deadness proof."
            ),
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8587)
    parser.add_argument("--base-url", default=os.environ.get("DG_COMPUTE_RESOLVER_LIVE_BASE_URL"))
    parser.add_argument("--url", default=os.environ.get("DG_COMPUTE_RESOLVER_LIVE_URL"))
    parser.add_argument("--recipe", default=os.environ.get("DG_COMPUTE_RESOLVER_LIVE_RECIPE") or DEFAULT_RECIPE)
    parser.add_argument("--timeout-s", type=float, default=75.0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    compile_run = _run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "design_brain/design_guide_controller.py",
            "inputs_page.py",
            "tools/verification/design_guide_compute_resolver_replacement_browser_live_parity_snapshot.py",
        ]
    )
    process: subprocess.Popen | None = None
    errors: list[str] = []
    target_url = args.url
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    live_capture: dict[str, Any] = {}
    try:
        if args.url:
            _wait_for_http(args.url)
        elif args.base_url:
            _wait_for_http(base_url)
            target_url = _query(base_url, {"page": "inputs", "browser_recipe": args.recipe})
        else:
            env_before = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            os.environ["PERF_TRACE_INPUTS"] = "1"
            try:
                process = _start_streamlit(args.port)
            finally:
                os.environ.clear()
                os.environ.update(env_before)
            target_url = _query(base_url, {"page": "inputs", "browser_recipe": args.recipe})

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            context = browser.new_context(viewport={"width": 1800, "height": 1000})
            page = context.new_page()
            page.set_default_timeout(30_000)
            page.goto(str(target_url), wait_until="domcontentloaded", timeout=90_000)
            live_capture = _capture_live_trace(page, timeout_s=args.timeout_s)
            context.close()
            browser.close()
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    live_trace = _summarise_capture(live_capture)
    required_artifacts = {name: _latest(prefix) for name, prefix in REQUIRED_ARTIFACTS.items()}
    failures: list[str] = []
    if compile_run["returncode"] != 0:
        failures.append("py_compile_failed")
    if errors:
        failures.extend(f"browser_error::{error}" for error in errors)
    if not live_trace.get("captured"):
        failures.append("compute_resolver_replacement_trace_not_captured")
    if not live_trace.get("browser_state_available"):
        failures.append("browser_state_unavailable")
    if not live_trace.get("visible_card"):
        failures.append("visible_design_guide_card_not_confirmed")
    if live_trace.get("loading_shell_visible"):
        failures.append("loading_shell_still_visible")
    if live_trace.get("effective_selected_item_match") is not True:
        failures.append("effective_selected_item_mismatch")
    if live_trace.get("visible_semantics_match") is not True:
        failures.append("visible_semantics_mismatch")
    if live_trace.get("cta_semantics_match") is not True:
        failures.append("cta_semantics_mismatch")
    if live_trace.get("blocker_semantics_match") is not True:
        failures.append("blocker_semantics_mismatch")
    if live_trace.get("render_reason_match") is not True:
        failures.append("render_reason_mismatch")
    if live_trace.get("state_fingerprint_match") is not True:
        failures.append("state_fingerprint_mismatch")
    if live_trace.get("old_resolver_input_required") is not False:
        failures.append("old_resolver_input_required")
    if live_trace.get("pre_resolver_request_built") is not True:
        failures.append("pre_resolver_request_not_built")
    if not live_trace.get("pre_resolver_trace_hash"):
        failures.append("pre_resolver_trace_hash_missing")
    if live_trace.get("old_resolver_output_consumed_for_request") is not False:
        failures.append("old_resolver_output_consumed_for_request")
    if live_trace.get("controller_cutover_used") is not True:
        failures.append("controller_cutover_not_used")
    if live_trace.get("controller_cutover_fallback_used") is not False:
        failures.append("controller_cutover_fallback_used")
    if live_trace.get("trace_only") is not True:
        failures.append("trace_not_trace_only")
    for field in ("product_driving", "render_driving", "apply_driving", "session_driving"):
        if live_trace.get(field) is not False:
            failures.append(f"trace_{field}_not_false")
    for flag, value in (live_trace.get("debug_flags") or {}).items():
        if value is not False:
            failures.append(f"debug_flag_{flag}_not_false")
    if live_trace.get("missing_blocking_fields"):
        failures.append("compute_handoff_missing_blocking_fields")
    if live_trace.get("field_hash_count") not in (0, 9):
        failures.append("unexpected_compute_handoff_field_hash_count")
    if not all(artifact.get("passed") for artifact in required_artifacts.values()):
        failures.append("required_trace_or_lock_artifact_not_green")

    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_compute_resolver_replacement_browser_live_parity_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "target_url": target_url,
        "recipe": args.recipe,
        "product_behaviour_changed": False,
        "family_runtimes_changed": False,
        "contracts_changed": False,
        "cta_rendering_changed": False,
        "publication_semantics_changed": False,
        "apply_routing_changed": False,
        "visible_wording_changed": False,
        "compile_run": compile_run,
        "live_trace": live_trace,
        "required_artifacts": required_artifacts,
        "errors": errors,
        "failures": failures,
    }
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_compute_resolver_replacement_browser_live_parity_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_compute_resolver_replacement_browser_live_parity_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, md_path)
    print(f"design_guide_compute_resolver_replacement_browser_live_parity {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + json.dumps(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
