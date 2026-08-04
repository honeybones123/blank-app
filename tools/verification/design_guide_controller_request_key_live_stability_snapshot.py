"""Browser/live DesignGuideController request-key stability snapshot.

Proof-only. Samples live Browser state to prove stable no-input reruns produce
the same DesignGuideController request_hash/publication_hash/controller_hash,
and changed inputs produce a different request_hash before any memo/cache
implementation is allowed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_helpers import _load_browser_state  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import _start_streamlit  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
DEFAULT_PORT = 8589
DEFAULT_RECIPE = "R2A_M0_V400"
DEFAULT_CHANGED_RECIPE = "R2B_M0_V600"

REQUIRED_LOCKS = {
    "memo_readiness": "design_guide_final_publication_rebuild_memo_readiness",
    "cta_apply_binding_bypass_live_impact": "design_guide_cta_apply_binding_bypass_live_impact",
    "design_guide_independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": (
        "design_guide_compute_resolver_publication_bridge_lock"
    ),
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = artifacts[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "snapshot": {}, "passed": False, "error": str(exc)}
    return {
        "found": True,
        "path": str(path),
        "snapshot": snapshot,
        "passed": snapshot.get("status") == "PASS",
    }


def _wait_for_live_url(url: str, *, timeout_s: float = 45.0) -> None:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}/"
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urlopen(base) as response:  # noqa: S310 - local verifier only
                if 200 <= int(response.status) < 500:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(0.35)
    raise RuntimeError(f"Timed out waiting for live app at {base}: {last_error}")


def _query(base_url: str, params: dict[str, Any]) -> str:
    pairs = {key: value for key, value in params.items() if value is not None}
    return f"{base_url.rstrip('/')}/?{urlencode(pairs)}"


def _extract_controller_request_key_state(state: dict[str, Any]) -> dict[str, Any]:
    probe = dict(state.get("design_guide_probe") or {})
    debug = dict(probe.get("debug_bundle") or {})
    publication = dict(debug.get("final_publication_verifier_payload") or {})
    parity = dict(debug.get("design_guide_controller_trace_only_parity") or {})
    button_contract = dict(
        probe.get("displayed_primary_button_contract")
        or probe.get("primary_button_contract")
        or probe.get("button_contract")
        or debug.get("displayed_primary_button_contract")
        or debug.get("primary_button_contract")
        or debug.get("button_contract")
        or {}
    )
    apply_payload = dict(
        state.get("design_guide_primary_apply_payload")
        or probe.get("design_guide_primary_apply_payload")
        or debug.get("design_guide_primary_apply_payload")
        or {}
    )
    request_hash = (
        parity.get("controller_request_hash")
        or debug.get("design_guide_controller_trace_only_request_hash")
        or debug.get("design_guide_controller_publication_authority_request_hash")
        or debug.get("design_guide_controller_collapsed_replacement_request_hash")
    )
    request_source = (
        parity.get("controller_request_source")
        or debug.get("design_guide_controller_trace_only_request_source")
        or debug.get("design_guide_controller_publication_authority_request_source")
        or debug.get("design_guide_controller_collapsed_replacement_request_source")
    )
    controller_hash = (
        parity.get("controller_hash")
        or debug.get("design_guide_controller_publication_authority_hash")
        or debug.get("design_guide_controller_collapsed_replacement_hash")
    )
    memo_cache_hit = (
        parity.get("controller_memo_cache_hit")
        if "controller_memo_cache_hit" in parity
        else debug.get("design_guide_controller_trace_only_memo_cache_hit")
    )
    if memo_cache_hit is None:
        memo_cache_hit = debug.get("design_guide_controller_publication_authority_memo_cache_hit")
    if memo_cache_hit is None:
        memo_cache_hit = debug.get("design_guide_controller_collapsed_replacement_memo_cache_hit")
    memo_cache_key = (
        parity.get("controller_memo_cache_key")
        or debug.get("design_guide_controller_trace_only_memo_cache_key")
        or debug.get("design_guide_controller_publication_authority_memo_cache_key")
        or debug.get("design_guide_controller_collapsed_replacement_memo_cache_key")
    )
    memo_cache_reason = (
        parity.get("controller_memo_cache_reason")
        or debug.get("design_guide_controller_trace_only_memo_cache_reason")
        or debug.get("design_guide_controller_publication_authority_memo_cache_reason")
        or debug.get("design_guide_controller_collapsed_replacement_memo_cache_reason")
    )
    memo_key_section_hashes = (
        parity.get("controller_memo_key_section_hashes")
        or debug.get("design_guide_controller_trace_only_memo_key_section_hashes")
        or debug.get("design_guide_controller_publication_authority_memo_key_section_hashes")
        or {}
    )
    publication_hash = (
        parity.get("controller_publication_hash")
        or parity.get("live_publication_hash")
        or publication.get("publication_hash")
        or debug.get("publication_hash")
        or debug.get("final_publication_publication_hash")
    )
    cta_hash = (
        parity.get("controller_cta_hash")
        or publication.get("final_publication_cta_hash")
        or debug.get("final_publication_cta_hash")
        or button_contract.get("final_publication_cta_hash")
    )
    display_hash = (
        parity.get("controller_display_hash")
        or publication.get("final_publication_display_hash")
        or debug.get("final_publication_display_hash")
    )
    return {
        "has_browser_state": bool(state),
        "guidance_branch": probe.get("guidance_branch") or debug.get("guidance_branch"),
        "primary_card_title": probe.get("primary_card_title") or debug.get("primary_card_title"),
        "controller_request_hash": request_hash,
        "controller_request_source": request_source,
        "controller_hash": controller_hash,
        "controller_memo_cache_hit": bool(memo_cache_hit),
        "controller_memo_cache_key": memo_cache_key,
        "controller_memo_cache_reason": memo_cache_reason,
        "controller_memo_key_section_hashes": dict(memo_key_section_hashes)
        if isinstance(memo_key_section_hashes, dict)
        else {},
        "publication_hash": publication_hash,
        "selected_family_id": (
            parity.get("selected_family")
            or publication.get("selected_family")
            or debug.get("selected_family_id")
            or probe.get("selected_family_id")
        ),
        "outcome_state": parity.get("outcome_state") or publication.get("outcome_state"),
        "final_publication_cta_hash": cta_hash,
        "final_publication_display_hash": display_hash,
        "apply_payload_hash": _stable_hash(apply_payload) if apply_payload else None,
        "apply_payload_exists": bool(apply_payload),
        "button_contract_hash": _stable_hash(button_contract) if button_contract else None,
        "button_contract_enabled": bool(button_contract.get("enabled") or button_contract.get("actionable")),
        "state_fingerprint": (
            apply_payload.get("state_fingerprint")
            or debug.get("state_fingerprint")
            or probe.get("state_fingerprint")
        ),
        "parity_pass": parity.get("parity_pass"),
        "trace_only_live_wired": bool(debug.get("design_guide_controller_trace_only_live_wired")),
    }


def _capture_samples(page, *, samples: int, interval_ms: int, timeout_s: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(max(1, samples)):
        page.wait_for_timeout(max(0, interval_ms))
        try:
            state = dict(_load_browser_state(page, timeout_s=min(3.0, max(0.5, timeout_s))))
            state_error = None
        except Exception as exc:
            state = {}
            state_error = f"{type(exc).__name__}: {exc}"
        extracted = _extract_controller_request_key_state(state)
        body_signals = dict(
            page.evaluate(
                r"""
                () => {
                  const text = String(document.body && document.body.innerText || "");
                  return {
                    hasDesignGuide: /Design Guide/i.test(text),
                    hasCheckingGuidance: /Checking design guidance/i.test(text),
                    hasApplyButton: /Run one-click auto design|Apply/i.test(text)
                  };
                }
                """
            )
            or {}
        )
        rows.append(
            {
                "sample_index": index + 1,
                "state_error": state_error,
                "controller": extracted,
                "body_signals": body_signals,
            }
        )
    return rows


def _sample_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    request_hashes = [row["controller"].get("controller_request_hash") for row in rows]
    publication_hashes = [row["controller"].get("publication_hash") for row in rows]
    controller_hashes = [row["controller"].get("controller_hash") for row in rows]
    live_rows = [row for row in rows if row["controller"].get("controller_request_hash")]
    latest = rows[-1]["controller"] if rows else {}
    return {
        "samples": rows,
        "latest": latest,
        "request_hashes": request_hashes,
        "publication_hashes": publication_hashes,
        "controller_hashes": controller_hashes,
        "has_request_hash": bool(latest.get("controller_request_hash")),
        "stable_request_hash": bool(
            request_hashes and request_hashes[-1] and len(set(item for item in request_hashes if item)) == 1
        ),
        "stable_publication_hash": bool(
            publication_hashes
            and publication_hashes[-1]
            and len(set(item for item in publication_hashes if item)) == 1
        ),
        "stable_controller_hash": bool(
            controller_hashes
            and controller_hashes[-1]
            and len(set(item for item in controller_hashes if item)) == 1
        ),
        "memo_cache_hits": sum(
            1 for row in rows if bool(row["controller"].get("controller_memo_cache_hit"))
        ),
        "live_sample_count": len(live_rows),
    }


def _browser_capture(
    base_url: str,
    *,
    recipe: str,
    changed_recipe: str,
    samples: int,
    interval_ms: int,
    timeout_s: float,
) -> dict[str, Any]:
    stable_url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
    changed_url = _query(base_url, {"page": "inputs", "browser_recipe": changed_recipe})
    _wait_for_live_url(stable_url, timeout_s=timeout_s)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1610, "height": 900})
        page.goto(stable_url, wait_until="domcontentloaded", timeout=int(timeout_s * 1000))
        stable_warmup_rows = _capture_samples(page, samples=samples, interval_ms=interval_ms, timeout_s=timeout_s)
        page.goto(stable_url, wait_until="domcontentloaded", timeout=int(timeout_s * 1000))
        stable_initial_rows = _capture_samples(page, samples=samples, interval_ms=interval_ms, timeout_s=timeout_s)
        page.goto(stable_url, wait_until="domcontentloaded", timeout=int(timeout_s * 1000))
        stable_rerun_rows = _capture_samples(page, samples=samples, interval_ms=interval_ms, timeout_s=timeout_s)
        page.goto(changed_url, wait_until="domcontentloaded", timeout=int(timeout_s * 1000))
        changed_rows = _capture_samples(page, samples=samples, interval_ms=interval_ms, timeout_s=timeout_s)
        browser.close()
    stable_warmup = _sample_summary(stable_warmup_rows)
    stable_initial = _sample_summary(stable_initial_rows)
    stable_rerun = _sample_summary(stable_rerun_rows)
    stable = _sample_summary(stable_initial_rows + stable_rerun_rows)
    changed = _sample_summary(changed_rows)
    stable_hash = stable.get("latest", {}).get("controller_request_hash")
    changed_hash = changed.get("latest", {}).get("controller_request_hash")
    return {
        "stable_url": stable_url,
        "changed_url": changed_url,
        "stable_warmup": stable_warmup,
        "stable_initial": stable_initial,
        "stable_rerun": stable_rerun,
        "stable": stable,
        "changed": changed,
        "changed_input_request_hash_differs": bool(stable_hash and changed_hash and stable_hash != changed_hash),
    }


def _guard_scenarios(live_hash: str | None) -> list[dict[str, Any]]:
    rows = [
        ("stable_no_input_rerun", live_hash, live_hash, False, False, False, True),
        ("changed_input_rerun", f"{live_hash or 'hash'}-changed", live_hash, False, False, False, False),
        ("missing_publication_state", None, live_hash, False, False, False, False),
        ("debug_mode", live_hash, live_hash, True, False, False, False),
        ("post_click_apply_in_flight", live_hash, live_hash, False, True, False, False),
    ]
    out: list[dict[str, Any]] = []
    for scenario_id, current_hash, previous_hash, debug_mode, apply_in_flight, missing_state, expected_memo_ready in rows:
        memo_ready = bool(
            current_hash
            and previous_hash
            and current_hash == previous_hash
            and not debug_mode
            and not apply_in_flight
            and not missing_state
        )
        out.append(
            {
                "scenario_id": scenario_id,
                "current_request_hash": current_hash,
                "previous_request_hash": previous_hash,
                "debug_mode": debug_mode,
                "post_click_or_apply_in_flight": apply_in_flight,
                "missing_publication_state": missing_state or not bool(current_hash),
                "memo_ready": memo_ready,
                "expected_memo_ready": expected_memo_ready,
                "expected_met": memo_ready is expected_memo_ready,
                "rebuild_required": not memo_ready,
            }
        )
    return out


def _source_checks() -> dict[str, bool]:
    input_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8", errors="replace")
    return {
        "controller_response_exposes_request_hash": all(
            token in controller_source
            for token in (
                "request_hash: str",
                "request_source: str",
                "request_hash=request_hash",
                "controller_request_hash",
            )
        ),
        "inputs_stamps_request_hash": all(
            token in input_source
            for token in (
                "design_guide_controller_trace_only_request_hash",
                "design_guide_controller_publication_authority_request_hash",
                "collapsed_guidance_replacement_controller_request_hash",
            )
        ),
        "memo_cache_implemented_and_diagnosed": (
            "_final_publication_memo_cache" in controller_source
            and "stable_design_guide_controller_request_hash" in controller_source
            and "_memo_key_payload" in controller_source
            and "_MEMO_DEBUG_PRODUCT_KEYS" in controller_source
            and "request_hash_unchanged" in controller_source
            and "design_guide_controller_trace_only_memo_cache_hit" in input_source
        ),
        "final_publication_no_page_imports": "inputs_page" not in final_source and "streamlit" not in final_source,
        "apply_routing_still_page_owned": (
            "_consume_design_guide_component_cta_value" in input_source
            and "_consume_design_guide_component_cta_value" not in final_source
        ),
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = payload["generated_at"].replace(":", "-")
    payload["snapshot_hash"] = _stable_hash(
        {
            "browser_live": {
                "stable_latest": payload["browser_live"]["stable"]["latest"],
                "stable_rerun_latest": payload["browser_live"]["stable_rerun"]["latest"],
                "changed_latest": payload["browser_live"]["changed"]["latest"],
                "changed_input_request_hash_differs": payload["browser_live"][
                    "changed_input_request_hash_differs"
                ],
            },
            "guard_scenarios": payload["guard_scenarios"],
            "source_checks": payload["source_checks"],
        }
    )
    json_path = ARTIFACT_DIR / f"design_guide_controller_request_key_live_stability_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_controller_request_key_live_stability_{stamp}.md"
    stable = payload["browser_live"]["stable"]
    changed = payload["browser_live"]["changed"]
    lines = [
        "# DesignGuideController Request-Key Live Stability Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Browser/Live Summary",
        "",
        f"- Stable URL: `{payload['browser_live']['stable_url']}`",
        f"- Changed URL: `{payload['browser_live']['changed_url']}`",
        f"- Stable request hash: `{stable['latest'].get('controller_request_hash')}`",
        f"- Stable publication hash: `{stable['latest'].get('publication_hash')}`",
        f"- Stable controller hash: `{stable['latest'].get('controller_hash')}`",
        f"- Stable rerun memo hits: `{payload['browser_live']['stable_rerun'].get('memo_cache_hits')}`",
        f"- Changed request hash: `{changed['latest'].get('controller_request_hash')}`",
        f"- Changed input request hash differs: `{payload['browser_live']['changed_input_request_hash_differs']}`",
        "",
        "## Guard Scenarios",
        "",
        "| Scenario | Memo ready | Rebuild required | Expected met |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["guard_scenarios"]:
        lines.append(
            "| `{scenario}` | `{ready}` | `{rebuild}` | `{expected}` |".format(
                scenario=_escape_md(row["scenario_id"]),
                ready=row["memo_ready"],
                rebuild=row["rebuild_required"],
                expected=row["expected_met"],
            )
        )
    lines.extend(["", "## Source Checks", "", "| Check | PASS |", "| --- | --- |"])
    for key, value in payload["source_checks"].items():
        lines.append(f"| `{_escape_md(key)}` | `{value}` |")
    lines.extend(["", "## Locks", ""])
    for name, lock in payload["locks"].items():
        lines.append(f"- `{name}`: passed=`{lock['passed']}`, path=`{lock['path']}`")
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Recommendation", "", payload["recommended_next_slice"]])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=None)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--changed-recipe", default=DEFAULT_CHANGED_RECIPE)
    parser.add_argument("--samples", type=int, default=6)
    parser.add_argument("--interval-ms", type=int, default=1200)
    parser.add_argument("--timeout-s", type=float, default=90.0)
    parser.add_argument("--no-start-server", action="store_true")
    args = parser.parse_args()

    server: subprocess.Popen | None = None
    base_url = args.url or f"http://localhost:{args.port}"
    if not args.url and not args.no_start_server:
        server = _start_streamlit(args.port)
        time.sleep(1.0)

    try:
        browser_live = _browser_capture(
            base_url,
            recipe=args.recipe,
            changed_recipe=args.changed_recipe,
            samples=args.samples,
            interval_ms=args.interval_ms,
            timeout_s=args.timeout_s,
        )
        locks = {name: _latest(prefix) for name, prefix in REQUIRED_LOCKS.items()}
        source_checks = _source_checks()
        live_hash = browser_live["stable"]["latest"].get("controller_request_hash")
        guard_scenarios = _guard_scenarios(live_hash)

        failures: list[str] = []
        for name, lock in locks.items():
            if lock.get("passed") is not True:
                failures.append(f"{name}_not_passed")
        for key, value in source_checks.items():
            if value is not True:
                failures.append(f"source_check_failed::{key}")
        stable = browser_live["stable"]
        if stable.get("has_request_hash") is not True:
            failures.append("stable_live_request_hash_missing")
        if stable.get("stable_request_hash") is not True:
            failures.append("stable_live_request_hash_not_stable")
        if stable.get("stable_publication_hash") is not True:
            failures.append("stable_live_publication_hash_not_stable")
        if stable.get("stable_controller_hash") is not True:
            failures.append("stable_live_controller_hash_not_stable")
        if int(browser_live["stable_rerun"].get("memo_cache_hits") or 0) <= 0:
            failures.append("stable_live_memo_cache_hit_missing")
        if browser_live.get("changed_input_request_hash_differs") is not True:
            failures.append("changed_input_request_hash_did_not_change")
        for row in guard_scenarios:
            if row["expected_met"] is not True:
                failures.append(f"{row['scenario_id']}_unexpected_guard_decision")

        passed = not failures
        payload = {
            "schema": "design_guide_controller_request_key_live_stability_snapshot.v1",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "status": "PASS" if passed else "FAIL",
            "failures": failures,
            "product_behavior_changed": False,
            "browser_live": browser_live,
            "guard_scenarios": guard_scenarios,
            "source_checks": source_checks,
            "locks": {
                name: {"path": lock.get("path"), "passed": lock.get("passed"), "found": lock.get("found")}
                for name, lock in locks.items()
            },
            "ready_for_memo_implementation": passed,
            "recommended_next_slice": (
                "Implement guarded FinalDesignGuidePublication memoization inside DesignGuideController, "
                "keyed by request_hash, with debug/missing/post-click/changed-request states rebuilding."
            ),
        }
        json_path, md_path = _write(payload)
        print(f"design_guide_controller_request_key_live_stability_snapshot {payload['status']}")
        print(f"ready_for_memo_implementation={payload['ready_for_memo_implementation']}")
        print(f"json={json_path}")
        print(f"report={md_path}")
        if failures:
            print("failures:", json.dumps(failures, sort_keys=True))
        return 0 if passed else 1
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
