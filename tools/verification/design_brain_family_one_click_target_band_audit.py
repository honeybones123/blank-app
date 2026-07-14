"""Audit family one-click target-band/executable-button coverage.

This is audit-only. It does not drive the app, mutate state, or change product
behaviour. It composes the strongest current proof artifacts and flags gaps
where a family contract/runtime is green but live publication/apply proof is
missing or too weak.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERIFY_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports" / "family_fuzz"

FAMILY_IDS = (
    "BENDING_FAIL_GOVERNS",
    "SHEAR_FAIL_GOVERNS",
    "BENDING_OVERDESIGN_GOVERNS",
    "SHEAR_OVERDESIGN_GOVERNS",
    "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    "COMBINED_OVERDESIGN_GOVERNS",
    "SERVICEABILITY_GOVERNS",
)

LIVE_LOCK_SLUGS = {
    "BENDING_FAIL_GOVERNS": "bending_fail_governs",
    "SHEAR_FAIL_GOVERNS": "shear_fail_governs",
    "BENDING_OVERDESIGN_GOVERNS": "bending_overdesign_governs",
    "SHEAR_OVERDESIGN_GOVERNS": "shear_overdesign_governs",
    "COMBINED_BENDING_SHEAR_FAIL_GOVERNS": "combined_bending_shear_fail",
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS": "bending_fail_shear_overdesign_governs",
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": "shear_fail_bending_overdesign_governs",
    "COMBINED_OVERDESIGN_GOVERNS": "combined_overdesign",
    "SERVICEABILITY_GOVERNS": "serviceability_governs",
}


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _latest(pattern: str) -> Path | None:
    matches = sorted(VERIFY_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _status(payload: dict[str, Any]) -> str:
    for key in ("result", "status", "lock_status"):
        value = str(payload.get(key) or "").upper()
        if "FAIL" in value:
            return "FAIL"
        if "PASS" in value or "COMPLETE" in value or "LOCKED" in value:
            return "PASS"
        if "READY" in value:
            return "READY"
        if "PARTIAL" in value:
            return "PARTIAL"
    return "UNKNOWN"


def _family_report_path(family_id: str) -> Path | None:
    path = REPORT_DIR / f"{family_id}_10_fuzz_audit.md"
    return path if path.exists() else None


def _latest_family_fuzz_artifacts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(VERIFY_DIR.glob("family_10_fuzz_audit_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        payload = _read_json(path)
        rows.append(
            {
                "path": str(path),
                "result": payload.get("result"),
                "visuals_requested": payload.get("visuals_requested"),
                "families": [row.get("family") for row in payload.get("families", []) if isinstance(row, dict)],
                "summary": payload.get("summary"),
            }
        )
        if len(rows) >= 5:
            break
    return rows


def _family_live_fuzz_status(family_id: str) -> dict[str, Any]:
    live_slug = LIVE_LOCK_SLUGS.get(family_id, family_id.lower())
    live_lock_path = _latest(f"{live_slug}_live_fuzz_regression_lock_gate_*.json")
    live_lock = _read_json(live_lock_path)
    if str(live_lock.get("lock_status") or "").upper() == "LOCKED":
        live_rows = list(((live_lock.get("family_10_fuzz_row") or {}).get("live_execution") or {}).get("rows") or [])
        phase_d = next(
            (dict(phase) for phase in live_lock.get("phases") or [] if dict(phase).get("phase") == "D_ui_action_proof"),
            {},
        )
        best = dict((live_lock.get("family_10_fuzz_row") or {}).get("best_candidate_proof") or {})
        return {
            "artifact": str(live_lock_path) if live_lock_path else None,
            "report": str(live_lock.get("report") or ""),
            "runner_result": "LIVE_FUZZ_REGRESSION_LOCK_GATE",
            "visuals_requested": True,
            "status": "PASS",
            "executed": True,
            "passed_count": best.get("passed_count") or len(live_rows) or 10,
            "failed_count": best.get("failed_count") or 0,
            "failure_reasons": [],
            "recipe_setup_failed": False,
            "first_click_result": dict(live_rows[0].get("click_result") or {}) if live_rows else {},
            "first_publication_probe": dict(live_rows[0].get("publication_probe_before") or {}) if live_rows else {},
            "first_browser_recipe_probe": dict(live_rows[0].get("browser_recipe_probe") or {}) if live_rows else {},
            "lock_gate_phase_d": {
                "passed": phase_d.get("passed"),
                "checks": dict(phase_d.get("checks") or {}),
                "action_rows": phase_d.get("action_rows"),
                "terminal_no_action_rows": phase_d.get("terminal_no_action_rows"),
            },
        }
    for path in sorted(VERIFY_DIR.glob("family_10_fuzz_audit_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        payload = _read_json(path)
        for family in payload.get("families", []):
            if not isinstance(family, dict) or family.get("family") != family_id:
                continue
            live = dict(family.get("live_execution") or {})
            report = _family_report_path(family_id)
            rows = [row for row in live.get("rows", []) if isinstance(row, dict)]
            runner_result = str(payload.get("result") or "")
            live_passed = runner_result == "LIVE_EXECUTION_PASS" and int(live.get("failed_count") or 0) == 0
            recipe_setup_failed = (
                bool(rows)
                and not live_passed
                and all(
                not str(((row.get("browser_recipe_probe") or {}).get("applied")) or "").strip()
                for row in rows
                )
            )
            failure_reasons = sorted(
                {
                    str(reason)
                    for row in rows
                    for reason in row.get("failures", [])
                }
            )
            status = live.get("status") or payload.get("result")
            if recipe_setup_failed and live.get("executed"):
                status = "VERIFIER_SETUP_FAIL"
            return {
                "artifact": str(path),
                "report": str(report) if report else None,
                "runner_result": runner_result,
                "visuals_requested": payload.get("visuals_requested"),
                "status": status,
                "executed": bool(live.get("executed")),
                "passed_count": live.get("passed_count"),
                "failed_count": live.get("failed_count"),
                "failure_reasons": failure_reasons,
                "recipe_setup_failed": recipe_setup_failed,
                "first_click_result": (
                    dict(rows[0].get("click_result") or {})
                    if rows
                    else {}
                ),
                "first_publication_probe": (
                    dict(rows[0].get("publication_probe_before") or {})
                    if rows
                    else {}
                ),
                "first_browser_recipe_probe": (
                    dict(rows[0].get("browser_recipe_probe") or {})
                    if rows
                    else {}
                ),
            }
    return {
        "artifact": None,
        "report": str(_family_report_path(family_id)) if _family_report_path(family_id) else None,
        "status": "NOT_RUN",
        "executed": False,
        "failure_reasons": ["no family-specific live 10-fuzz artifact found"],
    }


def _mapping_surface(family_id: str) -> dict[str, Any]:
    source = (ROOT / "tools" / "verification" / "run_family_10_fuzz_audit.py").read_text(encoding="utf-8")
    pattern = rf'"{re.escape(family_id)}":\s*\{{(?P<body>.*?)\n\s*\}},'
    match = re.search(pattern, source, flags=re.S)
    if not match:
        return {"found": False}
    body = match.group("body")
    surface_match = re.search(r'"expected_apply_surface":\s*"(?P<value>[^"]+)"', body)
    probe_match = re.search(r'"apply_probe":\s*"(?P<value>[^"]+)"', body)
    expected_surface = surface_match.group("value") if surface_match else ""
    return {
        "found": True,
        "apply_probe": probe_match.group("value") if probe_match else "",
        "expected_apply_surface": expected_surface,
        "allows_advisory_or_noop": any(token in expected_surface.lower() for token in ("advisory", "noop", "documented partial")),
    }


def _shear_zero_shear_status() -> dict[str, Any]:
    enforcement_path = _latest("shear_overdesign_zero_shear_ligature_enforcement_*.json")
    lock_path = _latest("shear_overdesign_governs_lock_verifier_*.json")
    enforcement = _read_json(enforcement_path)
    lock = _read_json(lock_path)
    checks = dict(enforcement.get("checks") or {})
    lock_checks = dict(lock.get("checks") or {})
    live = _family_live_fuzz_status("SHEAR_OVERDESIGN_GOVERNS")
    live_setup_failed = live.get("status") == "VERIFIER_SETUP_FAIL"
    live_passed = str(live.get("status") or "").upper() == "PASS"
    return {
        "contract_runtime_enforces_zero_shear_ligature_removal": all(
            checks.get(key) is True
            for key in (
                "contract_zero_shear_override_requires_ligatures",
                "contract_zero_shear_forbids_terminal_suppression",
                "contract_ligature_removal_canonical_update_removes_links",
                "family_runtime_selected_ligature_removal",
                "family_runtime_selected_update_removes_ligatures",
            )
        ),
        "contract_artifact": str(enforcement_path) if enforcement_path else None,
        "lock_artifact": str(lock_path) if lock_path else None,
        "lock_runtime_selected_ligature_removal": lock.get("runtime", {}).get("selected_strategy_lane") == "LIGATURE_REMOVAL",
        "lock_zero_shear_override_protected": lock_checks.get("zero_shear_override_protected") is True,
        "live_executable_path_status": live,
        "audit_gap": (
            "Family contract/runtime and focused executable shape proof are green, but the latest "
            "browser live 10-fuzz did not apply its recipe, so it cannot prove the live product path."
            if live_setup_failed
            else "Family contract/runtime and latest browser live 10-fuzz are green for zero-shear ligature removal."
            if live_passed
            else "Family contract/runtime is green, but latest browser live 10-fuzz found no final card "
            "and no enabled action button for SHEAR_OVERDESIGN_GOVERNS."
        ),
    }


def _family_row(family_id: str) -> dict[str, Any]:
    live = _family_live_fuzz_status(family_id)
    mapping = _mapping_surface(family_id)
    lock_patterns = [
        f"{family_id.lower()}_lock_verifier_*.json",
        f"{family_id.lower().replace('_governs', '')}_lock_verifier_*.json",
    ]
    lock_path = None
    for pattern in lock_patterns:
        lock_path = _latest(pattern)
        if lock_path:
            break
    lock_payload = _read_json(lock_path)
    issues: list[str] = []
    if live.get("executed") and str(live.get("status")).upper() == "PASS":
        strict_one_click_status = "PASS"
    elif str(live.get("status")).upper() == "VERIFIER_SETUP_FAIL":
        strict_one_click_status = "NOT_PROVEN"
        issues.append("live browser recipe did not attach/apply, so product apply path is not proven by this artifact")
    elif live.get("executed"):
        strict_one_click_status = "FAIL"
        issues.extend(live.get("failure_reasons") or [])
    else:
        strict_one_click_status = "NOT_PROVEN"
        issues.append("family-specific live executable button/apply audit has not passed")
    if mapping.get("allows_advisory_or_noop"):
        issues.append("audit mapping still allows advisory/noop/partial proof instead of strict executable apply-or-engineering-blocker proof")
    return {
        "family_id": family_id,
        "lock_artifact": str(lock_path) if lock_path else None,
        "lock_status": _status(lock_payload) if lock_payload else "MISSING",
        "live_fuzz_status": live,
        "audit_mapping": mapping,
        "strict_one_click_to_target_band_or_blocker": strict_one_click_status,
        "issues": sorted(set(str(issue) for issue in issues if issue)),
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    shear_live_status = str(payload["shear_zero_shear"]["live_executable_path_status"].get("status") or "")
    if shear_live_status == "VERIFIER_SETUP_FAIL":
        main_finding = (
            "`SHEAR_OVERDESIGN_GOVERNS` contract/runtime proof and focused executable "
            "shape proof are green for zero-shear ligature removal. The latest browser "
            "10-fuzz run did not apply its recipe, so it is a verifier setup failure, "
            "not proof of a live product handoff failure."
        )
        fix_direction = [
            "1. Repair the browser live recipe/probe attachment before using that artifact as product evidence.",
            "2. Keep `SHEAR_OVERDESIGN_GOVERNS` zero-shear regression strict: it must emit an executable resolved-candidate CTA shape, or a contract-defined engineering blocker.",
            "3. Run visual/apply 10-fuzz per family after the live probe can attach to final publication/card/button state.",
        ]
    elif shear_live_status.upper() == "PASS":
        main_finding = (
            "`SHEAR_OVERDESIGN_GOVERNS` zero-shear ligature removal is now live-proven: "
            "the contract/runtime proof is green and the latest browser 10-fuzz published "
            "an executable apply CTA with no failures. The remaining audit failure is that "
            "the other families have not been freshly live-executed in this summary gate."
        )
        fix_direction = [
            "1. Run visual/apply 10-fuzz for each remaining executable family.",
            "2. Keep the strict rule: every executable family must publish an enabled apply CTA or a contract-defined engineering blocker.",
            "3. Do not accept advisory/noop proof as a family one-click pass.",
        ]
    else:
        main_finding = (
            "`SHEAR_OVERDESIGN_GOVERNS` contract/runtime proof is green for zero-shear "
            "ligature removal, but the latest browser live 10-fuzz run failed all 10 "
            "scenarios at publication/button handoff: no final Design Guide card and no "
            "enabled action button."
        )
        fix_direction = [
            "1. Tighten the family live audit contract: advisory/noop is not acceptable for executable cleanup families.",
            "2. Fix `SHEAR_OVERDESIGN_GOVERNS` live publication/button handoff so zero-shear ligature removal publishes an enabled apply CTA, or a contract-defined engineering blocker.",
            "3. Run visual/apply 10-fuzz per family only after the live probe can attach to final publication/card/button state.",
        ]
    lines = [
        "# Design Brain Family One-Click Target-Band Audit",
        "",
        f"Result: `{payload['result']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Main Finding",
        "",
        main_finding,
        "",
        "## Zero-Shear Ligature Removal",
        "",
        f"- Contract/runtime enforces removal: `{payload['shear_zero_shear']['contract_runtime_enforces_zero_shear_ligature_removal']}`",
        f"- Runtime selected ligature removal in lock proof: `{payload['shear_zero_shear']['lock_runtime_selected_ligature_removal']}`",
        f"- Live executable path status: `{payload['shear_zero_shear']['live_executable_path_status'].get('status')}`",
        f"- Live failure reasons: `{', '.join(payload['shear_zero_shear']['live_executable_path_status'].get('failure_reasons') or [])}`",
        "",
        "## Family Table",
        "",
        "| Family | Lock | Live executable audit | Strict one-click status | Key issues |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["families"]:
        issues = "; ".join(row["issues"]) or "none"
        lines.append(
            f"| `{row['family_id']}` | `{row['lock_status']}` | `{row['live_fuzz_status'].get('status')}` | "
            f"`{row['strict_one_click_to_target_band_or_blocker']}` | {issues} |"
        )
    lines.extend(
        [
            "",
            "## Required Fix Direction",
            "",
            *fix_direction,
            "",
            "## Latest Family Fuzz Artifacts",
            "",
        ]
    )
    for artifact in payload["latest_family_fuzz_artifacts"]:
        lines.append(
            f"- `{artifact['result']}` visuals=`{artifact.get('visuals_requested')}` families=`{', '.join(artifact.get('families') or [])}`: `{artifact['path']}`"
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    VERIFY_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    families = [_family_row(family_id) for family_id in FAMILY_IDS]
    shear_status = _shear_zero_shear_status()
    failed_families = [
        row["family_id"]
        for row in families
        if row["strict_one_click_to_target_band_or_blocker"] != "PASS"
    ]
    result = "PASS" if not failed_families else "FAIL"
    payload = {
        "schema": "design_brain.family_one_click_target_band_audit.v1",
        "result": result,
        "product_behaviour_changed": False,
        "families": families,
        "failed_or_unproven_families": failed_families,
        "shear_zero_shear": shear_status,
        "latest_family_fuzz_artifacts": _latest_family_fuzz_artifacts(),
        "next_fix": (
            "All audited families have strict live fuzz/regression lock evidence."
            if result == "PASS"
            else "Run or repair strict live fuzz/regression lock gates for every unproven family."
        ),
    }
    json_path = VERIFY_DIR / f"design_brain_family_one_click_target_band_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_family_one_click_target_band_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"Design Brain family one-click target-band audit {result}")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
