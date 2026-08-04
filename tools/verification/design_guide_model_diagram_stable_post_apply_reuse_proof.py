"""Browser/live proof for stable post-Apply model/diagram reuse eligibility.

Proof-only. The first post-Apply model render may be required when geometry or
reinforcement changes. This verifier checks the next state: a stable no-input
rerun after Apply. It proves whether the model fingerprint stays unchanged and
whether Plotly/model DOM churn still occurs, which is the prerequisite before
any live render skip/bypass can be implemented.

It does not change product behaviour, engineering logic, publication,
CTA/apply semantics, visible wording, widget keys, or family runtimes.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_browser_live_smoothness_profile import (  # noqa: E402
    DEFAULT_RECIPE,
    _run_live_scenario,
)
from tools.verification.design_guide_post_apply_settle_source_profile import (  # noqa: E402
    _install_post_click_mutation_probe,
    _read_post_click_mutation_probe,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "passed": proc.returncode == 0,
    }


def _trace(row: dict[str, Any]) -> dict[str, Any]:
    return dict(((row.get("counters") or {}).get("model_diagram_render_reuse_trace") or {}))


def _first_trace_pair(trace: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    for key in sorted(trace):
        value = trace.get(key)
        if isinstance(value, dict):
            return key, dict(value)
    return None, {}


def _owner_totals(probe: dict[str, Any]) -> dict[str, int]:
    return {str(key): int(value or 0) for key, value in dict(probe.get("ownerTotals") or {}).items()}


def _capture(base_url: str, *, recipe: str, timeout_s: float, headed: bool) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.set_default_timeout(30_000)
        initial = _run_live_scenario(
            page,
            scenario_id="initial_recipe_load",
            action="goto",
            base_url=base_url,
            recipe=recipe,
            timeout_s=timeout_s,
        )
        _install_post_click_mutation_probe(page)
        try:
            post_apply = _run_live_scenario(
                page,
                scenario_id="post_click_apply",
                action="click_apply",
                base_url=base_url,
                recipe=recipe,
                timeout_s=timeout_s,
            )
        except PlaywrightTimeoutError as exc:
            post_apply = {
                "scenario_id": "post_click_apply",
                "action": "click_apply",
                "elapsed_ms": None,
                "click_meta": {"clicked": False, "error": str(exc)},
                "milestones": {},
                "counters": {},
                "layout": {},
                "churn": {},
            }
        post_apply_mutations = _read_post_click_mutation_probe(page)

        stable_reload_url = page.evaluate(
            r"""
            () => {
              const url = new URL(window.location.href);
              url.searchParams.delete("browser_recipe");
              window.history.replaceState({}, "", url.toString());
              return url.toString();
            }
            """
        )
        _install_post_click_mutation_probe(page)
        try:
            stable_post_apply_reload = _run_live_scenario(
                page,
                scenario_id="stable_post_apply_reload",
                action="reload",
                base_url=base_url,
                recipe=recipe,
                timeout_s=timeout_s,
            )
        except PlaywrightTimeoutError as exc:
            stable_post_apply_reload = {
                "scenario_id": "stable_post_apply_reload",
                "action": "reload",
                "elapsed_ms": None,
                "error": str(exc),
                "milestones": {},
                "counters": {},
                "layout": {},
                "churn": {},
            }
        stable_reload_mutations = _read_post_click_mutation_probe(page)
        browser.close()
    return {
        "recipe": recipe,
        "initial": initial,
        "post_apply": post_apply,
        "post_apply_mutations": post_apply_mutations,
        "stable_reload_url": stable_reload_url,
        "stable_post_apply_reload": stable_post_apply_reload,
        "stable_reload_mutations": stable_reload_mutations,
    }


def _classify(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, Any]:
    initial = dict(capture.get("initial") or {})
    post_apply = dict(capture.get("post_apply") or {})
    stable = dict(capture.get("stable_post_apply_reload") or {})
    initial_key, initial_row = _first_trace_pair(_trace(initial))
    post_key, post_row = _first_trace_pair(_trace(post_apply))
    stable_key, stable_row = _first_trace_pair(_trace(stable))

    initial_hash = initial_row.get("render_fingerprint_hash")
    post_hash = post_row.get("render_fingerprint_hash")
    stable_hash = stable_row.get("render_fingerprint_hash")
    post_previous_hash = post_row.get("previous_render_fingerprint_hash")
    stable_previous_hash = stable_row.get("previous_render_fingerprint_hash")
    first_post_apply_changed = bool(initial_hash and post_hash and initial_hash != post_hash)
    stable_after_apply_unchanged = bool(post_hash and stable_hash and post_hash == stable_hash)
    stable_reset_to_initial = bool(initial_hash and stable_hash and initial_hash == stable_hash)
    stable_reports_reuse_eligible = bool(stable_row.get("reuse_eligible"))
    stable_decision = str(stable_row.get("decision") or "")
    stable_totals = _owner_totals(dict(capture.get("stable_reload_mutations") or {}))
    stable_model_or_plotly_mutations = int(stable_totals.get("plotly_or_chart") or 0) + int(
        stable_totals.get("model_panel") or 0
    )
    stable_mutation_total = sum(stable_totals.values())

    blockers: list[str] = []
    observations: list[str] = []
    if not compile_run.get("passed"):
        blockers.append("py_compile_failed")
    if not dict(post_apply.get("click_meta") or {}).get("clicked"):
        blockers.append("post_apply_action_not_clicked")
    if not initial_hash or not post_hash or not stable_hash:
        blockers.append("missing_model_render_fingerprint_hash")
    if not first_post_apply_changed:
        blockers.append("first_post_apply_fingerprint_did_not_change")
    if not stable_after_apply_unchanged:
        blockers.append("stable_post_apply_fingerprint_not_unchanged")
    if stable_reset_to_initial:
        blockers.append("stable_reload_reset_to_initial_recipe_state")
    if (
        not stable_reports_reuse_eligible
        and "TRACE_REUSE_ELIGIBLE" not in stable_decision
        and stable_model_or_plotly_mutations >= 100
    ):
        blockers.append("stable_post_apply_trace_not_reuse_eligible")
    elif not stable_reports_reuse_eligible and "TRACE_REUSE_ELIGIBLE" not in stable_decision:
        observations.append("stable_trace_not_reuse_eligible_but_no_model_or_plotly_churn")
    if stable_previous_hash is None:
        observations.append("stable_trace_previous_hash_not_persisted_across_reload")

    if blockers:
        decision = "NOT_READY_FOR_STABLE_POST_APPLY_REUSE"
        ready_for_guarded_bypass_readiness = False
    elif stable_model_or_plotly_mutations >= 100:
        decision = "READY_FOR_STABLE_POST_APPLY_REUSE_READINESS_SLICE"
        ready_for_guarded_bypass_readiness = True
    else:
        decision = "STABLE_POST_APPLY_REUSE_ELIGIBLE_BUT_NO_CHURN_HOTSPOT"
        ready_for_guarded_bypass_readiness = False

    return {
        "status": "PASS",
        "decision": decision,
        "ready_for_guarded_bypass_readiness": ready_for_guarded_bypass_readiness,
        "blockers": blockers,
        "observations": observations,
        "product_behaviour_changed": False,
        "trace_keys": {
            "initial": initial_key,
            "post_apply": post_key,
            "stable_post_apply_reload": stable_key,
        },
        "fingerprints": {
            "initial_hash": initial_hash,
            "post_apply_previous_hash": post_previous_hash,
            "post_apply_hash": post_hash,
            "stable_previous_hash": stable_previous_hash,
            "stable_hash": stable_hash,
            "first_post_apply_changed": first_post_apply_changed,
            "stable_after_apply_unchanged": stable_after_apply_unchanged,
            "stable_reset_to_initial": stable_reset_to_initial,
            "stable_reuse_eligible": stable_reports_reuse_eligible,
            "stable_decision": stable_decision,
        },
        "stable_reload_mutations": {
            "owner_totals": stable_totals,
            "total": stable_mutation_total,
            "model_or_plotly_total": stable_model_or_plotly_mutations,
        },
        "recommended_next_slice": (
            "Create readiness proof for a guarded stable-post-Apply model/diagram render reuse implementation keyed by the model fingerprint."
            if ready_for_guarded_bypass_readiness
            else "Do not implement model/diagram render reuse from this proof; resolve blockers or gather a stronger stable-rerun churn sample first."
        ),
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_model_diagram_stable_post_apply_reuse_proof_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_model_diagram_stable_post_apply_reuse_proof_{stamp}.md"
    summary = dict(payload.get("summary") or {})
    lines = [
        "# Design Guide Model/Diagram Stable Post-Apply Reuse Proof",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Decision: `{summary.get('decision')}`",
        f"- Ready for guarded bypass readiness: `{summary.get('ready_for_guarded_bypass_readiness')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        "",
        "## Fingerprints",
        "",
        "```json",
        json.dumps(summary.get("fingerprints") or {}, indent=2, sort_keys=True, default=str),
        "```",
        "",
        "## Stable Reload Mutations",
        "",
        "```json",
        json.dumps(summary.get("stable_reload_mutations") or {}, indent=2, sort_keys=True, default=str),
        "```",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- `{item}`" for item in summary.get("blockers") or [])
    lines.extend(["", "## Observations", ""])
    lines.extend(f"- `{item}`" for item in summary.get("observations") or [])
    lines.extend(["", "## Recommendation", "", str(summary.get("recommended_next_slice") or ""), ""])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8687)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_STABLE_POST_APPLY_REUSE_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--timeout-s", type=float, default=55.0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://127.0.0.1:{args.port}")
    if not args.base_url:
        process = _start_streamlit(args.port)
        _wait_for_http(base_url, timeout_s=90)
    try:
        compile_run = _run([sys.executable, "-m", "py_compile", "inputs_page.py"])
        capture = _capture(base_url, recipe=args.recipe, timeout_s=args.timeout_s, headed=args.headed)
        summary = _classify(capture, compile_run)
        payload = {
            "schema": "design_guide_model_diagram_stable_post_apply_reuse_proof.v1",
            "created_at": _stamp(),
            "status": summary["status"],
            "base_url": base_url,
            "recipe": args.recipe,
            "product_behaviour_changed": False,
            "compile_run": compile_run,
            "summary": summary,
            **capture,
        }
        json_path, md_path = _write(payload)
        print(f"wrote {json_path}")
        print(f"wrote {md_path}")
        print(json.dumps({"status": payload["status"], "decision": summary["decision"]}, indent=2))
        return 0 if payload["status"] == "PASS" else 1
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
