"""Browser/live DesignGuideController trace parity snapshot.

Proof-only. This verifier checks that the live Inputs page exposes a
DesignGuideController trace-only payload in the browser-state probe and that
the controller publication hash matches the already-published
FinalDesignGuidePublication hash.

It does not change product behaviour, family runtimes, CTA rendering,
publication semantics, Apply routing, session ownership, or visible wording.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
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
    "controller_trace_only_parity": "design_guide_controller_trace_only_parity",
    "controller_live_trace_wiring": "design_guide_controller_live_trace_wiring",
    "controller_publication_authority_cutover": (
        "design_guide_controller_publication_authority_cutover"
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
    return {
        "found": True,
        "path": str(path),
        "status": status,
        "passed": status == "PASS" or str(status or "").endswith("locked"),
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
    probe_debug_bundle = _as_dict(design_guide_probe.get("debug_bundle"))
    if probe_debug_bundle:
        debug.update(probe_debug_bundle)
    render_plan_debug = _as_dict(design_guide_probe.get("render_plan_debug"))
    if render_plan_debug:
        debug.setdefault("render_plan_debug", dict(render_plan_debug))
    return debug


def _state_score(state: dict[str, Any]) -> int:
    debug = _pick_debug(state)
    trace = _as_dict(debug.get("design_guide_controller_trace_only_parity"))
    verifier = _as_dict(debug.get("final_publication_verifier_payload"))
    score = 0
    if trace:
        score += 100
    if trace.get("parity_pass") is True:
        score += 50
    if verifier.get("publication_hash") or _publication_hash_from_debug(debug):
        score += 30
    if state.get("browser_shared_probe"):
        score += 10
    if state.get("summary_state_probe"):
        score += 10
    return score


def _diagnose_state(state: dict[str, Any], *, score: int) -> dict[str, Any]:
    debug = _pick_debug(state)
    design_guide_probe = _as_dict(state.get("design_guide_probe"))
    debug_bundle = _as_dict(design_guide_probe.get("debug_bundle"))
    return {
        "score": score,
        "top_keys": sorted(str(key) for key in state.keys())[:80],
        "design_guide_probe_keys": sorted(str(key) for key in design_guide_probe.keys())[:80],
        "debug_bundle_controller_keys": sorted(
            str(key)
            for key in debug_bundle.keys()
            if "controller" in str(key) or "final_visible_resolution" in str(key)
        )[:80],
        "merged_debug_controller_keys": sorted(
            str(key)
            for key in debug.keys()
            if "controller" in str(key) or "final_visible_resolution" in str(key)
        )[:80],
        "publication_hash_present": bool(_publication_hash_from_debug(debug)),
        "trace_present": bool(_as_dict(debug.get("design_guide_controller_trace_only_parity"))),
        "primary_card_title": design_guide_probe.get("primary_card_title")
        or debug_bundle.get("primary_card_title")
        or debug.get("primary_title"),
        "render_eligibility_trace": _as_dict(debug.get("design_guide_render_eligibility_trace")),
        "browser_probe_phase": state.get("browser_probe_phase"),
        "page_slug": state.get("page_slug"),
    }


def _load_best_browser_state(page, *, timeout_s: float) -> tuple[dict[str, Any], str | None, list[dict[str, Any]]]:
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
                fallback = _load_browser_state(page, timeout_s=min(1.0, max(0.1, deadline - time.time())))
                if isinstance(fallback, dict):
                    candidates.append(fallback)
            for candidate in candidates:
                score = _state_score(candidate)
                diagnostics.append(_diagnose_state(candidate, score=score))
                if score > best_score:
                    best = candidate
                    best_score = score
            if best and _state_score(best) >= 100:
                return best, None, diagnostics[-10:]
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(0.3)
    return best, last_error, diagnostics[-10:]


def _publication_hash_from_debug(debug: dict[str, Any]) -> str:
    verifier = _as_dict(debug.get("final_publication_verifier_payload"))
    return str(
        debug.get("final_visible_resolution_authority_hash")
        or debug.get("final_visible_resolution_publication_hash")
        or verifier.get("publication_hash")
        or debug.get("final_publication_publication_hash")
        or debug.get("publication_hash")
        or debug.get("final_publication_authority_hash")
        or ""
    ).strip()


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
        trace = _as_dict(debug.get("design_guide_controller_trace_only_parity"))
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
        "trace": _as_dict(_pick_debug(last_state).get("design_guide_controller_trace_only_parity")),
        "dom": last_dom,
        "browser_state_error": last_error,
        "state_diagnostics": last_diagnostics,
    }


def _summarise_capture(capture: dict[str, Any]) -> dict[str, Any]:
    debug = _as_dict(capture.get("debug"))
    trace = _as_dict(capture.get("trace"))
    live_hash = str(_publication_hash_from_debug(debug) or trace.get("live_publication_hash") or "").strip()
    controller_hash = str(trace.get("controller_publication_hash") or "").strip()
    return {
        "captured": bool(capture.get("captured")),
        "browser_state_available": bool(capture.get("state")),
        "browser_state_error": capture.get("browser_state_error"),
        "visible_card": bool(_as_dict(capture.get("dom")).get("design_guide_card_visible")),
        "loading_shell_visible": bool(_as_dict(capture.get("dom")).get("loading_shell_visible")),
        "live_publication_hash": live_hash,
        "trace_reported_live_publication_hash": str(trace.get("live_publication_hash") or "").strip(),
        "legacy_verifier_publication_hash": str(
            _as_dict(debug.get("final_publication_verifier_payload")).get("publication_hash")
            or ""
        ).strip(),
        "controller_publication_hash": controller_hash,
        "controller_collapsed_publication_hash": trace.get("controller_collapsed_publication_hash"),
        "controller_resolution_publication_hash": trace.get("controller_resolution_publication_hash"),
        "trace_hash": trace.get("trace_hash"),
        "parity_pass": bool(trace.get("parity_pass")),
        "selected_family": trace.get("selected_family"),
        "outcome_state": trace.get("outcome_state"),
        "published_item_id": trace.get("published_item_id"),
        "trace_input_title": trace.get("trace_input_title"),
        "trace_input_status": trace.get("trace_input_status"),
        "trace_input_family": trace.get("trace_input_family"),
        "controller_display_title": trace.get("controller_display_title"),
        "controller_display_status": trace.get("controller_display_status"),
        "live_verifier_publication_hash": trace.get("live_verifier_publication_hash"),
        "live_verifier_cta_hash": trace.get("live_verifier_cta_hash"),
        "live_verifier_display_hash": trace.get("live_verifier_display_hash"),
        "live_verifier_evidence_hash": trace.get("live_verifier_evidence_hash"),
        "controller_cta_hash": trace.get("controller_cta_hash"),
        "controller_display_hash": trace.get("controller_display_hash"),
        "controller_evidence_hash": trace.get("controller_evidence_hash"),
        "trace_debug_keys_hash": trace.get("trace_debug_keys_hash"),
        "trace_debug_keys_count": trace.get("trace_debug_keys_count"),
        "trace_input_item_hash": trace.get("trace_input_item_hash"),
        "trace_final_visible_resolution_item_hash": trace.get(
            "trace_final_visible_resolution_item_hash"
        ),
        "trace_only": trace.get("trace_only"),
        "product_driving": trace.get("product_driving"),
        "render_driving": trace.get("render_driving"),
        "apply_driving": trace.get("apply_driving"),
        "session_driving": trace.get("session_driving"),
        "hashes_match": bool(live_hash and live_hash == controller_hash),
        "collapsed_hash_matches": bool(
            live_hash and live_hash == str(trace.get("controller_collapsed_publication_hash") or "")
        ),
        "resolution_hash_matches": bool(
            live_hash and live_hash == str(trace.get("controller_resolution_publication_hash") or "")
        ),
        "final_publication_verifier_payload_present": bool(
            _as_dict(debug.get("final_publication_verifier_payload")).get("publication_hash")
        ),
        "controller_trace_debug_flags": {
            "live_wired": debug.get("design_guide_controller_trace_only_live_wired"),
            "product_driving": debug.get("design_guide_controller_trace_only_product_driving"),
            "render_driving": debug.get("design_guide_controller_trace_only_render_driving"),
            "apply_driving": debug.get("design_guide_controller_trace_only_apply_driving"),
            "session_driving": debug.get("design_guide_controller_trace_only_session_driving"),
        },
        "state_diagnostics": capture.get("state_diagnostics") or [],
    }


def _write_report(payload: dict[str, Any], md_path: Path) -> None:
    live = dict(payload.get("live_trace") or {})
    lines = [
        "# DesignGuideController Browser Live Trace Parity Snapshot",
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
        f"- Selected family: `{live.get('selected_family')}`",
        f"- Outcome state: `{live.get('outcome_state')}`",
        f"- Live publication hash: `{live.get('live_publication_hash')}`",
        f"- Controller publication hash: `{live.get('controller_publication_hash')}`",
        f"- Hashes match: `{live.get('hashes_match')}`",
        f"- Collapsed item hash matches: `{live.get('collapsed_hash_matches')}`",
        f"- Resolution hash matches: `{live.get('resolution_hash_matches')}`",
        f"- Parity pass: `{live.get('parity_pass')}`",
        f"- Trace flags: `{live.get('controller_trace_debug_flags')}`",
        "",
        "## Composed Gates",
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
                "With browser/live controller trace parity proven, continue moving "
                "remaining compatibility proof surfaces behind `DesignGuideController` "
                "or profile the next measured smoothness hotspot."
            ),
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8537)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_CONTROLLER_LIVE_BASE_URL"))
    parser.add_argument("--url", default=os.environ.get("DESIGN_GUIDE_CONTROLLER_LIVE_URL"))
    parser.add_argument("--recipe", default=os.environ.get("DESIGN_GUIDE_CONTROLLER_LIVE_RECIPE") or DEFAULT_RECIPE)
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
            "tools/verification/design_guide_controller_browser_live_trace_parity_snapshot.py",
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
        failures.append("controller_live_trace_not_captured")
    if not live_trace.get("browser_state_available"):
        failures.append("browser_state_unavailable")
    if not live_trace.get("visible_card"):
        failures.append("visible_design_guide_card_not_confirmed")
    if live_trace.get("loading_shell_visible"):
        failures.append("loading_shell_still_visible")
    if not live_trace.get("parity_pass"):
        failures.append("controller_trace_parity_failed")
    if not live_trace.get("hashes_match"):
        failures.append("controller_publication_hash_mismatch")
    if not live_trace.get("collapsed_hash_matches"):
        failures.append("controller_collapsed_item_hash_mismatch")
    if not live_trace.get("resolution_hash_matches"):
        failures.append("controller_resolution_hash_mismatch")
    if live_trace.get("trace_only") is not True:
        failures.append("controller_trace_not_trace_only")
    for field in ("product_driving", "render_driving", "apply_driving", "session_driving"):
        if live_trace.get(field) is not False:
            failures.append(f"controller_trace_{field}_not_false")
    if not all(artifact.get("passed") for artifact in required_artifacts.values()):
        failures.append("required_controller_or_design_guide_gate_not_green")

    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_controller_browser_live_trace_parity_snapshot.v1",
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
    json_path = ARTIFACT_DIR / f"design_guide_controller_browser_live_trace_parity_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_controller_browser_live_trace_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, md_path)
    print(f"design_guide_controller_browser_live_trace_parity {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + json.dumps(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
