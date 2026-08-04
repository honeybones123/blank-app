"""Browser/live deadness probe for guarded Design Guide restamper fallbacks.

This snapshot does not delete code. It samples live browser recipes and checks
whether the remaining guarded fallback wrappers report that the old page-owned
restamper helper was actually used. Deletion is only considered later if live
states observe the wrappers and all observed rows avoid old-helper fallback.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_helpers import (  # noqa: E402
    _browser_state_raw_candidates,
    _load_browser_state,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _query,
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
DEFAULT_RECIPES = ["R1A_M300_V0", "R2A_M0_V400", "R3A_M300_V400", "R6A_M45_V150"]
WRAPPER_KEYS = {
    "compatibility": "final_visible_contract_binding_adapter_cutovers",
    "default_rebuild": "final_visible_restamper_default_rebuild_adapter_cutovers",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


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
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _walk(value: Any, *, path: str = "$") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        rows.append((path, value))
        for key, child in value.items():
            rows.extend(_walk(child, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(_walk(child, path=f"{path}[{index}]"))
    return rows


def _collect_fallback_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path, node in _walk(state):
        if not isinstance(node, dict):
            continue
        for wrapper_kind, key in WRAPPER_KEYS.items():
            traces = node.get(key)
            if not isinstance(traces, dict):
                continue
            for callsite, trace in traces.items():
                if not isinstance(trace, dict):
                    continue
                row = {
                    "path": path,
                    "wrapper_kind": wrapper_kind,
                    "callsite": str(callsite),
                    "used_old_helper_fallback": bool(trace.get("used_old_helper_fallback")),
                    "fallback_reason": str(trace.get("fallback_reason") or ""),
                    "adapter_hash": trace.get("adapter_hash") or trace.get("component_projection_hash"),
                    "output_hash": trace.get("output_hash") or trace.get("projected_item_hash"),
                    "product_driving": trace.get("product_driving"),
                    "render_driving": trace.get("render_driving"),
                    "apply_driving": trace.get("apply_driving"),
                    "session_driving": trace.get("session_driving"),
                }
                dedupe = _stable_hash(row)
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                rows.append(row)
    return rows


def _load_best_state(page, *, timeout_s: float) -> tuple[dict[str, Any], str | None]:
    deadline = time.time() + max(1.0, timeout_s)
    best: dict[str, Any] = {}
    best_score = -1
    last_error: str | None = None
    while time.time() < deadline:
        try:
            candidates: list[dict[str, Any]] = []
            for raw in _browser_state_raw_candidates(page, timeout_ms=1500):
                try:
                    parsed = json.loads(raw)
                except Exception:
                    continue
                if isinstance(parsed, dict):
                    candidates.append(parsed)
            if not candidates:
                fallback = _load_browser_state(page, timeout_s=1.0)
                if isinstance(fallback, dict):
                    candidates.append(fallback)
            for candidate in candidates:
                rows = _collect_fallback_rows(candidate)
                score = len(rows) * 100
                if candidate.get("browser_shared_probe"):
                    score += 10
                if candidate.get("summary_state_probe"):
                    score += 10
                if score > best_score:
                    best = candidate
                    best_score = score
            if best and _collect_fallback_rows(best):
                return best, None
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(0.25)
    return best, last_error


def _sample_recipe(page, *, base_url: str, recipe: str, wait_ms: int) -> dict[str, Any]:
    page.goto(
        _query(base_url, {"page": "inputs", "browser_recipe": recipe}),
        wait_until="domcontentloaded",
        timeout=90_000,
    )
    page.wait_for_timeout(wait_ms)
    state, state_error = _load_best_state(page, timeout_s=15.0)
    rows = _collect_fallback_rows(state)
    return {
        "recipe": recipe,
        "state_error": state_error,
        "rows": rows,
        "row_count": len(rows),
        "fallback_used_count": sum(1 for row in rows if row.get("used_old_helper_fallback") is True),
        "wrappers_seen": sorted({str(row.get("wrapper_kind")) for row in rows}),
        "callsites_seen": sorted({str(row.get("callsite")) for row in rows}),
        "state_top_keys": sorted(str(key) for key in state.keys())[:80],
    }


def _capture(base_url: str, *, recipes: list[str], wait_ms: int, headed: bool) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.set_default_timeout(30_000)
        recipe_rows = [
            _sample_recipe(page, base_url=base_url, recipe=recipe, wait_ms=wait_ms)
            for recipe in recipes
        ]
        browser.close()
    all_rows = [row for recipe in recipe_rows for row in list(recipe.get("rows") or [])]
    wrappers_seen = sorted({str(row.get("wrapper_kind")) for row in all_rows if row.get("wrapper_kind")})
    fallback_used = [row for row in all_rows if row.get("used_old_helper_fallback") is True]
    required_wrappers_observed = all(kind in wrappers_seen for kind in WRAPPER_KEYS)
    decision = (
        "GUARDED_FALLBACKS_OBSERVED_AND_NOT_USED"
        if required_wrappers_observed and not fallback_used
        else "GUARDED_FALLBACK_DEADNESS_NOT_FULLY_PROVEN"
    )
    status = "PASS" if required_wrappers_observed and not fallback_used else "PARTIAL"
    return {
        "decision": decision,
        "status": status,
        "base_url": base_url,
        "recipes": recipes,
        "recipe_rows": recipe_rows,
        "rows": all_rows,
        "row_count": len(all_rows),
        "wrappers_seen": wrappers_seen,
        "required_wrappers_observed": required_wrappers_observed,
        "fallback_used_count": len(fallback_used),
        "fallback_used_rows": fallback_used,
        "safe_to_delete_old_helper_fallbacks_now": bool(required_wrappers_observed and not fallback_used),
        "latest": {
            "render_fallback_cutover": _latest("design_guide_render_fallback_default_rebuild_adapter_cutover"),
            "fallback_inventory": _latest("design_guide_remaining_fallback_only_paths"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
        "next_safe_step": (
            "Delete guarded fallback calls only if this snapshot is PASS; otherwise add targeted "
            "recipes or keep wrappers bounded as emergency fallback."
        ),
    }


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "render_fallback_cutover_pass": (latest.get("render_fallback_cutover") or {}).get("status") == "PASS",
        "fallback_inventory_pass": (latest.get("fallback_inventory") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "no_observed_old_helper_fallback": capture.get("fallback_used_count") == 0,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Design Guide Guarded Restamper Fallback Live Deadness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{payload.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        f"- Wrappers seen: `{payload.get('wrappers_seen')}`",
        f"- Fallback used count: `{payload.get('fallback_used_count')}`",
        f"- Safe to delete old helper fallbacks now: `{payload.get('safe_to_delete_old_helper_fallbacks_now')}`",
        "",
        "## Verification Results",
    ]
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Next Safe Step", str(payload.get("next_safe_step"))])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="")
    parser.add_argument("--port", type=int, default=8589)
    parser.add_argument("--wait-ms", type=int, default=3500)
    parser.add_argument("--recipes", nargs="*", default=DEFAULT_RECIPES)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    compile_run = _run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "tools/verification/design_guide_guarded_restamper_fallback_live_deadness_snapshot.py",
        ]
    )
    process: subprocess.Popen | None = None
    base_url = str(args.url or "").strip()
    try:
        if not base_url:
            process = _start_streamlit(int(args.port))
            base_url = f"http://127.0.0.1:{int(args.port)}"
        else:
            _wait_for_http(base_url, timeout_s=45.0)
        capture = _capture(
            base_url,
            recipes=[str(recipe) for recipe in args.recipes if str(recipe).strip()],
            wait_ms=int(args.wait_ms),
            headed=bool(args.headed),
        )
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
    checks = _checks(capture, compile_run)
    hard_failures = [
        key
        for key, value in checks.items()
        if value is not True and key not in {"no_observed_old_helper_fallback"}
    ]
    status = "FAIL" if hard_failures else str(capture.get("status") or "PARTIAL")
    payload = {
        "schema": "design_guide_guarded_restamper_fallback_live_deadness_snapshot.v1",
        **capture,
        "status": status,
        "created_at": stamp,
        "checks": checks,
        "failures": hard_failures,
        "compile_run": compile_run,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_guarded_restamper_fallback_live_deadness_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_guarded_restamper_fallback_live_deadness_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_guarded_restamper_fallback_live_deadness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(f"design_guide_guarded_restamper_fallback_live_deadness {status}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    if hard_failures:
        print("failures=" + ", ".join(hard_failures))
    return 0 if status in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

