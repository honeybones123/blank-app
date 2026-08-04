"""Mixed-family live fuzz that proves visible widget-origin inputs persist."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

MIXED_CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "WIDGET_ORIGIN_BENDING_FAIL_AFTER_TYPED_EDIT",
        "seed_recipe": "C_combined_underdesign",
        "expected_families": {"BENDING_FAIL_GOVERNS"},
        "inputs": {
            "Positive design moment Mu*+ (kNm)": 310.0,
            "Design shear Vu* (kN)": 80.0,
        },
    },
    {
        "case_id": "WIDGET_ORIGIN_COMBINED_FAIL_AFTER_TYPED_EDIT",
        "seed_recipe": "C_combined_underdesign",
        "expected_families": {"COMBINED_BENDING_SHEAR_FAIL", "COMBINED_BENDING_SHEAR_FAIL_GOVERNS"},
        "inputs": {
            "Positive design moment Mu*+ (kNm)": 310.0,
            "Design shear Vu* (kN)": 410.0,
        },
    },
    {
        "case_id": "WIDGET_ORIGIN_OVERDESIGN_AFTER_TYPED_EDIT",
        "seed_recipe": "OPT_EXPECT_COMBINED_SAFE_OVERDESIGNED",
        "expected_families": {
            "BENDING_OVERDESIGN_GOVERNS",
            "SHEAR_OVERDESIGN_GOVERNS",
            "COMBINED_OVERDESIGN",
            "COMBINED_OVERDESIGN_GOVERNS",
        },
        "requires_cleanup_action": True,
        "inputs": {
            "Positive design moment Mu*+ (kNm)": 60.0,
            "Design shear Vu* (kN)": 25.0,
        },
    },
    {
        "case_id": "WIDGET_ORIGIN_SHEAR_FAIL_AFTER_TYPED_EDIT",
        "seed_recipe": "R2A_M0_V400",
        "expected_families": {"SHEAR_FAIL_GOVERNS", "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"},
        "inputs": {
            "Positive design moment Mu*+ (kNm)": 70.0,
            "Design shear Vu* (kN)": 420.0,
        },
    },
    {
        "case_id": "WIDGET_ORIGIN_SHEAR_OVERDESIGN_AFTER_TYPED_EDIT",
        "seed_recipe": "OPT_EXPECT_SHEAR_SAFE_OVERDESIGNED",
        "expected_families": {
            "SHEAR_OVERDESIGN_GOVERNS",
            "COMBINED_OVERDESIGN",
            "COMBINED_OVERDESIGN_GOVERNS",
        },
        "requires_cleanup_action": True,
        "inputs": {
            "Positive design moment Mu*+ (kNm)": 20.0,
            "Design shear Vu* (kN)": 45.0,
        },
    },
)


def _query(base_url: str, params: dict[str, Any]) -> str:
    return f"{base_url.rstrip('/')}?{urlencode(params)}"


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        text = str(value).replace(",", "").strip()
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(match.group(0)) if match else None
    except Exception:
        return None


def _values_match(left: Any, right: Any, *, tol: float = 1e-6) -> bool:
    left_f = _safe_float(left)
    right_f = _safe_float(right)
    return left_f is not None and right_f is not None and abs(left_f - right_f) <= tol


def _state_candidates(page) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    selectors = (
        'textarea[aria-label="Browser state"]',
        'input[aria-label="Browser state"]',
        '[data-codex-browser-state-probe="1"]',
    )
    for selector in selectors:
        try:
            locator = page.locator(selector)
            count = min(locator.count(), 20)
        except Exception:
            count = 0
        for index in range(count):
            el = locator.nth(index)
            try:
                raw = el.input_value(timeout=500)
            except Exception:
                try:
                    raw = el.inner_text(timeout=500)
                except Exception:
                    raw = ""
            text = str(raw or "").strip()
            if not text.startswith("{"):
                continue
            try:
                payload = json.loads(text)
            except Exception:
                continue
            if isinstance(payload, dict):
                candidates.append(payload)
    return candidates


def _payload_cid(payload: dict[str, Any]) -> str:
    query_probe = dict(payload.get("browser_query_param_probe") or {})
    query_params = dict(query_probe.get("query_params") or {})
    experimental_query_params = dict(query_probe.get("experimental_query_params") or {})
    for source in (query_params, experimental_query_params):
        value = source.get("cid")
        if isinstance(value, list):
            value = value[0] if value else ""
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _load_browser_state(page, *, expected_cid: str | None = None) -> dict[str, Any]:
    candidates = _state_candidates(page)
    if not candidates:
        return {}
    expected_cid_text = str(expected_cid or "").strip()
    if expected_cid_text:
        matching = [payload for payload in candidates if _payload_cid(payload) == expected_cid_text]
        if matching:
            candidates = matching
    ranked = sorted(
        candidates,
        key=lambda payload: (
            (not expected_cid_text) or _payload_cid(payload) == expected_cid_text,
            str(payload.get("browser_probe_phase") or payload.get("probe_phase") or "") == "post_page_render",
            bool(payload.get("final_publication_verifier_payload")),
            bool(payload.get("summary_state_probe")),
        ),
        reverse=True,
    )
    merged = dict(ranked[0])
    for payload in candidates:
        payload_d = dict(payload or {})
        for key in (
            "browser_recipe_last_action",
            "browser_shared_probe",
            "summary_state_probe",
            "summary_overview_probe",
        ):
            if merged.get(key) in (None, "", [], {}):
                value = payload_d.get(key)
                if value not in (None, "", [], {}):
                    merged[key] = value
        merged_debug = dict(merged.get("browser_debug_probe") or {})
        payload_debug = dict(payload_d.get("browser_debug_probe") or {})
        if payload_debug:
            for key, value in payload_debug.items():
                if merged_debug.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
                    merged_debug[key] = value
            merged["browser_debug_probe"] = merged_debug
    return merged


def _publication_family_from_state(state: dict[str, Any]) -> str:
    final_payload = dict(state.get("final_publication_verifier_payload") or {})
    cta = dict(final_payload.get("cta") or {})
    return str(
        final_payload.get("selected_family_id")
        or final_payload.get("published_family_id")
        or cta.get("family")
        or cta.get("family_id")
        or ""
    ).strip().upper()


def _visible_family_from_card(text: str, attrs: dict[str, Any]) -> str:
    attr_family = str(
        attrs.get("data-selected-family-id")
        or attrs.get("data-published-family-id")
        or attrs.get("data-cta-family-id")
        or ""
    ).strip().upper()
    if attr_family:
        return attr_family
    lower = str(text or "").lower()
    if "bending and shear" in lower or "combined" in lower:
        return "COMBINED_BENDING_SHEAR_FAIL"
    if "overdesign" in lower or "reduce" in lower:
        return "COMBINED_OVERDESIGN"
    if "bending" in lower:
        return "BENDING_FAIL_GOVERNS"
    if "shear" in lower:
        return "SHEAR_FAIL_GOVERNS"
    return ""


def _wait_for_final_card(page, *, timeout_s: float) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            locator = page.locator(".fast-guidance-item").first
            if locator.count() > 0 and locator.is_visible(timeout=750):
                text = str(locator.inner_text(timeout=1_000) or "").strip()
                attrs = locator.evaluate(
                    "(el)=>Object.fromEntries(Array.from(el.attributes).map(a=>[a.name,a.value]))"
                )
                loading = "checking design guidance" in text.lower()
                last = {"ready": bool(text and not loading), "text": text, "attrs": dict(attrs or {})}
                if last["ready"]:
                    return last
        except Exception as exc:
            last = {"ready": False, "error": f"{type(exc).__name__}: {exc}"}
        page.wait_for_timeout(500)
    return last or {"ready": False, "error": "timeout"}


def _input_value(page, label: str) -> str:
    locator = page.locator(f'input[aria-label="{label}"]:visible').first
    try:
        locator.wait_for(state="attached", timeout=10_000)
        return str(locator.input_value(timeout=5_000) or "")
    except Exception:
        return ""


def _set_number_input(page, label: str, value: float) -> None:
    last_error = ""
    for _attempt in range(8):
        try:
            locator = page.locator(f'input[aria-label="{label}"]:visible').first
            locator.wait_for(state="attached", timeout=10_000)
            locator.scroll_into_view_if_needed(timeout=5_000)
            locator.fill(str(value), timeout=8_000)
            locator.press("Enter", timeout=5_000)
            locator.press("Tab", timeout=5_000)
            page.wait_for_timeout(700)
            for _poll in range(12):
                try:
                    current = locator.input_value(timeout=1_000)
                except Exception:
                    current = ""
                if _values_match(current, value):
                    return
                page.wait_for_timeout(350)
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            page.wait_for_timeout(750)
    raise RuntimeError(f"failed_to_set_number_input:{label}:{value}:{last_error}")


def _wait_for_widget_and_state(
    page,
    expected_inputs: dict[str, float],
    *,
    timeout_s: float,
    expected_cid: str | None = None,
) -> dict[str, Any]:
    label_to_state_keys = {
        "Positive design moment Mu*+ (kNm)": ("uls_Mstar_pos_manual", "load_Mstar_pos_proxy", "inputs_load_Mstar_pos_proxy"),
        "Design shear Vu* (kN)": ("uls_Vstar", "load_Vstar_proxy", "inputs_load_Vstar_proxy"),
    }
    deadline = time.time() + timeout_s
    last: dict[str, Any] = {}
    while time.time() < deadline:
        widget_values = {label: _input_value(page, label) for label in expected_inputs}
        state = _load_browser_state(page, expected_cid=expected_cid)
        shared = dict(state.get("browser_shared_probe") or {})
        summary = dict(state.get("summary_state_probe") or {})
        mismatches: list[str] = []
        for label, expected in expected_inputs.items():
            if not _values_match(widget_values.get(label), expected):
                mismatches.append(f"widget:{label}:{widget_values.get(label)}!={expected}")
            saw_state_key = False
            for state_key in label_to_state_keys.get(label, ()):
                source = shared if state_key in shared else summary
                if state_key not in source:
                    continue
                saw_state_key = True
                if not _values_match(source.get(state_key), expected):
                    mismatches.append(f"state:{state_key}:{source.get(state_key)}!={expected}")
            if not saw_state_key:
                expected_keys = ",".join(label_to_state_keys.get(label, ()))
                mismatches.append(f"state_keys_missing:{label}:{expected_keys}")
        last = {
            "widget_values": widget_values,
            "browser_state": state,
            "shared_probe": shared,
            "summary_probe": summary,
            "mismatches": mismatches,
        }
        if not mismatches:
            return last
        page.wait_for_timeout(750)
    return last


def _blocked_card_has_specific_reason(card_text: str, attrs: dict[str, Any] | None = None) -> bool:
    lower = str(card_text or "").lower()
    attrs_d = dict(attrs or {})
    is_blocked = bool(
        "blocked" in lower
        or str(attrs_d.get("data-visible-badge") or "").strip().upper() == "BLOCKED"
        or str(attrs_d.get("data-visible-exact-blocker") or "").strip().lower() == "true"
    )
    if not is_blocked:
        return True
    return bool(
        "repair search exhausted" in lower
        or "safe executable candidates" in lower
        or "attempted moves:" in lower
        or "maximum depth reached" in lower
        or "maximum width reached" in lower
        or "non-terminal" in lower
        or "target-band or exact-stop proof" in lower
    )


def _run_case(page, base_url: str, case: dict[str, Any], *, timeout_s: float) -> dict[str, Any]:
    case_id = str(case["case_id"])
    seed_recipe = str(case["seed_recipe"])
    expected_families = {str(value).upper() for value in case["expected_families"]}
    typed_inputs = {str(k): float(v) for k, v in dict(case["inputs"]).items()}
    row: dict[str, Any] = {
        "case_id": case_id,
        "seed_recipe": seed_recipe,
        "typed_inputs": typed_inputs,
        "expected_families": sorted(expected_families),
        "failures": [],
    }
    page.goto(
        _query(
            base_url,
            {
                "page": "inputs",
                "browser_recipe": seed_recipe,
                "browser_test_mode": "1",
                "cid": case_id,
            },
        ),
        wait_until="domcontentloaded",
        timeout=90_000,
    )
    seed_card = _wait_for_final_card(page, timeout_s=timeout_s)
    row["seed_card"] = seed_card
    for label, value in typed_inputs.items():
        _set_number_input(page, label, value)
    state_probe = _wait_for_widget_and_state(page, typed_inputs, timeout_s=timeout_s, expected_cid=case_id)
    page.wait_for_timeout(1_500)
    final_card = _wait_for_final_card(page, timeout_s=timeout_s)
    final_state = _load_browser_state(page, expected_cid=case_id)
    browser_debug = dict(final_state.get("browser_debug_probe") or {})
    browser_last_action = dict(final_state.get("browser_recipe_last_action") or browser_debug.get("browser_recipe_last_action") or {})
    publication_family = _publication_family_from_state(final_state)
    visible_family = _visible_family_from_card(str(final_card.get("text") or ""), dict(final_card.get("attrs") or {}))
    row.update(
        {
            "state_probe": {
                "widget_values": state_probe.get("widget_values"),
                "shared_probe_subset": {
                    key: dict(state_probe.get("shared_probe") or {}).get(key)
                    for key in (
                        "uls_Mstar_pos_manual",
                        "uls_Vstar",
                        "load_Mstar_pos_proxy",
                        "load_Vstar_proxy",
                        "inputs_load_Mstar_pos_proxy",
                        "inputs_load_Vstar_proxy",
                    )
                },
                "mismatches": state_probe.get("mismatches"),
            },
            "final_card": final_card,
            "publication_family": publication_family,
            "visible_family": visible_family,
            "browser_recipe_last_action": browser_last_action,
            "publication_hash": dict(final_state.get("final_publication_verifier_payload") or {}).get("publication_hash")
            or dict(final_card.get("attrs") or {}).get("data-publication-hash"),
        }
    )
    widget_edit_map = {
        "Positive design moment Mu*+ (kNm)": "inputs_load_Mstar_pos_proxy",
        "Design shear Vu* (kN)": "inputs_load_Vstar_proxy",
    }
    user_widget_edits = dict(browser_last_action.get("user_widget_edits") or {})
    row["session_widget_edit_probe"] = {
        label: dict(user_widget_edits.get(widget_key) or {})
        for label, widget_key in widget_edit_map.items()
        if label in typed_inputs
    }
    if not seed_card.get("ready"):
        row["failures"].append("seed_final_card_not_ready")
    if state_probe.get("mismatches"):
        row["failures"].append("typed_widget_values_not_reflected_in_state")
    if str(browser_last_action.get("action") or "") != "skip_user_widget_edit":
        row["failures"].append("browser_recipe_did_not_yield_to_user_widget_edit")
    for label, expected in typed_inputs.items():
        widget_key = widget_edit_map.get(label)
        if not widget_key:
            continue
        edit_probe = dict(user_widget_edits.get(widget_key) or {})
        if not _values_match(edit_probe.get("current"), expected):
            row["failures"].append(f"session_widget_edit_probe_missing:{widget_key}")
    if publication_family not in expected_families and visible_family not in expected_families:
        row["failures"].append(
            f"family_mismatch:publication={publication_family or '<missing>'}:visible={visible_family or '<missing>'}"
        )
    if publication_family and visible_family and publication_family != visible_family:
        row["failures"].append(
            f"visible_publication_family_drift:publication={publication_family}:visible={visible_family}"
        )
    if bool(case.get("requires_cleanup_action")):
        final_text = str(final_card.get("text") or "").lower()
        attrs = dict(final_card.get("attrs") or {})
        cleanup_text = "cleanup" in final_text or "reduce" in final_text
        cta_enabled = str(attrs.get("data-render-cta-enabled") or "").strip().lower() == "true"
        exact_blocker = str(attrs.get("data-visible-exact-blocker") or "").strip().lower() == "true"
        if not cleanup_text:
            row["failures"].append("cleanup_route_text_missing")
        if not cta_enabled and not exact_blocker:
            row["failures"].append("cleanup_route_cta_not_enabled")
        if not cta_enabled and "safe one-click cleanup is available" in final_text:
            row["failures"].append("disabled_cleanup_still_claims_safe_one_click")
    if not final_card.get("ready"):
        row["failures"].append("final_card_not_ready_after_widget_edit")
    if not row.get("publication_hash"):
        row["failures"].append("publication_hash_missing_after_widget_edit")
    if not _blocked_card_has_specific_reason(str(final_card.get("text") or ""), dict(final_card.get("attrs") or {})):
        row["failures"].append("blocked_card_lacks_specific_reason")
    row["passed"] = not row["failures"]
    return row


def _write(snapshot: dict) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_widget_origin_mixed_family_live_fuzz_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_widget_origin_mixed_family_live_fuzz_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Design Guide Widget-Origin Mixed Family Live Fuzz",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Rows",
                "",
                *[
                    (
                        f"- `{row['case_id']}`: passed=`{row['passed']}` "
                        f"publication_family=`{row.get('publication_family')}` "
                        f"visible_family=`{row.get('visible_family')}` "
                        f"failures=`{row.get('failures')}`"
                    )
                    for row in snapshot["rows"]
                ],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8504")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout-s", type=float, default=45.0)
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        try:
            for case in MIXED_CASES:
                context = browser.new_context(viewport={"width": 1600, "height": 1100})
                page = context.new_page()
                page.set_default_timeout(30_000)
                try:
                    rows.append(_run_case(page, str(args.base_url), case, timeout_s=float(args.timeout_s)))
                except PlaywrightTimeoutError as exc:
                    rows.append(
                        {
                            "case_id": case.get("case_id"),
                            "seed_recipe": case.get("seed_recipe"),
                            "passed": False,
                            "failures": [f"playwright_timeout:{exc}"],
                        }
                    )
                except Exception as exc:
                    rows.append(
                        {
                            "case_id": case.get("case_id"),
                            "seed_recipe": case.get("seed_recipe"),
                            "passed": False,
                            "failures": [f"{type(exc).__name__}:{exc}"],
                        }
                    )
                finally:
                    context.close()
        finally:
            browser.close()
    failures = [row for row in rows if not row.get("passed")]
    snapshot = {
        "schema": "design_guide_widget_origin_mixed_family_live_fuzz.v1",
        "result": "PASS" if not failures and not errors else "FAIL",
        "base_url": args.base_url,
        "rows": rows,
        "failures": failures,
        "errors": errors,
    }
    json_path, report_path = _write(snapshot)
    if snapshot["result"] != "PASS":
        print("design guide widget-origin mixed family live fuzz FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True, default=str))
        return 1
    print("design guide widget-origin mixed family live fuzz PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
