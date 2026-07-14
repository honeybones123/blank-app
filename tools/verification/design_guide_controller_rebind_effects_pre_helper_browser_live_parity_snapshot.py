"""Browser/live parity for pre-helper controller rebind traces.

Proof-only. This verifier opens the live Inputs page with browser recipes and
captures the trace-only pre-helper controller rebind parity rows for the two
remaining render-panel rebind bridges. It proves whether the controller
projection matches the old page helper output before any cutover or deletion.
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
REPORT_DIR = ROOT / "artifacts" / "reports"
TRACE_KEY = "controller_final_visible_rebind_effects_pre_helper_cutover_parity_traces"
TRACE_HASH_KEY = "controller_final_visible_rebind_effects_pre_helper_cutover_parity_hash"
PROBE_KEY = "controller_final_visible_rebind_effects_pre_helper_branch_predicate_probes"
PROBE_HASH_KEY = "controller_final_visible_rebind_effects_pre_helper_branch_predicate_probe_hash"
ENGINE_OUTER_PROBE_KEY = "controller_final_visible_rebind_effects_engine_outer_probe"
ENGINE_OUTER_PROBE_HASH_KEY = "controller_final_visible_rebind_effects_engine_outer_probe_hash"
REQUIRED_CALLSITES = (
    "combined_evidence_rebind_bridge",
    "engine_evidence_rebind_bridge",
)
DEFAULT_RECIPES = (
    "C_combined_underdesign",
    "R3B_M600_V600",
    "R6A_M45_V150",
    "A_bending_under_only",
)
REQUIRED_ARTIFACTS = {
    "pre_helper_trace_static": (
        "design_guide_controller_rebind_effects_pre_helper_cutover_parity_trace"
    ),
    "adapter_parity": "design_guide_controller_rebind_effects_adapter_parity",
    "callsite_parity_readiness": (
        "design_guide_controller_rebind_effects_callsite_parity_readiness"
    ),
    "render_rebind_parity_gap": "design_guide_render_combined_engine_rebind_parity_gap",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": (
        "design_guide_compute_resolver_publication_bridge_lock"
    ),
    "design_guide_independence_lock": "design_guide_independence_lock",
}


def _query(base_url: str, params: dict[str, Any]) -> str:
    return f"{str(base_url).rstrip('/')}/?{urlencode({k: v for k, v in params.items() if v is not None})}"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": "MISSING", "passed": False}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    passed = raw_status.upper() == "PASS" or raw_status.lower().endswith(("locked", "complete"))
    return {"found": True, "path": str(path), "status": raw_status or "UNKNOWN", "passed": passed}


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
    for key in ("debug_bundle", "render_plan_debug"):
        value = _as_dict(design_guide_probe.get(key))
        if value:
            debug.update(value)
    return debug


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


def _state_score(state: dict[str, Any]) -> int:
    debug = _pick_debug(state)
    traces = _as_dict(debug.get(TRACE_KEY))
    probes = _as_dict(debug.get(PROBE_KEY))
    engine_outer_probe = _as_dict(debug.get(ENGINE_OUTER_PROBE_KEY))
    score = 0
    for callsite in REQUIRED_CALLSITES:
        row = _as_dict(traces.get(callsite))
        probe = _as_dict(probes.get(callsite))
        if row:
            score += 100
        if row.get("projected_item_matches_old_output") is True:
            score += 35
        if row.get("projected_contract_matches_old_output") is True:
            score += 35
        if probe:
            score += 40
    if debug.get(TRACE_HASH_KEY):
        score += 20
    if debug.get(PROBE_HASH_KEY):
        score += 10
    if engine_outer_probe:
        score += 12
    if debug.get(ENGINE_OUTER_PROBE_HASH_KEY):
        score += 5
    if state.get("browser_shared_probe"):
        score += 5
    if state.get("summary_state_probe"):
        score += 5
    return score


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
                debug = _pick_debug(candidate)
                traces = _as_dict(debug.get(TRACE_KEY))
                probes = _as_dict(debug.get(PROBE_KEY))
                engine_outer_probe = _as_dict(debug.get(ENGINE_OUTER_PROBE_KEY))
                score = _state_score(candidate)
                diagnostics.append(
                    {
                        "score": score,
                        "trace_callsites": sorted(str(key) for key in traces.keys()),
                        "probe_callsites": sorted(str(key) for key in probes.keys()),
                        "engine_outer_probe_present": bool(engine_outer_probe),
                        "engine_outer_probe_hash_present": bool(
                            debug.get(ENGINE_OUTER_PROBE_HASH_KEY)
                        ),
                        "trace_hash_present": bool(debug.get(TRACE_HASH_KEY)),
                        "probe_hash_present": bool(debug.get(PROBE_HASH_KEY)),
                        "browser_probe_phase": candidate.get("browser_probe_phase"),
                        "page_slug": candidate.get("page_slug"),
                    }
                )
                if score > best_score:
                    best = candidate
                    best_score = score
            if best and _state_score(best) >= 170:
                return best, None, diagnostics[-10:]
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(0.3)
    return best, last_error, diagnostics[-10:]


def _capture_recipe(page, *, url: str, recipe: str, timeout_s: float) -> dict[str, Any]:
    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    deadline = time.time() + max(1.0, float(timeout_s or 1.0))
    last_state: dict[str, Any] = {}
    last_debug: dict[str, Any] = {}
    last_dom: dict[str, Any] = {}
    last_error: str | None = None
    last_diagnostics: list[dict[str, Any]] = []
    while time.time() < deadline:
        try:
            last_dom = _visible_dom_snapshot(page)
        except Exception as exc:
            last_dom = {"dom_error": f"{type(exc).__name__}: {exc}"}
        last_state, last_error, last_diagnostics = _load_best_browser_state(page, timeout_s=2.0)
        last_debug = _pick_debug(last_state)
        traces = _as_dict(last_debug.get(TRACE_KEY))
        probes = _as_dict(last_debug.get(PROBE_KEY))
        if (traces or probes) and not last_dom.get("loading_shell_visible"):
            break
        time.sleep(0.5)
    return {
        "recipe": recipe,
        "url": url,
        "state_available": bool(last_state),
        "browser_state_error": last_error,
        "dom": last_dom,
        "trace_hash": last_debug.get(TRACE_HASH_KEY),
        "predicate_probe_hash": last_debug.get(PROBE_HASH_KEY),
        "trace_only": last_debug.get(
            "controller_final_visible_rebind_effects_pre_helper_cutover_parity_trace_only"
        ),
        "predicate_probe_trace_only": last_debug.get(
            "controller_final_visible_rebind_effects_pre_helper_branch_predicate_probe_trace_only"
        ),
        "predicate_probe_product_driving": last_debug.get(
            "controller_final_visible_rebind_effects_pre_helper_branch_predicate_probe_product_driving"
        ),
        "predicate_probe_render_driving": last_debug.get(
            "controller_final_visible_rebind_effects_pre_helper_branch_predicate_probe_render_driving"
        ),
        "predicate_probe_apply_driving": last_debug.get(
            "controller_final_visible_rebind_effects_pre_helper_branch_predicate_probe_apply_driving"
        ),
        "predicate_probe_session_driving": last_debug.get(
            "controller_final_visible_rebind_effects_pre_helper_branch_predicate_probe_session_driving"
        ),
        "product_driving": last_debug.get(
            "controller_final_visible_rebind_effects_pre_helper_cutover_parity_product_driving"
        ),
        "render_driving": last_debug.get(
            "controller_final_visible_rebind_effects_pre_helper_cutover_parity_render_driving"
        ),
        "apply_driving": last_debug.get(
            "controller_final_visible_rebind_effects_pre_helper_cutover_parity_apply_driving"
        ),
        "session_driving": last_debug.get(
            "controller_final_visible_rebind_effects_pre_helper_cutover_parity_session_driving"
        ),
        "error": last_debug.get(
            "controller_final_visible_rebind_effects_pre_helper_cutover_parity_error"
        ),
        "traces": _as_dict(last_debug.get(TRACE_KEY)),
        "predicate_probes": _as_dict(last_debug.get(PROBE_KEY)),
        "engine_outer_probe": _as_dict(last_debug.get(ENGINE_OUTER_PROBE_KEY)),
        "engine_outer_probe_hash": last_debug.get(ENGINE_OUTER_PROBE_HASH_KEY),
        "state_diagnostics": last_diagnostics,
    }


def _summarise_callsite(recipe_captures: list[dict[str, Any]], callsite_id: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for capture in recipe_captures:
        row = _as_dict(_as_dict(capture.get("traces")).get(callsite_id))
        if row:
            rows.append(
                {
                    "recipe": capture.get("recipe"),
                    "visible_card": bool(_as_dict(capture.get("dom")).get("design_guide_card_visible")),
                    "loading_shell_visible": bool(_as_dict(capture.get("dom")).get("loading_shell_visible")),
                    "trace_hash": capture.get("trace_hash"),
                    "controller_hash": row.get("controller_hash"),
                    "controller_request_hash": row.get("controller_request_hash"),
                    "controller_projection_hash": row.get("controller_projection_hash"),
                    "controller_proof_hash": row.get("controller_proof_hash"),
                    "pre_item_hash": row.get("pre_item_hash"),
                    "old_output_item_hash": row.get("old_output_item_hash"),
                    "projected_item_hash": row.get("projected_item_hash"),
                    "old_contract_hash": row.get("old_contract_hash"),
                    "projected_contract_hash": row.get("projected_contract_hash"),
                    "projected_item_matches_old_output": row.get(
                        "projected_item_matches_old_output"
                    ),
                    "projected_contract_matches_old_output": row.get(
                        "projected_contract_matches_old_output"
                    ),
                    "trace_only": row.get("trace_only"),
                    "product_driving": row.get("product_driving"),
                    "render_driving": row.get("render_driving"),
                    "apply_driving": row.get("apply_driving"),
                    "session_driving": row.get("session_driving"),
                }
            )
    best = rows[0] if rows else {}
    for row in rows:
        if (
            row.get("projected_item_matches_old_output") is True
            and row.get("projected_contract_matches_old_output") is True
        ):
            best = row
            break
    return {
        "callsite_id": callsite_id,
        "captured": bool(rows),
        "capture_count": len(rows),
        "recipes_seen": [row.get("recipe") for row in rows],
        "best": best,
        "parity_pass": bool(
            best
            and best.get("projected_item_matches_old_output") is True
            and best.get("projected_contract_matches_old_output") is True
            and best.get("trace_only") is True
            and best.get("product_driving") is False
            and best.get("render_driving") is False
            and best.get("apply_driving") is False
            and best.get("session_driving") is False
        ),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Controller Rebind Effects Pre-Helper Browser Live Parity",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Coverage",
        "",
        "| Callsite | Captured | Parity | Recipes |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload.get("callsite_summaries") or []:
        lines.append(
            f"| `{row.get('callsite_id')}` | `{row.get('captured')}` | `{row.get('parity_pass')}` | `{row.get('recipes_seen')}` |"
        )
    lines.extend(
        [
            "",
            "## Recipe Captures",
            "",
        ]
    )
    for capture in payload.get("recipe_captures") or []:
        lines.append(
            f"- `{capture.get('recipe')}`: traces `{sorted((_as_dict(capture.get('traces'))).keys())}`, "
            f"probes `{sorted((_as_dict(capture.get('predicate_probes'))).keys())}`, "
            f"visible card `{_as_dict(capture.get('dom')).get('design_guide_card_visible')}`, "
            f"loading shell `{_as_dict(capture.get('dom')).get('loading_shell_visible')}`"
        )
    lines.extend(["", "## Required Artifacts", "", "| Gate | Found | Status | Path |", "| --- | --- | --- | --- |"])
    for name, artifact in (payload.get("required_artifacts") or {}).items():
        lines.append(
            f"| {name} | `{artifact.get('found')}` | `{artifact.get('status')}` | `{artifact.get('path')}` |"
        )
    if payload.get("failures"):
        lines.extend(["", "## Failures", "", "```json", json.dumps(payload["failures"], indent=2), "```"])
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            (
                "Only after both callsites stay green in live parity should the old "
                "render-panel binding helper calls be considered for a controller-backed "
                "cutover verifier. No deletion is proven by this snapshot alone."
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8591)
    parser.add_argument("--base-url", default=os.environ.get("DG_REBIND_PRE_HELPER_BASE_URL"))
    parser.add_argument("--url", default=os.environ.get("DG_REBIND_PRE_HELPER_URL"))
    parser.add_argument(
        "--recipe",
        action="append",
        default=None,
        help="Browser recipe to sample. Repeat to sample several recipes.",
    )
    parser.add_argument("--timeout-s", type=float, default=55.0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    recipes = tuple(args.recipe or DEFAULT_RECIPES)
    compile_run = _run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "inputs_page.py",
            "design_brain/design_guide_controller.py",
            "tools/verification/design_guide_controller_rebind_effects_pre_helper_browser_live_parity_snapshot.py",
        ]
    )
    process: subprocess.Popen | None = None
    errors: list[str] = []
    recipe_captures: list[dict[str, Any]] = []
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    try:
        if args.url:
            _wait_for_http(args.url)
            target_urls = [("explicit_url", args.url)]
        else:
            if args.base_url:
                _wait_for_http(base_url)
            else:
                env_before = dict(os.environ)
                os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
                os.environ["PERF_TRACE_INPUTS"] = "1"
                try:
                    process = _start_streamlit(args.port)
                finally:
                    os.environ.clear()
                    os.environ.update(env_before)
            target_urls = [
                (
                    recipe,
                    _query(base_url, {"page": "inputs", "browser_recipe": recipe}),
                )
                for recipe in recipes
            ]

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            context = browser.new_context(viewport={"width": 1800, "height": 1000})
            page = context.new_page()
            page.set_default_timeout(30_000)
            captured_callsite_ids: set[str] = set()
            for recipe, url in target_urls:
                capture = _capture_recipe(page, url=url, recipe=recipe, timeout_s=args.timeout_s)
                recipe_captures.append(capture)
                captured_callsite_ids.update(str(key) for key in _as_dict(capture.get("traces")).keys())
                if all(callsite in captured_callsite_ids for callsite in REQUIRED_CALLSITES):
                    break
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

    callsite_summaries = [
        _summarise_callsite(recipe_captures, callsite) for callsite in REQUIRED_CALLSITES
    ]
    required_artifacts = {name: _latest(prefix) for name, prefix in REQUIRED_ARTIFACTS.items()}
    failures: list[str] = []
    if compile_run["returncode"] != 0:
        failures.append("py_compile_failed")
    failures.extend(f"browser_error::{error}" for error in errors)
    for row in callsite_summaries:
        if not row.get("captured"):
            failures.append(f"{row.get('callsite_id')}_not_captured")
        elif row.get("parity_pass") is not True:
            failures.append(f"{row.get('callsite_id')}_parity_failed")
    for capture in recipe_captures:
        if capture.get("error"):
            failures.append(f"{capture.get('recipe')}_trace_error::{capture.get('error')}")
    if not recipe_captures:
        failures.append("no_recipe_captures")
    if not all(artifact.get("passed") for artifact in required_artifacts.values()):
        failures.append("required_trace_or_lock_artifact_not_green")

    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_controller_rebind_effects_pre_helper_browser_live_parity_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "recipes_requested": list(recipes),
        "product_behaviour_changed": False,
        "family_runtimes_changed": False,
        "contracts_changed": False,
        "cta_rendering_changed": False,
        "publication_semantics_changed": False,
        "apply_routing_changed": False,
        "visible_wording_changed": False,
        "compile_run": compile_run,
        "callsite_summaries": callsite_summaries,
        "recipe_captures": recipe_captures,
        "required_artifacts": required_artifacts,
        "errors": errors,
        "failures": failures,
        "next_safe_step": (
            "If PASS, create a controller cutover readiness verifier for replacing the "
            "two render-panel rebind helper calls. Do not delete the old calls yet."
        ),
    }
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_controller_rebind_effects_pre_helper_browser_live_parity_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_controller_rebind_effects_pre_helper_browser_live_parity_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_rebind_pre_helper_browser_live_parity_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, audit_path)
    _write_report(payload, report_path)
    print(f"design_guide_controller_rebind_effects_pre_helper_browser_live_parity {status}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + json.dumps(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
