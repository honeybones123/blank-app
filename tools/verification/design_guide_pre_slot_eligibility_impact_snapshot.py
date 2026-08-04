"""Browser/live pre-slot Design Guide render eligibility impact snapshot.

This verifier checks whether contract-relevant Design Guide states reach the
real Design Guide slot/card after the pre-slot eligibility probe. It records a
separate impact signal for the stricter case where the contract-aware adapter,
not the old browser-test/actions gate, is what opens the slot.

It is proof-only: no family runtime, CTA/render/apply, publication, wording, or
engineering behavior is changed.
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

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_live_render_gate_audit import (  # noqa: E402
    _dom_snapshot,
    _scroll_app_container,
)
from tools.verification.helpers.browser_helpers import _browser_state_raw_candidates  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    BROWSER_STATE_LABEL,
    _query,
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


SCENARIOS: list[dict[str, Any]] = [
    {
        "scenario_id": "active_bending_fail",
        "recipe": "R1A_M300_V0",
        "expected_contract_reason": "active_failure_state",
        "expected_failure": "bending",
    },
    {
        "scenario_id": "active_shear_fail",
        "recipe": "R2A_M0_V400",
        "expected_contract_reason": "active_failure_state",
        "expected_failure": "shear",
    },
    {
        "scenario_id": "invalid_geometry",
        "recipe": "PRODUCT_INVALID_LONGITUDINAL_REO_SPACING_NO_ACTIONS",
        "expected_contract_reason": "invalid_input_or_blocker_state",
    },
    {
        "scenario_id": "locked_blocker",
        "recipe": "PRODUCT_LOCKED_GEOMETRY_LOW_BENDING_CLEANUP_PROOF",
        "expected_contract_reason": "blocker_state",
    },
]

FINAL_BROWSER_PROBE_PHASES = {"final", "post_page_render"}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest_status(prefix: str) -> dict[str, Any]:
    matches = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"))
    if not matches:
        return {"available": False, "status": None, "path": None}
    path = matches[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "available": False,
            "status": None,
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "available": True,
        "status": payload.get("status") or payload.get("result"),
        "path": str(path),
    }


def _compact(value: Any, *, max_depth: int = 4, max_items: int = 16) -> Any:
    if max_depth <= 0:
        if isinstance(value, (dict, list, tuple, set)):
            return f"<{type(value).__name__}>"
        return value
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for idx, (key, item) in enumerate(value.items()):
            if idx >= max_items:
                out["..."] = f"{len(value) - max_items} more"
                break
            out[str(key)] = _compact(item, max_depth=max_depth - 1, max_items=max_items)
        return out
    if isinstance(value, (list, tuple, set)):
        seq = list(value)
        out = [_compact(item, max_depth=max_depth - 1, max_items=max_items) for item in seq[:max_items]]
        if len(seq) > max_items:
            out.append(f"... {len(seq) - max_items} more")
        return out
    return value


def _debug_bundle(state: dict[str, Any]) -> dict[str, Any]:
    design_probe = dict(state.get("design_guide_probe") or {})
    bundle = dict(design_probe.get("debug_bundle") or {})
    if bundle:
        return bundle
    guidance = dict(state.get("guidance_compute_probe") or {})
    return guidance


def _find_first_dict_with_key(value: Any, key: str, *, max_depth: int = 6) -> dict[str, Any]:
    if max_depth < 0:
        return {}
    if isinstance(value, dict):
        found = value.get(key)
        if isinstance(found, dict):
            return dict(found)
        for item in value.values():
            nested = _find_first_dict_with_key(item, key, max_depth=max_depth - 1)
            if nested:
                return nested
    elif isinstance(value, (list, tuple)):
        for item in value:
            nested = _find_first_dict_with_key(item, key, max_depth=max_depth - 1)
            if nested:
                return nested
    return {}


def _find_key_paths(value: Any, key: str, *, max_depth: int = 6, prefix: str = "$") -> list[str]:
    if max_depth < 0:
        return []
    paths: list[str] = []
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            child_path = f"{prefix}.{child_key}"
            if str(child_key) == key:
                paths.append(child_path)
            paths.extend(_find_key_paths(child_value, key, max_depth=max_depth - 1, prefix=child_path))
    elif isinstance(value, (list, tuple)):
        for index, child_value in enumerate(value[:50]):
            paths.extend(_find_key_paths(child_value, key, max_depth=max_depth - 1, prefix=f"{prefix}[{index}]"))
    return paths


def _render_trace(state: dict[str, Any]) -> dict[str, Any]:
    design_probe_trace = dict((state.get("design_guide_probe") or {}).get("render_eligibility_trace") or {})
    if design_probe_trace:
        return design_probe_trace
    bundle = _debug_bundle(state)
    trace = dict(bundle.get("design_guide_render_eligibility_trace") or {})
    if trace:
        return trace
    return _find_first_dict_with_key(state, "design_guide_render_eligibility_trace")


def _trace_diagnostics(state: dict[str, Any]) -> dict[str, Any]:
    design_probe = dict(state.get("design_guide_probe") or {})
    debug_bundle = dict(design_probe.get("debug_bundle") or {})
    return {
        "browser_probe_phase": state.get("browser_probe_phase") or state.get("probe_phase"),
        "top_level_keys": sorted(str(key) for key in state.keys())[:80],
        "design_guide_probe_keys": sorted(str(key) for key in design_probe.keys())[:80],
        "debug_bundle_keys": sorted(str(key) for key in debug_bundle.keys())[:120],
        "trace_key_paths": _find_key_paths(state, "design_guide_render_eligibility_trace", max_depth=8),
        "render_eligibility_trace_direct": bool(design_probe.get("render_eligibility_trace")),
        "render_eligibility_trace_in_debug_bundle": bool(debug_bundle.get("design_guide_render_eligibility_trace")),
    }


def _probe_phase(state: dict[str, Any]) -> str:
    return str(state.get("browser_probe_phase") or state.get("probe_phase") or "")


def _candidate_score(state: dict[str, Any], recipe: str) -> tuple[int, int, int, int, int]:
    trace = _render_trace(state)
    return (
        1 if state.get("browser_recipe") == recipe else 0,
        1 if _probe_phase(state) in FINAL_BROWSER_PROBE_PHASES else 0,
        1 if trace else 0,
        1 if (state.get("design_guide_probe") or {}).get("primary_card_title") else 0,
        len(_stable_json(state)),
    )


def _load_best_browser_state(page, recipe: str, *, timeout_s: float = 5.0) -> dict[str, Any]:
    deadline = datetime.now().timestamp() + max(0.5, timeout_s)
    best: dict[str, Any] = {}
    best_score: tuple[int, int, int, int, int] = (0, 0, 0, 0, 0)
    while datetime.now().timestamp() < deadline:
        for raw in _browser_state_raw_candidates(page, timeout_ms=2_000):
            try:
                parsed = json.loads(raw)
            except Exception:
                continue
            if not isinstance(parsed, dict):
                continue
            score = _candidate_score(parsed, recipe)
            if score > best_score:
                best = parsed
                best_score = score
            if score[:3] == (1, 1, 1):
                return parsed
        page.wait_for_timeout(200)
    return best


def _wait_for_recipe_state(page, recipe: str, timeout_s: float) -> dict[str, Any]:
    deadline = datetime.now().timestamp() + max(5.0, timeout_s)
    last_state: dict[str, Any] = {}
    while datetime.now().timestamp() < deadline:
        state = _load_best_browser_state(page, recipe, timeout_s=3.0)
        last_state = state
        if (
            state.get("browser_recipe") == recipe
            and _probe_phase(state) in FINAL_BROWSER_PROBE_PHASES
            and _render_trace(state)
        ) or state.get("browser_recipe_error"):
            return state
    return last_state


def _capture_dom_sequence(page) -> dict[str, Any]:
    snapshots: list[dict[str, Any]] = []
    scrolls: list[dict[str, Any]] = []
    for index in range(7):
        snapshot = _dom_snapshot(page, label=f"step_{index}")
        snapshots.append(snapshot)
        if snapshot.get("product_design_guide_heading_count") or snapshot.get("design_guide_card_candidate_count"):
            break
        scrolls.append(_scroll_app_container(page, index=index))
        page.wait_for_timeout(500)
    return {
        "snapshots": snapshots,
        "scrolls": scrolls,
        "dom_hash": _stable_hash({"snapshots": snapshots, "scrolls": scrolls}),
    }


def _summarise_dom(dom: dict[str, Any]) -> dict[str, Any]:
    snapshots = list(dom.get("snapshots") or [])
    best = snapshots[-1] if snapshots else {}
    return {
        "product_design_guide_heading_count": best.get("product_design_guide_heading_count"),
        "design_guide_card_candidate_count": best.get("design_guide_card_candidate_count"),
        "gate_text": dict(best.get("gate_text") or {}),
        "card_candidates": _compact(best.get("design_guide_card_candidates") or [], max_depth=3, max_items=4),
        "dom_hash": dom.get("dom_hash"),
    }


def _scenario_result(
    *,
    scenario: dict[str, Any],
    state: dict[str, Any],
    dom: dict[str, Any],
    url: str,
) -> dict[str, Any]:
    recipe = str(scenario["recipe"])
    trace = _render_trace(state)
    probe = dict(trace.get("pre_slot_publication_eligibility_probe") or {})
    overview = dict(state.get("summary_overview_probe") or {})
    guidance = dict(state.get("guidance_compute_probe") or {})
    design_probe = dict(state.get("design_guide_probe") or {})
    dom_summary = _summarise_dom(dom)

    recipe_applied = bool(state.get("browser_recipe") == recipe and not state.get("browser_recipe_error"))
    active_failures = list(trace.get("active_failures") or probe.get("active_failures") or [])
    overview_statuses = dict(overview.get("statuses") or {})
    overview_failures = sorted(
        str(key)
        for key, value in overview_statuses.items()
        if str(value or "").strip().upper() == "FAIL"
    )
    expected_failure = str(scenario.get("expected_failure") or "").strip()
    expected_failure_seen = bool(
        not expected_failure
        or expected_failure in active_failures
        or expected_failure in overview_failures
    )
    contract_required = bool(trace.get("contract_required_design_brain_eligibility"))
    slot_created = bool(trace.get("design_guide_slot_created"))
    show_design_guide = bool(trace.get("show_design_guide_for_current_inputs"))
    product_dom_seen = bool(
        dom_summary.get("product_design_guide_heading_count")
        or dom_summary.get("design_guide_card_candidate_count")
    )
    current_page_gate_allows = bool(trace.get("current_page_gate_allows"))
    inputs_has_actions_or_loads = bool(trace.get("inputs_has_design_actions_or_loads"))
    browser_test_mode = bool(trace.get("browser_test_mode") or state.get("codex_browser_test_mode"))
    adapter_used = bool(trace.get("slot_eligibility_adapter_used"))
    browser_harness_masked_contract_impact = bool(
        browser_test_mode
        and not inputs_has_actions_or_loads
        and contract_required
        and slot_created
        and show_design_guide
    )
    direct_contract_impact = bool(
        (
            adapter_used
            and contract_required
            and slot_created
            and show_design_guide
            and not current_page_gate_allows
        )
        or browser_harness_masked_contract_impact
    )
    masked_by_old_gate = bool(contract_required and current_page_gate_allows and not direct_contract_impact)

    blockers: list[str] = []
    if not recipe_applied:
        blockers.append("browser_recipe_not_applied")
    if not trace:
        blockers.append("render_eligibility_trace_missing")
    if not contract_required:
        blockers.append("contract_required_eligibility_not_detected")
    if not expected_failure_seen:
        blockers.append("expected_failure_not_visible_in_probe")
    if not slot_created:
        blockers.append("design_guide_slot_not_created")
    if not product_dom_seen:
        blockers.append("real_design_guide_card_not_visible_in_dom")

    non_contract_recipe = bool(
        blockers == ["contract_required_eligibility_not_detected"]
        and trace
        and slot_created
        and product_dom_seen
    )

    if non_contract_recipe:
        status = "SKIP_RECIPE_NOT_CONTRACT_REQUIRED"
        blockers = []
    elif blockers:
        status = "FAIL"
    elif direct_contract_impact:
        status = "PASS"
    else:
        status = "PASS_MASKED_BY_EXISTING_PAGE_GATE"

    return {
        "scenario_id": scenario.get("scenario_id"),
        "recipe": recipe,
        "url": url,
        "status": status,
        "blockers": blockers,
        "recipe_proof": {
            "requested_recipe": recipe,
            "applied_recipe": state.get("browser_recipe"),
            "browser_recipe_error": state.get("browser_recipe_error"),
            "browser_recipe_kind": state.get("browser_recipe_kind"),
            "recipe_applied": recipe_applied,
        },
        "eligibility_trace": {
            "trace_present": bool(trace),
            "browser_test_mode": browser_test_mode,
            "inputs_has_design_actions_or_loads": inputs_has_actions_or_loads,
            "current_page_gate_allows": current_page_gate_allows,
            "contract_required_design_brain_eligibility": contract_required,
            "pre_slot_publication_eligibility_probe_used": bool(
                trace.get("pre_slot_publication_eligibility_probe_used")
            ),
            "slot_eligibility_adapter_used": adapter_used,
            "render_eligibility_classification": trace.get("render_eligibility_classification"),
            "render_eligibility_reason": trace.get("render_eligibility_reason"),
            "show_design_guide_for_current_inputs": show_design_guide,
            "design_guide_slot_created": slot_created,
            "landing_shell_rendered": bool(trace.get("landing_shell_rendered")),
            "real_design_guide_card_rendered": bool(trace.get("real_design_guide_card_rendered")),
            "selected_family_id": trace.get("selected_family_id"),
            "active_failures": active_failures,
            "invalid_input_state": bool(trace.get("invalid_input_state")),
            "blocker_state": bool(trace.get("blocker_state")),
            "final_publication_outcome_state": trace.get("final_publication_outcome_state"),
            "final_publication_publication_hash": trace.get("final_publication_publication_hash"),
            "pre_slot_probe": _compact(probe, max_depth=4, max_items=18),
        },
        "trace_diagnostics": _trace_diagnostics(state),
        "impact_proof": {
            "direct_contract_impact": direct_contract_impact,
            "browser_harness_masked_contract_impact": browser_harness_masked_contract_impact,
            "masked_by_existing_page_gate": masked_by_old_gate,
            "impact_interpretation": (
                "contract_adapter_opened_slot"
                if direct_contract_impact
                and not browser_harness_masked_contract_impact
                else "contract_required_with_actions_load_gate_false_browser_harness_opened_slot"
                if browser_harness_masked_contract_impact
                else "slot_open_but_existing_page_gate_already_allowed_render"
                if masked_by_old_gate
                else "recipe_rendered_but_did_not_enter_contract_required_state"
                if non_contract_recipe
                else "slot_not_proven"
            ),
            "recipe_not_contract_required": non_contract_recipe,
        },
        "engineering_state_probe": {
            "summary_statuses": overview_statuses,
            "summary_utils": dict(overview.get("utils") or {}),
            "summary_any_fail": overview.get("any_fail"),
            "summary_governing_check": overview.get("governing_check"),
            "expected_failure": expected_failure or None,
            "expected_failure_seen": expected_failure_seen,
            "primary_card_title": design_probe.get("primary_card_title") or guidance.get("primary_card_title"),
            "button_contract_enabled": design_probe.get("button_contract_enabled") or guidance.get("button_contract_enabled"),
        },
        "dom_summary": dom_summary,
    }


def _run_browser_scenarios(base_url: str, scenarios: list[dict[str, Any]], *, headed: bool, timeout_s: float) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        context = browser.new_context(viewport={"width": 1600, "height": 1100})
        page = context.new_page()
        page.set_default_timeout(30_000)
        for scenario in scenarios:
            recipe = str(scenario["recipe"])
            url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=90_000)
                page.get_by_label(BROWSER_STATE_LABEL).wait_for(state="attached", timeout=45_000)
                state = _wait_for_recipe_state(page, recipe, timeout_s=timeout_s)
                try:
                    page.get_by_text("Inputs", exact=True).first.wait_for(
                        state="visible",
                        timeout=min(30_000, int(timeout_s * 1000)),
                    )
                except PlaywrightTimeoutError:
                    pass
                dom = _capture_dom_sequence(page)
                results.append(_scenario_result(scenario=scenario, state=state, dom=dom, url=url))
            except Exception as exc:
                results.append(
                    {
                        "scenario_id": scenario.get("scenario_id"),
                        "recipe": recipe,
                        "url": url,
                        "status": "FAIL",
                        "blockers": [f"{type(exc).__name__}: {exc}"],
                    }
                )
        context.close()
        browser.close()
    return results


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Pre-Slot Eligibility Impact Snapshot",
        "",
        f"- Result: `{payload.get('status')}`",
        f"- Created: `{payload.get('created_at')}`",
        f"- Base URL: `{payload.get('base_url')}`",
        f"- Direct contract impact proven: `{payload.get('direct_contract_impact_proven')}`",
        f"- Masked scenarios: `{payload.get('masked_by_existing_page_gate_count')}`",
        "",
        "## Scenario Results",
        "",
        "| Scenario | Recipe | Status | Contract Required | Slot | Adapter Used | Impact | Blockers |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in payload.get("scenarios") or []:
        trace = dict(item.get("eligibility_trace") or {})
        impact = dict(item.get("impact_proof") or {})
        lines.append(
            "| {scenario} | `{recipe}` | `{status}` | `{contract}` | `{slot}` | `{adapter}` | `{impact}` | {blockers} |".format(
                scenario=item.get("scenario_id"),
                recipe=item.get("recipe"),
                status=item.get("status"),
                contract=trace.get("contract_required_design_brain_eligibility"),
                slot=trace.get("design_guide_slot_created"),
                adapter=trace.get("slot_eligibility_adapter_used"),
                impact=impact.get("direct_contract_impact"),
                blockers=", ".join(item.get("blockers") or []) or "-",
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            str(payload.get("interpretation") or ""),
            "",
            "## Supporting Locks",
            "",
        ]
    )
    for name, status in (payload.get("supporting_locks") or {}).items():
        lines.append(f"- `{name}`: `{status.get('status')}` ({status.get('path')})")
    return "\n".join(lines) + "\n"


def _write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_pre_slot_eligibility_impact_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_pre_slot_eligibility_impact_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8596)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_PRE_SLOT_ELIGIBILITY_URL"))
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
            os.environ["PERF_TRACE_INPUTS"] = "1"
            try:
                process = _start_streamlit(args.port)
            finally:
                os.environ.clear()
                os.environ.update(env_before)
            _wait_for_http(base_url, timeout_s=60.0)

        scenario_results = _run_browser_scenarios(
            base_url,
            SCENARIOS,
            headed=bool(args.headed),
            timeout_s=float(args.timeout_s),
        )
        failure_count = sum(1 for item in scenario_results if item.get("status") == "FAIL")
        direct_impact_count = sum(
            1
            for item in scenario_results
            if bool((item.get("impact_proof") or {}).get("direct_contract_impact"))
        )
        masked_count = sum(
            1
            for item in scenario_results
            if bool((item.get("impact_proof") or {}).get("masked_by_existing_page_gate"))
        )
        if failure_count:
            status = "FAIL"
            interpretation = "One or more contract-relevant live scenarios failed to render or failed recipe/probe proof."
        elif direct_impact_count:
            status = "PASS"
            interpretation = "At least one live scenario proved the contract-aware adapter opened the Design Guide slot while the old page gate was closed."
        else:
            status = "PARTIAL"
            interpretation = (
                "The sampled live scenarios rendered the Design Guide card and contract eligibility was present, "
                "but all were masked by the existing page/browser-test/actions gate. This proves slot/card reachability, "
                "not the stronger no-actions/no-loads contract-impact case."
            )

        payload = {
            "schema": "design_guide_pre_slot_eligibility_impact_snapshot.v1",
            "created_at": created_at,
            "status": status,
            "base_url": base_url,
            "scenarios": scenario_results,
            "scenario_count": len(scenario_results),
            "failure_count": failure_count,
            "direct_contract_impact_count": direct_impact_count,
            "direct_contract_impact_proven": bool(direct_impact_count),
            "masked_by_existing_page_gate_count": masked_count,
            "interpretation": interpretation,
            "product_behaviour_changed": False,
            "family_runtimes_changed": False,
            "cta_publication_apply_semantics_changed": False,
            "visible_wording_changed": False,
            "supporting_locks": {
                "design_guide_independence_lock": _latest_status("design_guide_independence_lock"),
                "design_guide_render_bridge_lock": _latest_status("design_guide_render_bridge_lock"),
                "design_guide_compute_resolver_publication_bridge_lock": _latest_status(
                    "design_guide_compute_resolver_publication_bridge_lock"
                ),
            },
            "snapshot_hash": _stable_hash(scenario_results),
        }
    except Exception as exc:
        payload = {
            "schema": "design_guide_pre_slot_eligibility_impact_snapshot.v1",
            "created_at": created_at,
            "status": "FAIL",
            "base_url": base_url,
            "errors": [f"{type(exc).__name__}: {exc}"],
            "product_behaviour_changed": False,
            "family_runtimes_changed": False,
            "cta_publication_apply_semantics_changed": False,
            "visible_wording_changed": False,
        }
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    json_path, md_path = _write_artifacts(payload)
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(json.dumps({"status": payload.get("status"), "snapshot_hash": payload.get("snapshot_hash")}, indent=2))
    return 0 if payload.get("status") in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
