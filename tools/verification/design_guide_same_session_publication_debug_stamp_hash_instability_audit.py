"""Same-session publication debug-stamp hash instability audit.

This is proof-only. It does not implement a cache or bypass. It performs a
true same-browser-session no-change rerun, then compares the authoritative
FinalDesignGuidePublication hashes with the legacy/debug verifier payload hash
used by duplicate publication stamp bypass decisions.
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
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_browser_live_smoothness_profile import (  # noqa: E402
    _debug_bundle,
)
from tools.verification.design_guide_same_session_no_change_rerun_profile import (  # noqa: E402
    DEFAULT_RECIPE,
    _click_streamlit_rerun,
    _load_browser_state_prefer_final_debug,
    _summarise_state,
    _wait_for_full_publication_state,
    _wait_for_rerun_seq_change,
    _wait_for_streamlit_idle,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _query(base_url: str, params: dict[str, Any]) -> str:
    return f"{base_url.rstrip('/')}/?{urlencode({key: value for key, value in params.items() if value is not None})}"


def _compact(value: Any, *, max_text: int = 600) -> Any:
    if isinstance(value, dict):
        return {str(key): _compact(val, max_text=max_text) for key, val in value.items()}
    if isinstance(value, list):
        return [_compact(val, max_text=max_text) for val in value[:20]]
    if isinstance(value, str) and len(value) > max_text:
        return value[:max_text] + "...<truncated>"
    return value


def _payload_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = sorted(set(before) | set(after))
    changed = {}
    unchanged = []
    for key in keys:
        if before.get(key) == after.get(key):
            unchanged.append(key)
        else:
            changed[key] = {
                "before": _compact(before.get(key)),
                "after": _compact(after.get(key)),
            }
    return {"changed": changed, "unchanged": unchanged}


def _decision_rows(state_summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in list(state_summary.get("publication_stamp_decisions") or []):
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "candidate_id": row.get("candidate_id") or row.get("candidate"),
                "instance_key": row.get("instance_key"),
                "decision": row.get("decision"),
                "reason": row.get("reason"),
                "bypassed": bool(row.get("bypassed")),
                "publication_hash": row.get("publication_hash"),
                "previous_publication_hash": row.get("previous_publication_hash"),
                "debug_force_rebuild": bool(row.get("debug_force_rebuild")),
            }
        )
    return rows


def _capture(base_url: str, *, recipe: str, headed: bool, timeout_s: float) -> dict[str, Any]:
    url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_s * 1000))
        idle_before = _wait_for_streamlit_idle(page, timeout_s=timeout_s)
        before_state, before_samples = _wait_for_full_publication_state(page, timeout_s=timeout_s)
        before_summary = _summarise_state(before_state)
        before_bundle = _debug_bundle(before_state)
        before_payload = dict(before_bundle.get("final_publication_verifier_payload") or {})
        click = _click_streamlit_rerun(page)
        if click.get("clicked"):
            after_state, samples = _wait_for_rerun_seq_change(
                page,
                before_summary.get("rerun_seq"),
                timeout_s=timeout_s,
            )
        else:
            after_state, samples = {}, []
        page.wait_for_timeout(900)
        final_state = (
            dict(_load_browser_state_prefer_final_debug(page, timeout_s=min(8.0, timeout_s)))
            if click.get("clicked")
            else after_state
        )
        after_summary = _summarise_state(final_state) if final_state else {}
        after_bundle = _debug_bundle(final_state)
        after_payload = dict(after_bundle.get("final_publication_verifier_payload") or {})
        idle_after = _wait_for_streamlit_idle(page, timeout_s=min(12.0, timeout_s))
        browser.close()
    return {
        "url": url,
        "recipe": recipe,
        "idle_before": idle_before,
        "idle_after": idle_after,
        "before": {
            "summary": before_summary,
            "verifier_payload": _compact(before_payload),
        },
        "click": click,
        "after": {
            "summary": after_summary,
            "verifier_payload": _compact(after_payload),
        },
        "before_poll_samples": before_samples,
        "poll_samples": samples,
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    before = dict((capture.get("before") or {}).get("summary") or {})
    after = dict((capture.get("after") or {}).get("summary") or {})
    before_payload = dict((capture.get("before") or {}).get("verifier_payload") or {})
    after_payload = dict((capture.get("after") or {}).get("verifier_payload") or {})
    diff = _payload_diff(before_payload, after_payload)
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
    decision_rows = _decision_rows(after)
    stale_decisions = [
        row for row in decision_rows if row.get("reason") == "stale_or_changed_publication_hash"
    ]
    before_payload_ready = bool(before_payload.get("publication_hash"))
    after_payload_ready = bool(after_payload.get("publication_hash"))
    verifier_hash_changed = before_payload.get("publication_hash") != after_payload.get("publication_hash")
    status = "PASS" if capture.get("click", {}).get("clicked") and stable_authority and before_payload_ready else "PARTIAL"
    if not before_payload_ready:
        recommended = (
            "Do not implement publication/debug stamp reuse yet; the pre-click browser probe did not expose "
            "final_publication_verifier_payload. First audit why the hidden browser state prefers or emits a "
            "pre-render/lightweight state before the same-session rerun."
        )
    elif not decision_rows:
        recommended = "No publication debug-stamp decisions were visible; rerun the same-session profiler."
    elif stable_authority and stale_decisions and verifier_hash_changed:
        recommended = (
            "Audit/rekey duplicate debug-stamp bypass to the stable FinalDesignGuidePublication "
            "authority hash only after changed verifier payload fields are confirmed non-authoritative."
        )
    elif stable_authority and not stale_decisions:
        recommended = "No debug-stamp hash instability remains; re-rank smoothness hotspots."
    else:
        recommended = "Do not bypass; authority hashes were not stable."
    return {
        "status": status,
        "stable_authority_hashes": stable_authority,
        "before_verifier_payload_ready": before_payload_ready,
        "after_verifier_payload_ready": after_payload_ready,
        "verifier_payload_publication_hash_changed": verifier_hash_changed,
        "changed_payload_fields": sorted(diff["changed"]),
        "changed_payload_field_count": len(diff["changed"]),
        "publication_stamp_decisions": decision_rows,
        "stale_publication_stamp_decision_count": len(stale_decisions),
        "ready_for_rekey_implementation": False,
        "recommended_next_slice": recommended,
        "payload_diff": diff,
    }


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper() or "LOCKED" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Same-Session Publication Debug-Stamp Hash Instability Audit",
        "",
        f"Status: `{payload.get('status')}`",
        "",
        "## Executive Summary",
        "",
        f"- Stable authority hashes: `{cls.get('stable_authority_hashes')}`",
        f"- Before verifier payload ready: `{cls.get('before_verifier_payload_ready')}`",
        f"- After verifier payload ready: `{cls.get('after_verifier_payload_ready')}`",
        f"- Verifier payload publication hash changed: `{cls.get('verifier_payload_publication_hash_changed')}`",
        f"- Stale stamp decisions: `{cls.get('stale_publication_stamp_decision_count')}`",
        f"- Ready for rekey implementation: `{cls.get('ready_for_rekey_implementation')}`",
        "",
        "## Changed Verifier Payload Fields",
        "",
    ]
    changed = cls.get("changed_payload_fields") or []
    if changed:
        lines.extend(f"- `{field}`" for field in changed)
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Stamp Decisions",
            "",
            "| Candidate | Decision | Reason | Current hash | Previous hash |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in cls.get("publication_stamp_decisions") or []:
        lines.append(
            "| `{}` | `{}` | `{}` | `{}` | `{}` |".format(
                row.get("candidate_id"),
                row.get("decision"),
                row.get("reason"),
                row.get("publication_hash"),
                row.get("previous_publication_hash"),
            )
        )
    lines.extend(["", "## Recommendation", "", str(cls.get("recommended_next_slice") or "")])
    return "\n".join(lines) + "\n"


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_same_session_publication_debug_stamp_hash_instability_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_same_session_publication_debug_stamp_hash_instability_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8633)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_SAME_SESSION_RERUN_URL"))
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
        payload: dict[str, Any] = {
            "schema": "design_guide_same_session_publication_debug_stamp_hash_instability_audit.v1",
            "created_at": created_at,
            "status": classification["status"],
            "classification": classification,
            "capture": capture,
            "latest": {
                "duplicate_stamp_bypass_live_impact": _latest("design_guide_duplicate_publication_stamp_bypass_live_impact"),
                "same_session_no_change_rerun_profile": _latest("design_guide_same_session_no_change_rerun_profile"),
                "independence_lock": _latest("design_guide_independence_lock"),
                "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
                "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
                "zero_authority_lock": _latest("design_brain_inputs_page_zero_authority_inventory_lock"),
            },
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
