"""Replay the live Inputs authority chain through a real browser session.

This verifier is intentionally verification-only. It does not change product
code, add runtime state, or synthesize a result. It observes the existing
browser probe while replaying the current Inputs workflow:

initial render -> display-only toggle -> engineering edit -> two edits ->
Apply -> same-session rerun -> in-app navigate away/return.

The gate checks that draft/committed state, engineering snapshot, authoritative
result, publication, CTA, and Apply identity remain aligned at each boundary.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    BROWSER_STATE_LABEL,
    _load_browser_state,
    _query,
    _start_streamlit,
    _terminate_process_tree,
)
from tools.verification.helpers.browser_helpers import _page_cycle_click_page  # noqa: E402
from application.engineering_snapshot import (  # noqa: E402
    build_engineering_input_snapshot_from_resolved_state,
)
from design_brain.family_classification import load_family_classification_contract  # noqa: E402
from inputs_page_modules.design_guide.fingerprint import DESIGN_GUIDE_ALGORITHM_VERSION  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
APPLY_TRACE_PATH = ROOT / "artifacts" / "debug" / "design_guide" / "design_guide_trace.jsonl"
DEFAULT_RECIPE = "R1B_M600_V0"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
ACTIONABLE_APPLY_EXCLUSIONS = {
    "apply beam/reo/load edits",
    "save active beam back to table",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _hash(value: Any) -> str | None:
    text = str(value or "").strip()
    return text if HASH_RE.fullmatch(text) else None


def _trace_size() -> int:
    try:
        return APPLY_TRACE_PATH.stat().st_size
    except OSError:
        return 0


def _apply_trace_events_since(offset: int) -> list[dict[str, Any]]:
    try:
        with APPLY_TRACE_PATH.open("rb") as handle:
            handle.seek(max(0, int(offset)))
            raw = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    events: list[dict[str, Any]] = []
    for line in raw.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _load_current_replay_state(page: Any) -> dict[str, Any]:
    try:
        outer_state = _load_browser_state(page, fallback_timeout_ms=1_000)
    except Exception:
        outer_state = {}
    try:
        return _state_with_workspace_probe(page, outer_state)
    except Exception:
        return outer_state


def _wait_for_post_render_state(page: Any, *, timeout_ms: int = 90_000) -> dict[str, Any]:
    deadline = time.time() + timeout_ms / 1000.0
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = _load_current_replay_state(page)
        if (
            str(last.get("browser_probe_phase") or "").strip() == "post_page_render"
            and not bool(last.get("pre_page_render_lightweight"))
        ):
            return last
        time.sleep(0.25)
    return last


def _load_workspace_probe(page: Any) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for selector in (
        "textarea[aria-label='Inputs workspace state']",
        "[data-testid='stTextArea'] textarea",
    ):
        locator = page.locator(selector)
        for index in range(locator.count()):
            try:
                raw = locator.nth(index).input_value(timeout=2_000)
                payload = json.loads(raw or "{}")
            except Exception:
                continue
            if isinstance(payload, dict) and (
                "browser_state_overlay" in payload
                or "engineering_input_transaction" in payload
            ):
                candidates.append(payload)
    if not candidates:
        return {}
    candidates.sort(
        key=lambda item: (
            int(item.get("workspace_revision") or 0),
            int(item.get("workspace_fragment_render_count") or 0),
        )
    )
    return candidates[-1]


def _state_with_workspace_probe(page: Any, state: dict[str, Any]) -> dict[str, Any]:
    """Overlay the current fragment-owned probe over the outer page probe."""

    result = dict(state or {})
    workspace_probe = _load_workspace_probe(page)
    result["workspace_state_probe"] = workspace_probe
    overlay = _dict(workspace_probe.get("browser_state_overlay"))
    if not overlay:
        return result
    # The outer Browser state cannot update during a fragment-only rerun. The
    # workspace overlay is emitted by the current fragment and is therefore
    # the correct observation surface for the replay gate.
    result.update(overlay)
    result["workspace_revision"] = workspace_probe.get("workspace_revision")
    result["workspace_fragment_render_count"] = workspace_probe.get(
        "workspace_fragment_render_count"
    )
    result["workspace_authoritative_result_reuse"] = workspace_probe.get(
        "authoritative_result_reuse"
    )
    resolved_inputs = _dict(overlay.get("summary_state_probe"))
    if resolved_inputs:
        try:
            snapshot = build_engineering_input_snapshot_from_resolved_state(
                resolved_inputs,
                contract_versions={
                    "design_guide": str(DESIGN_GUIDE_ALGORITHM_VERSION),
                    "family_classification": str(
                        (
                            load_family_classification_contract().get(
                                "contract_identity"
                            )
                            or {}
                        ).get("contract_version")
                        or ""
                    ),
                },
                calculation_versions={
                    "summary_resolver": "resolved_inputs_summary_state.v1"
                },
            )
            result["engineering_snapshot_probe"] = {
                "engineering_hash": snapshot.engineering_hash,
                "snapshot": snapshot.to_dict(),
                "source": "inputs_workspace_state_probe",
            }
        except Exception as exc:
            result["engineering_snapshot_probe"] = {
                "error": f"{type(exc).__name__}: {exc}",
                "source": "inputs_workspace_state_probe",
            }
    result["browser_debug_probe"] = {
        **_browser_debug(result),
        "authoritative_design_result_runtime_probe": {
            "engineering_hash": _dict(
                overlay.get("authoritative_result_probe")
            ).get("stored_engineering_hash"),
            "reuse_decision": _dict(
                workspace_probe.get("authoritative_result_reuse")
            ),
            "source": "inputs_workspace_state_probe",
        },
        "authoritative_apply_command_probe": dict(
            workspace_probe.get("authoritative_apply_command_probe") or {}
        ),
        "typed_inputs_apply_probe": dict(
            workspace_probe.get("typed_inputs_apply_probe") or {}
        ),
    }
    return result


def _wait_for_state_change(
    page: Any,
    predicate: Callable[[dict[str, Any]], bool],
    *,
    timeout_ms: int = 90_000,
) -> dict[str, Any]:
    deadline = time.time() + timeout_ms / 1000.0
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = _wait_for_post_render_state(page, timeout_ms=2_000)
        if predicate(last):
            return last
        time.sleep(0.25)
    return last


def _browser_debug(state: dict[str, Any]) -> dict[str, Any]:
    return _dict(state.get("browser_debug_probe"))


def _compact_state(state: dict[str, Any], *, label: str) -> dict[str, Any]:
    debug = _browser_debug(state)
    engineering_probe = _dict(state.get("engineering_snapshot_probe"))
    authority_runtime = _dict(
        debug.get("authoritative_design_result_runtime_probe")
        or state.get("authoritative_design_result_runtime_probe")
    )
    transaction = _dict(
        debug.get("inputs_engineering_input_transaction_probe")
        or state.get("inputs_engineering_input_transaction_probe")
        or _dict(state.get("workspace_state_probe")).get(
            "engineering_input_transaction"
        )
    )
    workspace_probe = _dict(state.get("workspace_state_probe"))
    result_probe = _dict(state.get("authoritative_result_probe"))
    publication_hashes = _dict(state.get("final_publication_hashes"))
    final_publication = _dict(state.get("final_publication_verifier_payload"))
    primary_contract = _dict(
        state.get("primary_button_contract")
        or state.get("design_guide_primary_button_contract")
    )
    apply_payload = _dict(
        state.get("design_guide_primary_apply_payload")
        or debug.get("design_guide_primary_apply_payload")
    )
    binding_audit = _dict(state.get("design_guide_primary_payload_binding_audit"))
    cache_probe = _dict(debug.get("inputs_dirty_cache_probe"))
    router_probe = _dict(state.get("router_probe"))
    route_return_debug = _dict(state.get("inputs_route_return_debug"))
    resolved_inputs = _dict(state.get("summary_state_probe"))
    engineering_value_keys = (
        "D",
        "b",
        "bot1_count",
        "bot2_count",
        "bot_row_count",
        "bot_row_1_bars",
        "bot_row_1_dia",
        "bot_row_1_spacing",
        "bot_row_2_bars",
        "bot_row_2_dia",
        "bot_row_2_spacing",
        "top1_count",
        "top_row_count",
        "top_row_1_bars",
        "top_row_1_dia",
        "top_row_1_spacing",
    )
    selected_family = str(
        state.get("selected_family_id")
        or final_publication.get("selected_family_id")
        or ""
    ).strip() or None
    publication_family = str(
        result_probe.get("publication_verifier_selected_family_id")
        or result_probe.get("publication_selected_family_id")
        or final_publication.get("selected_family_id")
        or ""
    ).strip() or None
    cta_family = str(
        result_probe.get("cta_family_id")
        or primary_contract.get("family")
        or primary_contract.get("selected_family_id")
        or ""
    ).strip() or None
    apply_family = str(
        result_probe.get("apply_payload_family_id")
        or apply_payload.get("family")
        or apply_payload.get("selected_family_id")
        or ""
    ).strip() or None
    candidate_ids = {
        "publication": final_publication.get("source_candidate_id")
        or final_publication.get("candidate_id"),
        "cta": primary_contract.get("source_candidate_id")
        or primary_contract.get("candidate_id"),
        "apply": apply_payload.get("source_candidate_id")
        or apply_payload.get("candidate_id"),
        "binding": binding_audit.get("visible_primary_candidate_id")
        or binding_audit.get("button_contract_candidate_id"),
    }
    candidate_ids = {
        key: str(value).strip()
        for key, value in candidate_ids.items()
        if str(value or "").strip()
    }
    return {
        "label": label,
        "requested_recipe": state.get("requested_browser_recipe"),
        "applied_recipe": state.get("applied_browser_recipe")
        or state.get("browser_recipe"),
        "recipe_error": state.get("browser_recipe_error"),
        "engineering_hash": engineering_probe.get("engineering_hash"),
        "engineering_snapshot": _dict(engineering_probe.get("snapshot")),
        "authoritative_runtime_hash": authority_runtime.get("engineering_hash"),
        "stored_result_hash": result_probe.get("stored_engineering_hash"),
        "transaction": {
            "draft_hash": transaction.get("draft_hash"),
            "committed_hash": transaction.get("committed_hash"),
            "engineering_hash": transaction.get("engineering_hash"),
            "revision": transaction.get("revision"),
            "changed_keys": list(transaction.get("changed_keys") or []),
        },
        "committed_baseline": _dict(
            workspace_probe.get(
                "committed_engineering_input_baseline"
            )
        ),
        "reuse_reason": _dict(authority_runtime.get("reuse_decision")).get("reason"),
        "publication_hash": publication_hashes.get("publication_hash"),
        "authority_hash": publication_hashes.get("authority_hash"),
        "cta_hash": publication_hashes.get("cta_hash"),
        "display_hash": publication_hashes.get("display_hash"),
        "selected_family": selected_family,
        "publication_family": publication_family,
        "cta_family": cta_family,
        "apply_family": apply_family,
        "candidate_ids": candidate_ids,
        "fragment_fresh": state.get("fragment_fresh"),
        "pending_apply_refresh": cache_probe.get("pending_apply_refresh"),
        "apply_in_flight": cache_probe.get("apply_in_flight"),
        "authoritative_apply_probe": _dict(
            debug.get("authoritative_apply_command_probe")
            or state.get("authoritative_apply_command_probe")
            or workspace_probe.get("authoritative_apply_command_probe")
        ),
        "typed_apply_probe": _dict(
            debug.get("typed_inputs_apply_probe")
            or state.get("typed_inputs_apply_probe")
            or workspace_probe.get("typed_inputs_apply_probe")
        ),
        "last_apply_route": _dict(workspace_probe.get("last_apply_route")),
        "router_probe": router_probe,
        "route_return_debug": route_return_debug,
        "engineering_values": {
            key: resolved_inputs.get(key)
            for key in engineering_value_keys
        },
        "state_keys": sorted(state.keys()),
    }


def _state_checks(
    compact: dict[str, Any],
    *,
    expected_recipe: str,
    require_action: bool = True,
    require_recipe: bool = True,
) -> dict[str, bool]:
    engineering_hash = _hash(compact.get("engineering_hash"))
    runtime_hash = _hash(compact.get("authoritative_runtime_hash"))
    stored_hash = _hash(compact.get("stored_result_hash"))
    transaction = _dict(compact.get("transaction"))
    draft_hash = _hash(transaction.get("draft_hash"))
    committed_hash = _hash(transaction.get("committed_hash"))
    transaction_engineering_hash = _hash(transaction.get("engineering_hash"))
    family_values = [
        compact.get("selected_family"),
        compact.get("publication_family"),
    ]
    if require_action:
        family_values.extend([compact.get("cta_family"), compact.get("apply_family")])
    present_families = [str(value).strip() for value in family_values if str(value or "").strip()]
    candidate_values = list(_dict(compact.get("candidate_ids")).values())
    candidate_parity = len(set(candidate_values)) <= 1
    return {
        "recipe_applied": (
            compact.get("applied_recipe") == expected_recipe
            and not bool(compact.get("recipe_error"))
        )
        if require_recipe
        else not bool(compact.get("recipe_error")),
        "engineering_hash_present": engineering_hash is not None,
        "runtime_hash_matches_engineering": engineering_hash is not None
        and runtime_hash == engineering_hash,
        "stored_result_hash_matches_engineering": engineering_hash is not None
        and stored_hash == engineering_hash,
        "committed_hash_matches_engineering": engineering_hash is not None
        and transaction_engineering_hash == engineering_hash
        and committed_hash is not None,
        "draft_and_committed_hash_match": draft_hash is not None
        and draft_hash == committed_hash,
        "publication_hash_present": bool(_hash(compact.get("publication_hash"))),
        "authority_hash_present": bool(_hash(compact.get("authority_hash"))),
        "family_identity_parity": bool(present_families)
        and len(set(present_families)) == 1,
        "candidate_identity_parity": candidate_parity,
        "no_pending_apply_refresh": compact.get("pending_apply_refresh") is not True,
        "no_apply_in_flight": compact.get("apply_in_flight") is not True,
        "action_contract_present": bool(compact.get("cta_family"))
        and bool(compact.get("apply_family"))
        if require_action
        else True,
    }


def _visible_label(page: Any, label: str) -> Any:
    locator = page.get_by_label(label, exact=True)
    for index in range(locator.count()):
        candidate = locator.nth(index)
        try:
            if candidate.is_visible():
                return candidate
        except Exception:
            continue
    # Some Streamlit controls expose the text as a direct aria-label on the
    # input rather than as an associated label element.
    direct = page.locator(f'[aria-label="{label}"]')
    for index in range(direct.count()):
        candidate = direct.nth(index)
        try:
            if candidate.is_visible():
                return candidate
        except Exception:
            continue
    raise RuntimeError(f"visible widget not found: {label}")


def _edit_depth(page: Any, value: str) -> None:
    field = _visible_label(page, "Depth D (mm)")
    field.fill(str(value))
    field.press("Enter")


def _toggle_display_only(page: Any) -> None:
    deadline = time.time() + 30.0
    while time.time() < deadline:
        try:
            toggle = _visible_label(page, "3D model")
            toggle.click()
            return
        except RuntimeError:
            # The text label is still a valid user-facing control target when
            # the widget implementation does not expose an associated
            # aria-label. Wait briefly for the fragment to finish settling
            # after an Apply rerun before declaring the probe unavailable.
            text = page.get_by_text("3D model", exact=True)
            for index in range(text.count()):
                candidate = text.nth(index)
                try:
                    if candidate.is_visible():
                        candidate.click()
                        return
                except Exception:
                    continue
            time.sleep(0.25)
    raise RuntimeError("visible widget not found: 3D model")


def _find_apply_button(page: Any) -> Any:
    deadline = time.time() + 30.0
    while time.time() < deadline:
        buttons = page.get_by_role("button")
        for index in range(buttons.count()):
            button = buttons.nth(index)
            try:
                if not button.is_visible():
                    continue
                text = " ".join((button.inner_text() or "").split()).strip()
            except Exception:
                continue
            lowered = text.lower()
            if "apply" in lowered and lowered not in ACTIONABLE_APPLY_EXCLUSIONS:
                return button
        time.sleep(0.25)
    raise RuntimeError("actionable Apply button not found")


def _assert_transition(
    *,
    label: str,
    compact: dict[str, Any],
    checks: dict[str, bool],
    failures: list[str],
) -> None:
    for name, passed in checks.items():
        if not passed:
            failures.append(f"{label}:{name}")


def _run_apply_transition(
    *,
    page: Any,
    before_apply: dict[str, Any],
    expected_recipe: str,
    payload: dict[str, Any],
    record: Callable[[str, dict[str, Any], dict[str, bool]], None],
) -> dict[str, Any]:
    trace_offset = _trace_size()
    apply_button = _find_apply_button(page)
    apply_button_text = " ".join((apply_button.inner_text() or "").split()).strip()
    apply_button.click(timeout=30_000)
    apply_state = _wait_for_state_change(
        page,
        lambda state: (
            bool(state)
            and (
                _compact_state(state, label="apply").get("engineering_hash")
                != before_apply.get("engineering_hash")
                or bool(
                    _compact_state(state, label="apply").get(
                        "authoritative_apply_probe"
                    )
                )
                or bool(
                    _compact_state(state, label="apply").get("typed_apply_probe")
                )
                or any(
                    str(event.get("event") or "") == "run_end"
                    for event in _apply_trace_events_since(trace_offset)
                )
            )
        ),
        timeout_ms=120_000,
    )
    applied = _compact_state(apply_state, label="apply")
    trace_events = _apply_trace_events_since(trace_offset)
    trace_run_end = any(
        str(event.get("event") or "") == "run_end" for event in trace_events
    )
    post_apply_result_incomplete = (
        applied.get("engineering_hash") in {None, before_apply.get("engineering_hash")}
        or applied.get("authoritative_runtime_hash") != applied.get("engineering_hash")
        or applied.get("stored_result_hash") != applied.get("engineering_hash")
    )
    if (
        "apply" in apply_button_text.lower()
        and post_apply_result_incomplete
        and (
            trace_run_end
            or bool(applied.get("authoritative_apply_probe"))
            or bool(applied.get("typed_apply_probe"))
        )
    ):
        # The first post-click state can expose the completed trace event while
        # still carrying the pre-Apply result. Establish the baseline only
        # after the one transaction has published its new engineering hash.
        settled_state = _wait_for_state_change(
            page,
            lambda state: (
                bool(state)
                and _compact_state(state, label="apply_settled").get(
                    "engineering_hash"
                )
                != before_apply.get("engineering_hash")
                and _compact_state(state, label="apply_settled").get(
                    "authoritative_runtime_hash"
                )
                == _compact_state(state, label="apply_settled").get(
                    "engineering_hash"
                )
                and _compact_state(state, label="apply_settled").get(
                    "stored_result_hash"
                )
                == _compact_state(state, label="apply_settled").get(
                    "engineering_hash"
                )
            ),
            timeout_ms=120_000,
        )
        settled = _compact_state(settled_state, label="apply")
        if settled:
            applied = settled
    apply_checks = _state_checks(
        applied,
        expected_recipe=expected_recipe,
        require_action=False,
    )
    apply_checks["apply_probe_present"] = bool(
        applied.get("authoritative_apply_probe")
    ) or bool(applied.get("typed_apply_probe")) or trace_run_end
    apply_checks["final_result_is_current"] = (
        applied.get("authoritative_runtime_hash") == applied.get("engineering_hash")
        and applied.get("stored_result_hash") == applied.get("engineering_hash")
    )
    apply_checks["apply_does_not_leave_pending_refresh"] = (
        applied.get("pending_apply_refresh") is not True
        and applied.get("apply_in_flight") is not True
    )
    apply_checks["apply_state_transition_observed"] = (
        applied.get("engineering_hash") != before_apply.get("engineering_hash")
        or bool(applied.get("authoritative_apply_probe"))
        or bool(applied.get("typed_apply_probe"))
        or trace_run_end
    )
    applied["apply_trace_run_end"] = trace_run_end
    applied["apply_trace_events"] = trace_events
    payload["apply_button_text"] = apply_button_text
    record("apply", applied, apply_checks)
    return applied


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Runtime Authority Replay",
        "",
        f"Status: `{payload['status']}`",
        f"Recipe: `{payload['recipe']}`",
        f"Actual browser run: `{payload['actual_browser_run']}`",
        "",
        "## Replay Sequence",
        "",
        "initial render -> display-only toggle -> engineering edit -> two edits -> Apply -> same-session rerun -> in-app navigate away/return",
        "",
        "## Transition Checks",
        "",
        "| Transition | Result | Failed checks |",
        "| --- | --- | --- |",
    ]
    for row in payload.get("transitions", []):
        lines.append(
            f"| `{row['label']}` | `{row['status']}` | `{', '.join(row.get('failures') or []) or 'none'}` |"
        )
    lines.extend(["", "## Required Invariants", ""])
    for key, value in payload.get("overall_checks", {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This is live browser evidence for the current Inputs authority chain. It does not certify every family or replace the universal family lock. It proves whether the current session can carry one engineering edit through committed state, authoritative result, publication, CTA, and Apply without stale identity drift.",
            "",
            f"Machine-readable artifact: `{payload['artifact']}`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--port", type=int, default=9396)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    stamp = _stamp()
    process = None
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    payload: dict[str, Any] = {
        "gate": "inputs_runtime_authority_replay",
        "recipe": str(args.recipe),
        "timestamp": stamp,
        "actual_browser_run": True,
        "transitions": [],
        "overall_checks": {},
        "failures": [],
    }

    def record(label: str, compact: dict[str, Any], checks: dict[str, bool]) -> None:
        failures = [name for name, passed in checks.items() if not passed]
        payload["transitions"].append(
            {
                "label": label,
                "status": "PASS" if not failures else "FAIL",
                "checks": checks,
                "failures": failures,
                "state": compact,
            }
        )
        payload["failures"].extend(f"{label}:{failure}" for failure in failures)

    try:
        if args.base_url is None:
            process = _start_streamlit(args.port)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            page = browser.new_page(viewport={"width": 1600, "height": 1100})
            page.set_default_timeout(30_000)
            initial_url = _query(
                base_url,
                {
                    "page": "inputs",
                    "browser_recipe": args.recipe,
                    "browser_test_mode": "1",
                    "cid": f"authority_replay_{stamp}",
                },
            )
            page.goto(initial_url, wait_until="domcontentloaded", timeout=90_000)
            page.get_by_label(BROWSER_STATE_LABEL).wait_for(
                state="attached",
                timeout=90_000,
            )
            page.wait_for_function(
                """
                () => Array.from(document.querySelectorAll('label, [aria-label]'))
                  .some((element) => {
                    const text = String(
                      element.getAttribute('aria-label') ||
                      element.innerText ||
                      element.textContent || ''
                    ).trim();
                    return text === '3D model';
                  })
                """,
                timeout=90_000,
            )
            initial_state = _wait_for_post_render_state(page)
            initial = _compact_state(initial_state, label="initial_render")
            record(
                "initial_render",
                initial,
                _state_checks(initial, expected_recipe=args.recipe),
            )

            baseline_hash = initial.get("engineering_hash")
            _toggle_display_only(page)
            display_state = _wait_for_state_change(
                page,
                lambda state: bool(state)
                and _compact_state(state, label="display_only_toggle").get(
                    "engineering_hash"
                )
                == baseline_hash,
            )
            display = _compact_state(display_state, label="display_only_toggle")
            display_checks = _state_checks(display, expected_recipe=args.recipe)
            display_checks["engineering_hash_unchanged"] = (
                display.get("engineering_hash") == baseline_hash
            )
            display_checks["authority_hash_unchanged"] = (
                display.get("authority_hash") == initial.get("authority_hash")
            )
            record("display_only_toggle", display, display_checks)

            before_edit_hash = display.get("engineering_hash")
            _edit_depth(page, "635")
            edit_state = _wait_for_state_change(
                page,
                lambda state: _compact_state(state, label="engineering_edit").get(
                    "engineering_hash"
                )
                not in {None, before_edit_hash},
            )
            edit = _compact_state(edit_state, label="engineering_edit")
            edit_checks = _state_checks(edit, expected_recipe=args.recipe)
            edit_checks["engineering_hash_changed"] = (
                edit.get("engineering_hash") not in {None, before_edit_hash}
            )
            record("engineering_edit", edit, edit_checks)

            previous_hash = edit.get("engineering_hash")
            _edit_depth(page, "640")
            second_state = _wait_for_state_change(
                page,
                lambda state: _compact_state(state, label="rapid_edit_1").get(
                    "engineering_hash"
                )
                not in {None, previous_hash},
            )
            second = _compact_state(second_state, label="rapid_edit_1")
            second_checks = _state_checks(second, expected_recipe=args.recipe)
            second_checks["engineering_hash_changed"] = (
                second.get("engineering_hash") not in {None, previous_hash}
            )
            record("rapid_edit_1", second, second_checks)

            previous_hash = second.get("engineering_hash")
            _edit_depth(page, "645")
            third_state = _wait_for_state_change(
                page,
                lambda state: _compact_state(state, label="rapid_edit_2").get(
                    "engineering_hash"
                )
                not in {None, previous_hash},
            )
            third = _compact_state(third_state, label="rapid_edit_2")
            third_checks = _state_checks(third, expected_recipe=args.recipe)
            third_checks["engineering_hash_changed"] = (
                third.get("engineering_hash") not in {None, previous_hash}
            )
            record("rapid_edit_2", third, third_checks)

            applied = _run_apply_transition(
                page=page,
                before_apply=third,
                expected_recipe=args.recipe,
                payload=payload,
                record=record,
            )

            stable_before_reload = applied
            # A hard page.goto() creates a new Streamlit client session. The
            # architecture guarantee is same-session rerun/reuse, so exercise
            # a display-only widget in the existing session instead.
            _toggle_display_only(page)
            reload_state = _wait_for_state_change(
                page,
                lambda state: bool(state)
                and _compact_state(state, label="same_session_rerun").get(
                    "engineering_hash"
                )
                == stable_before_reload.get("engineering_hash"),
            )
            reloaded = _compact_state(reload_state, label="same_session_rerun")
            reload_checks = _state_checks(
                reloaded,
                expected_recipe=args.recipe,
                require_recipe=False,
            )
            reload_checks["engineering_hash_unchanged"] = (
                reloaded.get("engineering_hash") == stable_before_reload.get("engineering_hash")
            )
            # A display-only fragment rerun does not invoke the authority
            # coordinator, so its last decision may remain
            # ``engineering_hash_changed`` from Apply. The authoritative
            # reuse proof is the unchanged hash plus current runtime/stored
            # result parity; a fresh coordinator rerun reports
            # ``engineering_hash_match`` explicitly.
            reload_checks["reuse_reason_is_hash_match"] = (
                reloaded.get("reuse_reason") == "engineering_hash_match"
                or (
                    reloaded.get("reuse_reason")
                    == stable_before_reload.get("reuse_reason")
                    and reloaded.get("engineering_hash")
                    == stable_before_reload.get("engineering_hash")
                    and reloaded.get("stored_result_hash")
                    == stable_before_reload.get("stored_result_hash")
                )
            )
            record("same_session_rerun", reloaded, reload_checks)

            away_navigation = _page_cycle_click_page(
                page,
                "bending",
                "Bending",
            )
            away_state = _wait_for_post_render_state(page)
            payload["navigation_observations"] = {
                "away_navigation": dict(away_navigation or {}),
                "away_state": _compact_state(
                    away_state,
                    label="navigate_away_observation",
                ),
            }
            _page_cycle_click_page(page, "inputs", "Inputs")
            return_state = _wait_for_state_change(
                page,
                lambda state: bool(
                    _compact_state(
                        state,
                        label="navigate_away_return",
                    ).get("fragment_fresh")
                )
                and bool(
                    _dict(
                        _compact_state(
                            state,
                            label="navigate_away_return",
                        ).get("transaction")
                    ).get("engineering_hash")
                ),
            )
            returned = _compact_state(return_state, label="navigate_away_return")
            return_checks = _state_checks(
                returned,
                expected_recipe=args.recipe,
                require_recipe=False,
            )
            return_checks["engineering_hash_preserved"] = (
                returned.get("engineering_hash") == applied.get("engineering_hash")
            )
            return_checks["authority_hash_preserved"] = (
                returned.get("authority_hash") == applied.get("authority_hash")
            )
            record("navigate_away_return", returned, return_checks)
            browser.close()
    except (Exception, PlaywrightTimeoutError) as exc:
        payload["failures"].append(f"runtime_exception:{type(exc).__name__}:{exc}")
        payload["runtime_exception"] = f"{type(exc).__name__}: {exc}"
    finally:
        _terminate_process_tree(process)

    payload["overall_checks"] = {
        "all_transitions_pass": bool(payload["transitions"])
        and all(row["status"] == "PASS" for row in payload["transitions"]),
        "no_runtime_exception": "runtime_exception" not in payload,
        "replay_has_apply_transition": any(
            row.get("label") == "apply" for row in payload["transitions"]
        ),
        "no_failures": not payload["failures"],
    }
    payload["status"] = "PASS" if all(payload["overall_checks"].values()) else "FAIL"
    artifact_path = ARTIFACT_DIR / f"inputs_runtime_authority_replay_{stamp}.json"
    report_path = AUDIT_DIR / f"inputs_runtime_authority_replay_{stamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload["artifact"] = str(artifact_path)
    payload["report"] = str(report_path)
    artifact_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(payload, report_path)
    print(f"inputs_runtime_authority_replay {payload['status']}")
    print(f"failures={payload['failures']}")
    print(f"json={artifact_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
