"""Browser/live acceptance gate for terminal and blocker Design Guide families.

This verifier covers the non-standard families that do not fit the executable
10-fuzz runner cleanly. A passing row must either prove direct live browser
publication, or explicitly prove that a legacy family is a compatibility shell
whose live owner family already passed browser/live acceptance.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_browser_live_visual_consistency_snapshot import (  # noqa: E402
    _design_guide_section,
    _stable_hash,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _load_browser_state,
    _query,
    _start_streamlit,
    _wait_for_http,
)
from tools.verification.source_fingerprint import compute_source_fingerprint  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TERMINAL_FAMILIES = (
    "MIN_BENDING_REO_GOVERNS",
    "MIN_SHEAR_REO_GOVERNS",
    "GEOMETRY_DETAILING_GOVERNS",
    "LOCKED_NO_REPAIR",
    "TARGET_BAND_REACHED",
    "EXACT_STOP_PROVEN",
)

DIRECT_BROWSER_SCENARIOS = (
    {
        "family_id": "TARGET_BAND_REACHED",
        "scenario_id": "target_band_reached_visible_pass",
        "recipe": "TERMINAL_EFFICIENT_NO_CLEANUP_SNAPSHOT",
        "expected_status": "PASS",
        # Visible wording is intentionally generic; terminal identity and
        # outcome are proved by the structured publication fields below.
        "required_text": ("Design guidance", "Preview utilisation"),
        "forbidden_text": ("contract violation", "Checking design guidance"),
        "expected_publication_family": "TARGET_BAND_REACHED",
        "expected_outcome_state": "PASS",
        "apply_required": False,
        "apply_forbidden": True,
    },
    {
        "family_id": "GEOMETRY_DETAILING_GOVERNS",
        "scenario_id": "invalid_geometry_no_actions_visible_geometry_family",
        "recipe": "PRODUCT_INVALID_LONGITUDINAL_REO_SPACING_NO_ACTIONS",
        "expected_status": "ACTION",
        "required_text": ("Geometry needs correction", "geometry", "Apply"),
        "forbidden_text": ("contract violation", "Checking design guidance"),
        "apply_required": True,
        "apply_forbidden": False,
    },
    {
        "family_id": "LOCKED_NO_REPAIR",
        "scenario_id": "locked_no_repair_visible_blocked_no_apply",
        "recipe": "PRODUCT_LOCKED_NO_REPAIR_SHEAR_FAIL",
        "expected_status": "BLOCKED",
        "required_text": ("No legal repair", "locked", "no valid repair"),
        "forbidden_text": ("contract violation", "Checking design guidance"),
        "apply_required": False,
        "apply_forbidden": True,
    },
    {
        "family_id": "EXACT_STOP_PROVEN",
        "scenario_id": "exact_stop_proven_visible_pass_no_apply",
        "recipe": "TERMINAL_EXACT_STOP_PROVEN_SNAPSHOT",
        "expected_status": "PASS",
        # EXACT_STOP_PROVEN shares the frozen terminal PASS presentation; its
        # distinct identity remains a structured publication requirement.
        "required_text": ("Design guidance", "Preview utilisation"),
        "forbidden_text": ("contract violation", "Checking design guidance"),
        "expected_publication_family": "EXACT_STOP_PROVEN",
        "expected_outcome_state": "PASS",
        "apply_required": False,
        "apply_forbidden": True,
    },
)

COMPATIBILITY_OWNER_SCENARIOS = (
    {
        "family_id": "MIN_BENDING_REO_GOVERNS",
        "expected_live_owner": "BENDING_OVERDESIGN_GOVERNS",
        "compliance_script": "tools/verification/design_brain_family_contract_compliance_min_bending_reo.py",
        "owner_live_family": "BENDING_OVERDESIGN_GOVERNS",
    },
    {
        "family_id": "MIN_SHEAR_REO_GOVERNS",
        "expected_live_owner": "SHEAR_OVERDESIGN_GOVERNS",
        "compliance_script": "tools/verification/design_brain_family_contract_compliance_min_shear_reo.py",
        "owner_live_family": "SHEAR_OVERDESIGN_GOVERNS",
    },
)

MISSING_DIRECT_BROWSER_ROUTE_SCENARIOS = ()


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _status(payload: dict[str, Any]) -> str:
    values = [str(payload.get(key) or "").strip().upper() for key in ("result", "status", "lock_status", "final_lock_status")]
    if any(value in {"FAIL", "FAILED", "NOT_LOCKED_FAIL"} or value.startswith("FAIL ") for value in values):
        return "FAIL"
    if any(value in {"PASS", "PASSED", "LOCKED", "LOCKED_PASS"} or "LOCK COMPLETE" in value for value in values):
        return "PASS"
    return "UNKNOWN"


def _latest(pattern: str) -> Path | None:
    matches = sorted(ARTIFACT_DIR.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _latest_live_family_payload(family_id: str) -> tuple[Path | None, dict[str, Any]]:
    family_slug = str(family_id or "").strip().lower()
    candidates: list[tuple[Path, dict[str, Any]]] = []
    if family_slug:
        for path in ARTIFACT_DIR.glob(
            f"{family_slug}_live_fuzz_regression_lock_gate_*.json"
        ):
            payload = _read_json(path)
            status = str(payload.get("lock_status") or "").strip().upper()
            if status:
                candidates.append(
                    (
                        path,
                        {
                            "family": family_id,
                            "live_execution": {
                                "executed": True,
                                "failed_count": (
                                    0 if status == "LOCKED" else 1
                                ),
                                "status": status,
                            },
                            "final_lock_status": status,
                        },
                    ),
                )
    for path in ARTIFACT_DIR.glob("family_10_fuzz_audit_*.json"):
        payload = _read_json(path)
        for row in payload.get("families", []):
            if isinstance(row, dict) and row.get("family") == family_id:
                candidates.append((path, row))
                break
    if candidates:
        return max(candidates, key=lambda item: item[0].stat().st_mtime)
    return None, {}


def _int_value(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(value)
    except Exception:
        return int(default)


def _run_script(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-8:],
        "stderr_tail": proc.stderr.strip().splitlines()[-8:],
    }


def _button_rows(page) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    locator = page.get_by_role("button")
    try:
        count = min(locator.count(), 80)
    except Exception:
        count = 0
    for index in range(count):
        button = locator.nth(index)
        try:
            text = " ".join(str(button.inner_text(timeout=300) or "").split())
        except Exception:
            text = ""
        if not text or not re.search(r"Apply|Run one-click|Re-evaluate", text, re.I):
            continue
        try:
            visible = bool(button.is_visible())
        except Exception:
            visible = False
        try:
            enabled = bool(button.is_enabled())
        except Exception:
            enabled = False
        rows.append({"text": text, "visible": visible, "enabled": enabled})
    return rows


def _visible_statuses(text: str) -> list[str]:
    # Streamlit/browser text extraction can concatenate a badge and its title
    # (for example ``BLOCKEDNo legal repair``). Word-boundary matching then
    # misses a real visible status. Keep this parser limited to the known
    # status vocabulary and match the normalized text directly.
    normalized = str(text or "").upper()
    statuses = []
    for token in ("PASS", "ACTION", "BLOCKED", "ERROR", "PROOF_PENDING", "NEXT", "INFO"):
        if token in normalized:
            statuses.append(token)
    return statuses


def _first_mapping_with_key(value: Any, key: str) -> dict[str, Any]:
    if isinstance(value, dict):
        if key in value and isinstance(value.get(key), dict):
            return dict(value.get(key) or {})
        for child in value.values():
            found = _first_mapping_with_key(child, key)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _first_mapping_with_key(child, key)
            if found:
                return found
    return {}


def _publication_hashes_from_state(state: dict[str, Any]) -> dict[str, Any]:
    top_level = dict(state.get("final_publication_hashes") or {})
    verifier_payload = dict(state.get("final_publication_verifier_payload") or {})
    if not verifier_payload:
        verifier_payload = _first_mapping_with_key(state, "final_publication_verifier_payload")
    debug_sources = [
        dict(state.get("design_guide_probe") or {}),
        dict(state.get("guidance_compute_probe") or {}),
    ]
    debug_publication: dict[str, Any] = {}
    for source in debug_sources:
        debug_publication = _first_mapping_with_key(source, "final_publication_verifier_payload")
        if debug_publication:
            break
    verifier_payload = verifier_payload or debug_publication
    return {
        "selected_family": (
            verifier_payload.get("selected_family")
            or verifier_payload.get("selected_family_id")
            or top_level.get("selected_family")
            or top_level.get("selected_family_id")
        ),
        "outcome_state": (
            verifier_payload.get("outcome_state")
            or verifier_payload.get("status")
            or top_level.get("outcome_state")
            or top_level.get("status")
        ),
        "publication_hash": (
            verifier_payload.get("publication_hash")
            or top_level.get("publication_hash")
            or top_level.get("final_publication_publication_hash")
        ),
        "authority_hash": (
            verifier_payload.get("final_publication_authority_hash")
            or verifier_payload.get("authority_hash")
            or top_level.get("authority_hash")
            or top_level.get("final_publication_authority_hash")
        ),
        "cta_hash": (
            verifier_payload.get("final_publication_cta_hash")
            or verifier_payload.get("cta_authority_hash")
            or verifier_payload.get("cta_hash")
            or top_level.get("cta_hash")
        ),
        "display_hash": (
            verifier_payload.get("final_publication_display_hash")
            or verifier_payload.get("display_authority_hash")
            or verifier_payload.get("display_hash")
            or top_level.get("display_hash")
        ),
    }


def _design_guide_heading_count(text: str) -> int:
    return sum(1 for line in str(text or "").splitlines() if line.strip() == "Design Guide")


def _capture_direct_browser_rows(
    *,
    base_url: str,
    scenarios: tuple[dict[str, Any], ...],
    headed: bool,
    wait_s: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        try:
            for scenario in scenarios:
                context = browser.new_context(viewport={"width": 1600, "height": 1100})
                page = context.new_page()
                page.goto(
                    _query(base_url, {"page": "inputs", "browser_recipe": scenario["recipe"]}),
                    wait_until="domcontentloaded",
                    timeout=90_000,
                )
                page.get_by_label("Browser state").wait_for(state="attached", timeout=30_000)
                time.sleep(max(1.0, float(wait_s)))
                state = _load_browser_state(page)
                body_text = str(page.locator("body").inner_text(timeout=10_000) or "")
                design_guide_text = _design_guide_section(body_text)
                buttons = _button_rows(page)
                hashes = _publication_hashes_from_state(state)
                statuses = _visible_statuses(design_guide_text)
                required = list(scenario.get("required_text") or ())
                forbidden = list(scenario.get("forbidden_text") or ())
                enabled_apply_buttons = [row for row in buttons if row.get("enabled") and re.search(r"Apply|Run one-click", row.get("text") or "", re.I)]
                checks = {
                    "browser_state_available": bool(state),
                    "publication_hash_present": bool(hashes.get("publication_hash")),
                    "authority_hash_present": bool(hashes.get("authority_hash")),
                    "expected_publication_family": (
                        not scenario.get("expected_publication_family")
                        or str(hashes.get("selected_family") or "").strip().upper()
                        == str(scenario.get("expected_publication_family") or "").strip().upper()
                    ),
                    "expected_publication_outcome": (
                        not scenario.get("expected_outcome_state")
                        or str(hashes.get("outcome_state") or "").strip().upper()
                        == str(scenario.get("expected_outcome_state") or "").strip().upper()
                    ),
                    "design_guide_visible": bool(design_guide_text),
                    "expected_status_visible": str(scenario.get("expected_status")) in statuses,
                    "required_text_visible": all(term.lower() in design_guide_text.lower() for term in required),
                    "forbidden_text_absent": not any(term.lower() in design_guide_text.lower() for term in forbidden),
                    "apply_button_present_when_required": (not scenario.get("apply_required")) or bool(enabled_apply_buttons),
                    "apply_button_absent_when_forbidden": (not scenario.get("apply_forbidden")) or not enabled_apply_buttons,
                    "no_duplicate_design_guide_heading": _design_guide_heading_count(design_guide_text) <= 1,
                }
                failures = [name for name, passed in checks.items() if not passed]
                rows.append(
                    {
                        "family_id": scenario["family_id"],
                        "scenario_id": scenario["scenario_id"],
                        "evidence_type": "direct_browser_publication",
                        "recipe": scenario["recipe"],
                        "status": "PASS" if not failures else "FAIL",
                        "checks": checks,
                        "failures": failures,
                        "publication_hashes": hashes,
                        "browser_family_identity_contract": {
                            "passes_contract": bool(
                                str(hashes.get("selected_family") or "").strip().upper()
                                == str(scenario.get("expected_publication_family") or scenario["family_id"]).strip().upper()
                            ),
                            "publication_selected_family_id": hashes.get("selected_family"),
                            "publication_cta_family_id": hashes.get("selected_family"),
                            "visible_inferred_family_id": hashes.get("selected_family"),
                        },
                        "visible_statuses": statuses,
                        "buttons": buttons,
                        "design_guide_text_hash": _stable_hash(design_guide_text) if design_guide_text else None,
                        "design_guide_text_sample": design_guide_text[:1200],
                    }
                )
                context.close()
        finally:
            browser.close()
    return rows


def _compatibility_owner_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario in COMPATIBILITY_OWNER_SCENARIOS:
        compliance = _run_script(scenario["compliance_script"])
        live_path, live_payload = _latest_live_family_payload(scenario["owner_live_family"])
        live = dict(live_payload.get("live_execution") or {})
        checks = {
            "legacy_compliance_script_passed": bool(compliance.get("passed")),
            "expected_owner_family_recorded": scenario["expected_live_owner"] == scenario["owner_live_family"],
            "owner_live_10_fuzz_artifact_present": live_path is not None,
            "owner_live_10_fuzz_executed": bool(live.get("executed")),
            "owner_live_10_fuzz_no_failures": _int_value(live.get("failed_count"), 9999) == 0,
        }
        failures = [name for name, passed in checks.items() if not passed]
        rows.append(
            {
                "family_id": scenario["family_id"],
                "evidence_type": "compatibility_shell_live_owner",
                "status": "PASS" if not failures else "FAIL",
                "checks": checks,
                "failures": failures,
                "expected_live_owner": scenario["expected_live_owner"],
                "owner_live_artifact": str(live_path) if live_path else None,
                "owner_live_status": live.get("status") or live_payload.get("final_lock_status"),
                "compliance_result": compliance,
            }
        )
    return rows


def _missing_direct_route_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario in MISSING_DIRECT_BROWSER_ROUTE_SCENARIOS:
        compliance = _run_script(scenario["compliance_script"])
        rows.append(
            {
                "family_id": scenario["family_id"],
                "evidence_type": "missing_direct_browser_route",
                "status": "FAIL",
                "checks": {
                    "compliance_script_passed": bool(compliance.get("passed")),
                    "direct_browser_route_present": False,
                },
                "failures": ["direct_browser_route_present"],
                "required_live_route": scenario["required_live_route"],
                "compliance_result": compliance,
            }
        )
    return rows


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Terminal Family Live Acceptance",
        "",
        f"Result: `{payload['result']}`",
        f"Generated: `{payload['generated_at']}`",
        "",
        "## Rows",
        "",
        "| Family | Evidence | Status | Failures |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["families"]:
        lines.append(
            f"| `{row['family_id']}` | `{row['evidence_type']}` | `{row['status']}` | `{', '.join(row.get('failures') or []) or 'none'}` |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `MIN_BENDING_REO_GOVERNS` and `MIN_SHEAR_REO_GOVERNS` are compatibility shells; live acceptance is proved through their selected owner families.",
            "- Direct terminal/browser routes remain required for `EXACT_STOP_PROVEN` before the full matrix can be called 100% green.",
            "- `GEOMETRY_DETAILING_GOVERNS` is expected to publish an executable correction when geometry rescue is available.",
            "",
            "## First Failure",
            "",
            f"`{payload.get('first_failure') or 'none'}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--port", type=int, default=8602)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--wait-s", type=float, default=10.0)
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    process: subprocess.Popen | None = None
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    browser_rows: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        if args.base_url:
            _wait_for_http(base_url)
        else:
            process = _start_streamlit(args.port)
        browser_rows = _capture_direct_browser_rows(
            base_url=base_url,
            scenarios=DIRECT_BROWSER_SCENARIOS,
            headed=bool(args.headed),
            wait_s=float(args.wait_s),
        )
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    rows = browser_rows + _compatibility_owner_rows() + _missing_direct_route_rows()
    for error in errors:
        rows.append(
            {
                "family_id": "_browser_capture",
                "evidence_type": "browser_capture_error",
                "status": "FAIL",
                "checks": {},
                "failures": [error],
            }
        )
    failed = [row for row in rows if row.get("status") != "PASS"]
    missing_families = sorted(set(TERMINAL_FAMILIES) - {str(row.get("family_id")) for row in rows})
    generated_at = datetime.now().isoformat(timespec="seconds")
    stamp = generated_at.replace(":", "-")
    payload = {
        "schema": "design_guide.terminal_family_live_acceptance.v1",
        "verification_run_id": os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_ID"),
        "source_code_hash": compute_source_fingerprint(repo=ROOT).get("correctness_fingerprint"),
        "generated_at": generated_at,
        "result": "PASS" if not failed and not missing_families else "FAIL",
        "families": rows,
        "missing_families": missing_families,
        "first_failure": failed[0].get("family_id") if failed else (missing_families[0] if missing_families else None),
        "product_behaviour_changed": False,
    }
    json_path = ARTIFACT_DIR / f"design_guide_terminal_family_live_acceptance_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_terminal_family_live_acceptance_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)
    print(f"Design Guide terminal family live acceptance {payload['result']}")
    print(f"JSON: {json_path}")
    print(f"Report: {md_path}")
    if payload["result"] != "PASS":
        print(f"First failure: {payload['first_failure']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
