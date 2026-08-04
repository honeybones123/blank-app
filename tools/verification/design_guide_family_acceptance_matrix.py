"""Strict Design Guide family acceptance matrix.

This is the top-level gate for the user-facing Design Guide promise:
every family must either publish an executable recommendation that applies
cleanly, or publish an exact engineering blocker/terminal state with no fake
CTA. Missing live evidence is a failure, not an accepted drift.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERIFY_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

EXECUTABLE_FAMILIES = (
    "BENDING_FAIL_GOVERNS",
    "SHEAR_FAIL_GOVERNS",
    "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    "BENDING_OVERDESIGN_GOVERNS",
    "SHEAR_OVERDESIGN_GOVERNS",
    "COMBINED_OVERDESIGN_GOVERNS",
)

LIVE_NON_ACTION_FAMILIES = (
    "SERVICEABILITY_GOVERNS",
)

TERMINAL_OR_BLOCKER_FAMILIES = (
    "MIN_BENDING_REO_GOVERNS",
    "MIN_SHEAR_REO_GOVERNS",
    "GEOMETRY_DETAILING_GOVERNS",
    "LOCKED_NO_REPAIR",
    "TARGET_BAND_REACHED",
    "EXACT_STOP_PROVEN",
)

ALL_FAMILIES = EXECUTABLE_FAMILIES + LIVE_NON_ACTION_FAMILIES + TERMINAL_OR_BLOCKER_FAMILIES

COMPLIANCE_SCRIPTS = {
    "MIN_BENDING_REO_GOVERNS": "tools/verification/design_brain_family_contract_compliance_min_bending_reo.py",
    "MIN_SHEAR_REO_GOVERNS": "tools/verification/design_brain_family_contract_compliance_min_shear_reo.py",
    "GEOMETRY_DETAILING_GOVERNS": "tools/verification/design_brain_family_contract_compliance_geometry_detailing.py",
    "LOCKED_NO_REPAIR": "tools/verification/design_brain_family_contract_compliance_locked_no_repair.py",
    "TARGET_BAND_REACHED": "tools/verification/design_brain_family_contract_compliance_target_band_reached.py",
    "EXACT_STOP_PROVEN": "tools/verification/design_brain_family_contract_compliance_exact_stop_proven.py",
}

LOCK_PATTERNS = {
    "BENDING_FAIL_GOVERNS": ("bending_fail_governs_lock_verifier_*.json",),
    "SHEAR_FAIL_GOVERNS": ("shear_fail_governs_lock_verifier_*.json",),
    "BENDING_OVERDESIGN_GOVERNS": ("bending_overdesign_governs_lock_verifier_*.json",),
    "SHEAR_OVERDESIGN_GOVERNS": ("shear_overdesign_governs_lock_verifier_*.json",),
    "COMBINED_BENDING_SHEAR_FAIL_GOVERNS": (
        "combined_bending_shear_fail_governs_lock_verifier_*.json",
        "combined_bending_shear_fail_lock_verifier_*.json",
    ),
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS": (
        "bending_fail_shear_overdesign_governs_lock_verifier_*.json",
    ),
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": (
        "shear_fail_bending_overdesign_governs_lock_verifier_*.json",
    ),
    "COMBINED_OVERDESIGN_GOVERNS": ("combined_overdesign_governs_lock_verifier_*.json",),
}


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _latest(pattern: str) -> Path | None:
    matches = sorted(VERIFY_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _status(payload: dict[str, Any]) -> str:
    values = [str(payload.get(key) or "").strip().upper() for key in ("result", "status", "lock_status")]
    if any(value in {"FAIL", "FAILED"} or value.startswith("FAIL ") for value in values):
        return "FAIL"
    if any(
        value in {"PASS", "PASSED", "LOCKED", "COMPLETE"}
        or value.endswith(" LOCK COMPLETE")
        or value.endswith(" LOCKED")
        or " LOCK COMPLETE" in value
        for value in values
    ):
        return "PASS"
    return "UNKNOWN"


def _latest_lock(family_id: str) -> tuple[Path | None, str]:
    for pattern in LOCK_PATTERNS.get(family_id, ()):
        path = _latest(pattern)
        if path is not None:
            return path, _status(_read_json(path))
    return None, "MISSING"


def _latest_live_family_payload(family_id: str) -> tuple[Path | None, dict[str, Any]]:
    for path in sorted(VERIFY_DIR.glob("family_10_fuzz_audit_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        payload = _read_json(path)
        for row in payload.get("families", []):
            if isinstance(row, dict) and row.get("family") == family_id:
                return path, row
    return None, {}


def _row_bool(row: dict[str, Any], key: str, default: bool = False) -> bool:
    value = row.get(key)
    if value is None:
        return default
    return bool(value)


def _row_has_blocker_or_target_proof(row: dict[str, Any]) -> bool:
    text_parts = [
        json.dumps(row.get("post_apply_final_card_probe") or {}, sort_keys=True, default=str),
        json.dumps(row.get("final_card_probe") or {}, sort_keys=True, default=str),
        json.dumps(row.get("candidate_search_evidence_before") or {}, sort_keys=True, default=str),
        json.dumps(row.get("publication_probe_before") or {}, sort_keys=True, default=str),
    ]
    text = " ".join(text_parts).lower()
    return any(
        token in text
        for token in (
            "target_band",
            "target band",
            "exact",
            "blocker",
            "exhaust",
            "not reachable",
            "not reach",
            "minimum",
            "detailing",
            "locked",
        )
    )


def _int_value(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(value)
    except Exception:
        return int(default)


def _executable_family_row(family_id: str) -> dict[str, Any]:
    lock_path, lock_status = _latest_lock(family_id)
    live_path, live_payload = _latest_live_family_payload(family_id)
    live = dict(live_payload.get("live_execution") or {})
    rows = [row for row in live.get("rows", []) if isinstance(row, dict)]
    checks: dict[str, bool] = {
        "family_lock_pass": lock_status == "PASS",
        "live_10_fuzz_artifact_present": live_path is not None,
        "live_10_fuzz_executed": bool(live.get("executed")),
        "live_10_fuzz_has_10_scenarios": _int_value(live.get("scenario_count"), 0) >= 10,
        "live_10_fuzz_no_failures": _int_value(live.get("failed_count"), 9999) == 0,
        "family_selected_or_runner_scoped": bool(rows) and all(row.get("family") == family_id for row in rows),
        "contract_ladder_or_best_candidate_proof_present": bool(
            live_payload.get("best_candidate_proof")
            or live_payload.get("ladder_candidates_considered")
            or live_payload.get("winning_candidate")
        ),
        "apply_button_present_when_executable": bool(rows)
        and all(int((row.get("button_probe_before") or {}).get("enabled_action_count") or 0) >= 1 for row in rows),
        "apply_clicked_when_executable": bool(rows)
        and all(bool((row.get("click_result") or {}).get("clicked")) for row in rows),
        "final_card_not_stale_or_shell": bool(rows)
        and all(bool((row.get("post_apply_final_card_probe") or {}).get("final_card_ready")) for row in rows),
        "post_apply_target_or_engineering_blocker_proven": bool(rows)
        and all(
            bool((row.get("post_apply_green_pass_visual_contract") or {}).get("passes_contract"))
            or _row_has_blocker_or_target_proof(row)
            for row in rows
        ),
        "no_contract_violation_shell": bool(rows)
        and all("contract violation" not in json.dumps(row, sort_keys=True, default=str).lower() for row in rows),
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "family_id": family_id,
        "family_type": "executable",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "lock_artifact": str(lock_path) if lock_path else None,
        "live_artifact": str(live_path) if live_path else None,
        "live_status": live.get("status") or live_payload.get("status_note"),
        "scenario_count": live.get("scenario_count"),
        "failed_count": live.get("failed_count"),
        "sample_failure_reasons": sorted(
            {
                str(reason)
                for row in rows
                for reason in list(row.get("failures") or [])
            }
        )[:12],
    }


def _live_non_action_family_row(family_id: str) -> dict[str, Any]:
    live_path, live_payload = _latest_live_family_payload(family_id)
    live = dict(live_payload.get("live_execution") or {})
    rows = [row for row in live.get("rows", []) if isinstance(row, dict)]
    path = _latest("serviceability_governs_lock_verifier_*.json") or _latest("serviceability_governs_locked_regression_*.json")
    payload = _read_json(path)
    checks = {
        "family_lock_or_regression_pass": _status(payload) == "PASS",
        "live_10_fuzz_artifact_present": live_path is not None,
        "live_10_fuzz_executed": bool(live.get("executed")),
        "live_10_fuzz_has_10_scenarios": _int_value(live.get("scenario_count"), 0) >= 10,
        "live_10_fuzz_no_failures": _int_value(live.get("failed_count"), 9999) == 0,
        "family_selected_or_runner_scoped": bool(rows) and all(row.get("family") == family_id for row in rows),
        "final_card_not_stale_or_shell": bool(rows)
        and all(bool((row.get("final_card_probe") or {}).get("final_card_ready")) for row in rows),
        "no_contract_violation_shell": bool(rows)
        and all("contract violation" not in json.dumps(row, sort_keys=True, default=str).lower() for row in rows),
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "family_id": family_id,
        "family_type": "live_non_action",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "live_artifact": str(live_path) if live_path else None,
        "lock_artifact": str(path) if path else None,
        "live_status": live.get("status") or live_payload.get("status_note"),
        "scenario_count": live.get("scenario_count"),
        "failed_count": live.get("failed_count"),
        "sample_failure_reasons": sorted(
            {
                str(reason)
                for row in rows
                for reason in list(row.get("failures") or [])
            }
        )[:12],
    }


def _run_script(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-8:],
        "stderr_tail": proc.stderr.strip().splitlines()[-8:],
    }


def _terminal_family_row(family_id: str, *, run_compliance: bool) -> dict[str, Any]:
    script = COMPLIANCE_SCRIPTS.get(family_id)
    result = _run_script(script) if run_compliance and script else {}
    terminal_live_path = _latest("design_guide_terminal_family_live_acceptance_*.json")
    terminal_live_payload = _read_json(terminal_live_path)
    terminal_live_row = next(
        (
            row
            for row in terminal_live_payload.get("families", [])
            if isinstance(row, dict) and row.get("family_id") == family_id
        ),
        {},
    )
    checks = {
        "compliance_script_exists_or_serviceability_terminal": bool(script) or family_id == "SERVICEABILITY_GOVERNS",
        "compliance_script_passed": bool(result.get("passed")) if script and run_compliance else False,
        "terminal_live_acceptance_artifact_present": terminal_live_path is not None,
        "terminal_live_acceptance_family_row_present": bool(terminal_live_row),
        "terminal_live_acceptance_passed": terminal_live_row.get("status") == "PASS",
        "no_executable_live_apply_required": True,
    }
    if family_id == "SERVICEABILITY_GOVERNS":
        # Serviceability currently has family verifier coverage under families/.
        path = _latest("serviceability_governs_lock_verifier_*.json") or _latest("serviceability_governs_locked_regression_*.json")
        payload = _read_json(path)
        checks["compliance_script_passed"] = _status(payload) == "PASS"
        result = {"script": "serviceability lock/regression artifact", "passed": checks["compliance_script_passed"], "artifact": str(path) if path else None}
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "family_id": family_id,
        "family_type": "terminal_or_blocker",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "compliance_result": result,
        "terminal_live_artifact": str(terminal_live_path) if terminal_live_path else None,
        "terminal_live_row": terminal_live_row,
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Family Acceptance Matrix",
        "",
        f"Result: `{payload['result']}`",
        f"Generated: `{payload['generated_at']}`",
        f"Families passing: `{payload['summary']['passed']}/{payload['summary']['total']}`",
        "",
        "## Matrix",
        "",
        "| Family | Type | Status | Failed checks | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["families"]:
        failed = ", ".join(row.get("failures") or []) or "none"
        evidence = (
            row.get("live_artifact")
            or row.get("terminal_live_artifact")
            or row.get("lock_artifact")
            or (row.get("compliance_result") or {}).get("artifact")
            or ""
        )
        lines.append(
            f"| `{row['family_id']}` | `{row['family_type']}` | `{row['status']}` | {failed} | `{evidence}` |"
        )
    lines.extend(
        [
            "",
            "## First Failing Family",
            "",
            f"`{payload['first_failing_family'] or 'none'}`",
            "",
            "## Next Fix",
            "",
            payload["next_fix"],
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    VERIFY_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    families = [_executable_family_row(family_id) for family_id in EXECUTABLE_FAMILIES]
    families.extend(_live_non_action_family_row(family_id) for family_id in LIVE_NON_ACTION_FAMILIES)
    families.extend(
        _terminal_family_row(family_id, run_compliance=True)
        for family_id in TERMINAL_OR_BLOCKER_FAMILIES
    )
    failed = [row for row in families if row["status"] != "PASS"]
    payload = {
        "schema": "design_guide.family_acceptance_matrix.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "result": "PASS" if not failed else "FAIL",
        "summary": {
            "total": len(families),
            "passed": len(families) - len(failed),
            "failed": len(failed),
            "executable_families": len(EXECUTABLE_FAMILIES),
            "live_non_action_families": len(LIVE_NON_ACTION_FAMILIES),
            "terminal_or_blocker_families": len(TERMINAL_OR_BLOCKER_FAMILIES),
        },
        "families": families,
        "first_failing_family": failed[0]["family_id"] if failed else None,
        "next_fix": (
            "Run and fix the first failing family live 10-fuzz path until it proves selected family, "
            "contract ladder, enabled Apply CTA when executable, post-apply mutation, and target-band "
            "or exact blocker publication. Do not delete old code while this matrix is red."
            if failed
            else "All family acceptance rows are green; deletion/smoothness cleanup may be considered."
        ),
        "product_behavior_changed": False,
    }
    json_path = VERIFY_DIR / f"design_guide_family_acceptance_matrix_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_family_acceptance_matrix_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"Design Guide family acceptance matrix {payload['result']}")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    if failed:
        print(f"First failing family: {failed[0]['family_id']}")
        print(f"Failures: {', '.join(failed[0]['failures'])}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
