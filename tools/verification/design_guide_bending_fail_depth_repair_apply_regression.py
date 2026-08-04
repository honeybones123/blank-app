"""Live regression for bending-fail depth/width repair Apply behaviour.

This is the real-browser guard for the user-reported case where a bending-only
failure was blocked even though a legal depth/width repair existed. It verifies
the visible CTA contract and the post-click session/widget state mutation.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
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

from tools.verification.helpers.browser_helpers import _load_browser_state  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    BROWSER_STATE_LABEL,
    _start_streamlit,
    _wait_for_http,
)
from tools.verification.design_guide_bending_fail_no_button_root_audit import (  # noqa: E402
    _capture_root,
    _visible_dom_capture,
    _wait_for_final_design_guide_state,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
RECIPE = "BENDING_FAIL_ZERO_SHEAR_DUCTILITY_DEPTH_REPAIR_REPRO"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _query(url: str, params: dict[str, Any]) -> str:
    return f"{str(url).rstrip('/')}/?{urlencode({k: v for k, v in params.items() if v is not None})}"


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _same_float(value: Any, expected: float, *, tol: float = 1e-6) -> bool:
    try:
        return abs(float(value) - float(expected)) <= tol
    except Exception:
        return False


def _wait_for_post_apply_state(page, *, timeout_s: float) -> tuple[dict[str, Any], dict[str, Any]]:
    deadline = time.time() + max(1.0, float(timeout_s or 1.0))
    last_state: dict[str, Any] = {}
    last_dom: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            last_state = _load_browser_state(page, timeout_s=2.0)
        except Exception:
            last_state = {}
        try:
            last_dom = _visible_dom_capture(page)
        except Exception:
            last_dom = {}
        shared = _as_dict(last_state.get("browser_shared_probe"))
        summary_state = _as_dict(last_state.get("summary_state_probe"))
        overview = _as_dict(last_state.get("summary_overview_probe"))
        last_apply = _as_dict(_as_dict(last_state.get("post_cleanup_acceptance_probe")).get("last_apply_route"))
        if (
            _same_float(shared.get("b"), 350.0)
            and _same_float(shared.get("D"), 625.0)
            and _same_float(summary_state.get("b"), 350.0)
            and _same_float(summary_state.get("D"), 625.0)
            and bool(overview.get("all_key_pass"))
            and not bool(overview.get("any_fail"))
            and bool(last_apply.get("post_apply_required_checks_pass"))
            and _as_dict(last_apply.get("actual_changed_updates")).get("b") == 350.0
            and _as_dict(last_apply.get("actual_changed_updates")).get("D") == 625.0
        ):
            return last_state, last_dom
        time.sleep(0.5)
    return last_state, last_dom


def _failure_report(pre_root: dict[str, Any], post_state: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    contract = _as_dict(pre_root.get("button_contract"))
    if contract.get("family") != "BENDING_FAIL_GOVERNS":
        failures.append(f"pre_click_family_not_bending_fail:{contract.get('family')}")
    if contract.get("enabled") is not True:
        failures.append(f"pre_click_contract_not_enabled:{contract}")
    if contract.get("preview_pass") is not True:
        failures.append(f"pre_click_preview_not_pass:{contract.get('preview_pass')}")
    updates = _as_dict(contract.get("updates"))
    if not (_same_float(updates.get("b"), 350.0) and _same_float(updates.get("D"), 625.0)):
        failures.append(f"pre_click_contract_updates_not_depth_width_repair:{updates}")

    shared = _as_dict(post_state.get("browser_shared_probe"))
    summary_state = _as_dict(post_state.get("summary_state_probe"))
    overview = _as_dict(post_state.get("summary_overview_probe"))
    last_apply = _as_dict(_as_dict(post_state.get("post_cleanup_acceptance_probe")).get("last_apply_route"))
    actual_changed = _as_dict(last_apply.get("actual_changed_updates"))
    queued_updates = _as_dict(last_apply.get("queued_apply_updates"))
    applied_updates = _as_dict(last_apply.get("applied_updates"))
    if not (_same_float(shared.get("b"), 350.0) and _same_float(shared.get("D"), 625.0)):
        failures.append(f"shared_state_not_updated:b={shared.get('b')}:D={shared.get('D')}")
    if not (_same_float(summary_state.get("b"), 350.0) and _same_float(summary_state.get("D"), 625.0)):
        failures.append(f"summary_state_not_updated:b={summary_state.get('b')}:D={summary_state.get('D')}")
    if not bool(overview.get("all_key_pass")) or bool(overview.get("any_fail")):
        failures.append(f"post_apply_required_checks_not_pass:{overview.get('statuses')}")
    if not bool(last_apply.get("post_apply_required_checks_pass")):
        failures.append("last_apply_route_required_checks_not_pass")
    if not (_same_float(actual_changed.get("b"), 350.0) and _same_float(actual_changed.get("D"), 625.0)):
        failures.append(f"actual_changed_updates_missing_depth_width:{actual_changed}")
    if queued_updates != applied_updates:
        failures.append(f"queued_applied_updates_mismatch:queued={queued_updates}:applied={applied_updates}")
    if last_apply.get("queued_apply_candidate_id") != last_apply.get("applied_candidate_id"):
        failures.append(
            "queued_applied_candidate_id_mismatch:"
            f"queued={last_apply.get('queued_apply_candidate_id')}:applied={last_apply.get('applied_candidate_id')}"
        )
    if bool(last_apply.get("legacy_fallback_used")):
        failures.append("legacy_fallback_used_for_apply")
    return failures


def _compact_payload(
    *,
    status: str,
    failures: list[str],
    pre_root: dict[str, Any],
    post_state: dict[str, Any],
    post_dom: dict[str, Any],
    url: str,
) -> dict[str, Any]:
    last_apply = _as_dict(_as_dict(post_state.get("post_cleanup_acceptance_probe")).get("last_apply_route"))
    overview = _as_dict(post_state.get("summary_overview_probe"))
    return {
        "schema": "design_guide_bending_fail_depth_repair_apply_regression.v1",
        "status": status,
        "created_at": _stamp(),
        "recipe": RECIPE,
        "url": url,
        "failures": list(failures),
        "pre_click_button_contract": _as_dict(pre_root.get("button_contract")),
        "post_click_shared": {
            key: _as_dict(post_state.get("browser_shared_probe")).get(key)
            for key in ("b", "D", "uls_Mstar", "uls_Vstar", "inputs_load_Mstar_pos_proxy", "inputs_load_Vstar_proxy")
        },
        "post_click_summary_state": {
            key: _as_dict(post_state.get("summary_state_probe")).get(key)
            for key in ("b", "D", "uls_Mstar", "uls_Vstar")
        },
        "post_click_overview": {
            "worst_util": overview.get("worst_util"),
            "statuses": _as_dict(overview.get("statuses")),
            "all_key_pass": bool(overview.get("all_key_pass")),
            "any_fail": bool(overview.get("any_fail")),
        },
        "last_apply_route": {
            key: last_apply.get(key)
            for key in (
                "queued_apply_candidate_id",
                "applied_candidate_id",
                "queued_apply_updates",
                "applied_updates",
                "applied_changed_keys",
                "actual_changed_updates",
                "payload_binding_match",
                "post_apply_required_checks_pass",
                "legacy_fallback_used",
            )
        },
        "post_click_action_buttons": post_dom.get("actionButtons"),
    }


def _write_report(payload: dict[str, Any], json_path: Path, report_path: Path) -> None:
    lines = [
        "# Bending Fail Depth Repair Apply Regression",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Recipe: `{payload.get('recipe')}`",
        f"- JSON: `{json_path}`",
        "",
        "## Failures",
        "",
    ]
    failures = list(payload.get("failures") or [])
    lines.extend([f"- {failure}" for failure in failures] or ["- None"])
    lines.extend(
        [
            "",
            "## Proof",
            "",
            "```json",
            json.dumps(
                {
                    "pre_click_button_contract": payload.get("pre_click_button_contract"),
                    "post_click_shared": payload.get("post_click_shared"),
                    "post_click_overview": payload.get("post_click_overview"),
                    "last_apply_route": payload.get("last_apply_route"),
                },
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9320)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout-s", type=float, default=120.0)
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    process: subprocess.Popen | None = None
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_bending_fail_depth_repair_apply_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bending_fail_depth_repair_apply_regression_{stamp}.md"
    failures: list[str] = []
    pre_root: dict[str, Any] = {}
    post_state: dict[str, Any] = {}
    post_dom: dict[str, Any] = {}
    url = _query(base_url, {"page": "inputs", "browser_recipe": RECIPE})
    try:
        if args.base_url is None:
            process = _start_streamlit(args.port)
        else:
            _wait_for_http(base_url)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            context = browser.new_context()
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.get_by_label(BROWSER_STATE_LABEL).wait_for(state="attached", timeout=30_000)
            _wait_for_final_design_guide_state(page, timeout_s=args.timeout_s / 2)
            pre_root = _capture_root(page, scenario_id=RECIPE)
            button = page.get_by_role("button", name="Run one-click auto design").first
            button.wait_for(state="visible", timeout=15_000)
            if button.is_disabled():
                failures.append("one_click_button_visible_but_disabled")
            else:
                button.click(timeout=10_000)
                post_state, post_dom = _wait_for_post_apply_state(page, timeout_s=args.timeout_s / 2)
            context.close()
            browser.close()
    except Exception as exc:
        failures.append(f"{type(exc).__name__}:{exc}")
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    failures.extend(_failure_report(pre_root, post_state))
    status = "PASS" if not failures else "FAIL"
    payload = _compact_payload(
        status=status,
        failures=failures,
        pre_root=pre_root,
        post_state=post_state,
        post_dom=post_dom,
        url=url,
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, json_path, report_path)
    print(f"design_guide_bending_fail_depth_repair_apply_regression {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + json.dumps(failures, default=str))
    else:
        print("updates=" + json.dumps(payload["last_apply_route"].get("actual_changed_updates"), sort_keys=True))
        print("worst_util=" + str(payload["post_click_overview"].get("worst_util")))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
