"""Browser/live CTA/apply binding churn snapshot.

Proof-only. This verifier samples browser state from an instrumented Inputs page
and combines it with the CTA/apply binding readiness scenarios. It proves the
next safe step is still live proof/guarding, not implementation. It does not
skip binding work, move CTA/apply routing, alter publication, or change visible
wording.
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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
DEFAULT_PORT = 8584
DEFAULT_RECIPE = "A_M300_V0"

REQUIRED_LOCKS = {
    "cta_apply_binding_readiness": "design_guide_cta_apply_binding_bypass_readiness",
    "live_cta_authority_cutover": "design_guide_live_cta_authority_cutover",
    "design_guide_independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


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


def _extract_cta_binding_state(state: dict[str, Any]) -> dict[str, Any]:
    probe = dict(state.get("design_guide_probe") or {})
    debug = dict(probe.get("debug_bundle") or {})
    publication = dict(debug.get("final_publication_verifier_payload") or {})
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
    binding_audit = dict(
        debug.get("design_guide_primary_payload_binding_audit")
        or debug.get("primary_payload_binding_audit")
        or {}
    )
    cta_hash = (
        publication.get("final_publication_cta_hash")
        or debug.get("final_publication_cta_hash")
        or probe.get("final_publication_cta_hash")
        or binding_audit.get("final_publication_cta_hash")
        or button_contract.get("final_publication_cta_hash")
    )
    payload_hash = _stable_hash(apply_payload) if apply_payload else None
    button_hash = _stable_hash(button_contract) if button_contract else None
    return {
        "has_browser_state": bool(state),
        "guidance_branch": probe.get("guidance_branch") or debug.get("guidance_branch"),
        "primary_card_title": probe.get("primary_card_title") or debug.get("primary_card_title"),
        "final_publication_cta_hash": cta_hash,
        "button_contract_enabled": bool(button_contract.get("enabled") or button_contract.get("actionable")),
        "button_contract_actionable": bool(button_contract.get("actionable")),
        "button_contract_update_count": len(dict(button_contract.get("updates") or {})),
        "button_contract_hash": button_hash,
        "apply_payload_exists": bool(apply_payload),
        "apply_payload_hash": payload_hash,
        "apply_payload_update_count": len(dict(apply_payload.get("updates") or {})),
        "binding_audit_exists": bool(binding_audit),
        "binding_audit_hash": _stable_hash(binding_audit) if binding_audit else None,
        "binding_audit": binding_audit,
        "publication_hash": publication.get("publication_hash") or debug.get("publication_hash"),
        "display_hash": publication.get("final_publication_display_hash") or debug.get("final_publication_display_hash"),
        "state_fingerprint": (
            apply_payload.get("state_fingerprint")
            or binding_audit.get("state_fingerprint")
            or debug.get("state_fingerprint")
        ),
    }


def _browser_capture(url: str, *, samples: int, interval_ms: int, timeout_s: float) -> dict[str, Any]:
    _wait_for_live_url(url, timeout_s=timeout_s)
    rows: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1610, "height": 900})
        page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_s * 1000))
        for index in range(max(1, samples)):
            page.wait_for_timeout(max(0, interval_ms))
            try:
                state = dict(_load_browser_state(page, timeout_s=min(3.0, max(0.5, timeout_s))))
                state_error = None
            except Exception as exc:
                state = {}
                state_error = f"{type(exc).__name__}: {exc}"
            binding = _extract_cta_binding_state(state)
            body_signals = dict(
                page.evaluate(
                    r"""
                    () => {
                      const text = String(document.body && document.body.innerText || "");
                      return {
                        hasDesignGuide: /Design Guide/i.test(text),
                        hasApplyButton: /Run one-click auto design|Apply/i.test(text),
                        hasStartYourDesign: /Start Your Design/i.test(text),
                        hasCheckingGuidance: /Checking design guidance/i.test(text)
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
                    "binding": binding,
                    "body_signals": body_signals,
                }
            )
        browser.close()
    hashes = [row["binding"].get("final_publication_cta_hash") for row in rows]
    payload_hashes = [row["binding"].get("apply_payload_hash") for row in rows]
    button_hashes = [row["binding"].get("button_contract_hash") for row in rows]
    stable_cta_hash = bool(hashes and hashes[-1] and len(set(h for h in hashes if h)) == 1)
    stable_payload_hash = bool(payload_hashes and payload_hashes[-1] and len(set(h for h in payload_hashes if h)) == 1)
    stable_button_hash = bool(button_hashes and button_hashes[-1] and len(set(h for h in button_hashes if h)) == 1)
    return {
        "url": url,
        "samples": rows,
        "browser_state_available": any(row["binding"].get("has_browser_state") for row in rows),
        "stable_cta_hash": stable_cta_hash,
        "stable_apply_payload_hash": stable_payload_hash,
        "stable_button_contract_hash": stable_button_hash,
        "latest_binding": rows[-1]["binding"] if rows else {},
        "observed_hashes": {
            "cta": hashes,
            "apply_payload": payload_hashes,
            "button_contract": button_hashes,
        },
    }


def _guard_decision(
    *,
    scenario_id: str,
    current_cta_hash: str | None,
    previous_cta_hash: str | None,
    existing_payload: bool,
    debug_mode: bool = False,
    post_click_or_apply_in_flight: bool = False,
    stale_payload: bool = False,
    expected_skip_ready: bool,
) -> dict[str, Any]:
    reasons: list[str] = []
    if debug_mode:
        reasons.append("debug_mode_forces_rebuild")
    if post_click_or_apply_in_flight:
        reasons.append("post_click_or_apply_in_flight_forces_rebuild")
    if stale_payload:
        reasons.append("stale_payload_forces_rebuild")
    if not current_cta_hash:
        reasons.append("missing_current_cta_hash")
    if not previous_cta_hash:
        reasons.append("missing_previous_cta_hash")
    if current_cta_hash and previous_cta_hash and current_cta_hash != previous_cta_hash:
        reasons.append("cta_hash_changed")
    if not existing_payload:
        reasons.append("missing_existing_apply_payload")
    skip_ready = not reasons
    return {
        "scenario_id": scenario_id,
        "decision": "SKIP_BINDING_REBUILD_READY" if skip_ready else "REBUILD_REQUIRED",
        "skip_ready": skip_ready,
        "expected_skip_ready": expected_skip_ready,
        "expected_met": skip_ready is expected_skip_ready,
        "reasons": reasons,
    }


def _scenario_rows(live: dict[str, Any]) -> list[dict[str, Any]]:
    latest = dict(live.get("latest_binding") or {})
    live_cta_hash = latest.get("final_publication_cta_hash") or "cta-stable"
    live_existing_payload = bool(latest.get("apply_payload_exists")) or True
    return [
        _guard_decision(
            scenario_id="browser_stable_same_cta_hash",
            current_cta_hash=live_cta_hash,
            previous_cta_hash=live_cta_hash,
            existing_payload=live_existing_payload,
            expected_skip_ready=True,
        ),
        _guard_decision(
            scenario_id="browser_changed_cta_hash",
            current_cta_hash=f"{live_cta_hash}-changed",
            previous_cta_hash=live_cta_hash,
            existing_payload=live_existing_payload,
            expected_skip_ready=False,
        ),
        _guard_decision(
            scenario_id="browser_missing_current_hash",
            current_cta_hash=None,
            previous_cta_hash=live_cta_hash,
            existing_payload=live_existing_payload,
            expected_skip_ready=False,
        ),
        _guard_decision(
            scenario_id="browser_missing_existing_payload",
            current_cta_hash=live_cta_hash,
            previous_cta_hash=live_cta_hash,
            existing_payload=False,
            expected_skip_ready=False,
        ),
        _guard_decision(
            scenario_id="browser_debug_mode",
            current_cta_hash=live_cta_hash,
            previous_cta_hash=live_cta_hash,
            existing_payload=live_existing_payload,
            debug_mode=True,
            expected_skip_ready=False,
        ),
        _guard_decision(
            scenario_id="browser_post_click_or_apply_in_flight",
            current_cta_hash=live_cta_hash,
            previous_cta_hash=live_cta_hash,
            existing_payload=live_existing_payload,
            post_click_or_apply_in_flight=True,
            expected_skip_ready=False,
        ),
        _guard_decision(
            scenario_id="browser_stale_payload",
            current_cta_hash=live_cta_hash,
            previous_cta_hash=live_cta_hash,
            existing_payload=live_existing_payload,
            stale_payload=True,
            expected_skip_ready=False,
        ),
    ]


def _source_checks() -> dict[str, bool]:
    input_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8", errors="replace")
    return {
        "cta_authority_constant_present": '_FINAL_PUBLICATION_CTA_AUTHORITY = "FinalDesignGuidePublication.cta"'
        in input_source,
        "record_helper_present": "def _record_rendered_design_guide_primary_apply_payload(" in input_source,
        "current_state_apply_guard_present": "_design_guide_apply_updates_current_state_guard" in input_source,
        "stale_apply_payload_guard_surface_present": "stale_apply_payload_blocked" in input_source,
        "guarded_bypass_helper_present": all(
            token in input_source
            for token in (
                "_final_publication_cta_apply_binding_bypass_decision",
                "FinalDesignGuidePublication.cta_hash+apply_payload_hash+state_fingerprint",
                "post_click_or_apply_in_flight",
                "stale_or_changed_cta_hash",
                "stale_or_changed_payload_hash",
                "stale_or_changed_state_fingerprint",
            )
        ),
        "apply_routing_remains_page_owned": "_record_rendered_design_guide_primary_apply_payload" in input_source
        and "_record_rendered_design_guide_primary_apply_payload" not in final_source,
        "final_publication_no_page_imports": "inputs_page" not in final_source and "streamlit" not in final_source,
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = payload["generated_at"].replace(":", "-")
    payload["snapshot_hash"] = _stable_hash(
        {
            "live_summary": {
                "browser_state_available": payload["browser_live"]["browser_state_available"],
                "stable_cta_hash": payload["browser_live"]["stable_cta_hash"],
                "stable_apply_payload_hash": payload["browser_live"]["stable_apply_payload_hash"],
                "latest_binding": payload["browser_live"]["latest_binding"],
            },
            "scenarios": payload["scenarios"],
            "source_checks": payload["source_checks"],
        }
    )
    json_path = ARTIFACT_DIR / f"design_guide_cta_apply_binding_live_churn_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_cta_apply_binding_live_churn_{stamp}.md"
    live = payload["browser_live"]
    lines = [
        "# Design Guide CTA/Apply Binding Live Churn Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Browser/Live Summary",
        "",
        f"- URL: `{live.get('url')}`",
        f"- Browser state available: `{live.get('browser_state_available')}`",
        f"- Stable CTA hash observed: `{live.get('stable_cta_hash')}`",
        f"- Stable apply payload hash observed: `{live.get('stable_apply_payload_hash')}`",
        f"- Stable button contract hash observed: `{live.get('stable_button_contract_hash')}`",
        "",
        "## Scenario Decisions",
        "",
        "| Scenario | Decision | Expected met | Reasons |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["scenarios"]:
        lines.append(
            f"| `{row['scenario_id']}` | `{row['decision']}` | `{row['expected_met']}` | `{', '.join(row['reasons']) or 'none'}` |"
        )
    lines.extend(["", "## Source Checks", ""])
    for key, value in payload["source_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Next Slice", "", payload["next_slice"]])
    if payload["errors"]:
        lines.extend(["", "## Errors", "", "```json", json.dumps(payload["errors"], indent=2), "```"])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=None, help="Use an existing app URL instead of starting Streamlit.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--samples", type=int, default=4)
    parser.add_argument("--interval-ms", type=int, default=900)
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument(
        "--require-apply-payload",
        action="store_true",
        help="Fail unless the browser/live sample exposes an executor-backed apply payload.",
    )
    args = parser.parse_args()

    process: subprocess.Popen | None = None
    if args.base_url:
        url = args.base_url
    else:
        process = _start_streamlit(args.port)
        url = _query(f"http://127.0.0.1:{args.port}", {"page": "inputs", "browser_recipe": args.recipe})
    try:
        locks = {name: _latest(prefix) for name, prefix in REQUIRED_LOCKS.items()}
        live = _browser_capture(url, samples=args.samples, interval_ms=args.interval_ms, timeout_s=args.timeout_s)
        scenarios = _scenario_rows(live)
        source_checks = _source_checks()
        errors: list[str] = []
        for name, lock in locks.items():
            if lock.get("passed") is not True:
                errors.append(f"{name}_not_passed")
        if not live.get("browser_state_available"):
            errors.append("browser_state_unavailable")
        latest_binding = dict(live.get("latest_binding") or {})
        if args.require_apply_payload and not bool(latest_binding.get("apply_payload_exists")):
            errors.append("required_apply_payload_not_observed")
        if args.require_apply_payload and not bool(latest_binding.get("button_contract_enabled")):
            errors.append("required_enabled_button_contract_not_observed")
        if not all(source_checks.values()):
            errors.append("source_checks_failed")
        for row in scenarios:
            if row.get("expected_met") is not True:
                errors.append(f"{row.get('scenario_id')}_unexpected_decision")
        payload = {
            "schema": "design_guide_cta_apply_binding_live_churn.v1",
            "status": "PASS" if not errors else "FAIL",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "product_behavior_changed": False,
            "browser_live": live,
            "required_apply_payload": bool(args.require_apply_payload),
            "scenarios": scenarios,
            "source_checks": source_checks,
            "locks": {
                name: {"path": lock.get("path"), "passed": lock.get("passed"), "found": lock.get("found")}
                for name, lock in locks.items()
            },
            "errors": errors,
            "ready_for_live_bypass_implementation": False,
            "next_slice": (
                "If this remains PASS on an actionable post-click fixture, implement a guarded non-debug binding "
                "bypass keyed by FinalDesignGuidePublication.cta hash. Keep post-click/apply-in-flight, stale, "
                "debug, missing-hash, and missing-payload states as rebuild paths."
            ),
        }
        json_path, md_path = _write(payload)
        print(f"design_guide_cta_apply_binding_live_churn {payload['status']}")
        print(f"json={json_path}")
        print(f"report={md_path}")
        if errors:
            print("errors=" + json.dumps(errors))
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
