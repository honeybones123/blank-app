"""Permanent regression for SHEAR_FAIL_GOVERNS normal product routing.

This wrapper runs the normal product-path pure shear-underdesign scenario with
`CODEX_BROWSER_TEST_MODE` removed. It requires the visible product route to
publish either an actionable shear repair or explicit no-repair evidence, and
the repair-action path must be owned by `ShearFailFamily` rather than the old
generic active-strength fallback.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO / "artifacts" / "verification"
SCENARIO = "scenario_c1_pure_shear_underdesign_repair"
REPORT_LINE_RE = re.compile(r"^Report:\s*(?P<path>.+?\.json)\s*$")
ACCEPTED_PUBLICATION_FAMILIES = {
    "SHEAR_FAIL_GOVERNS",
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
}


def _latest_gate_report(started_at: float) -> Path | None:
    reports = sorted(
        ARTIFACT_DIR.glob("design_guide_product_path_gate_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in reports:
        if path.stat().st_mtime >= started_at - 1:
            return path
    return reports[0] if reports else None


def _gate_report_from_stdout(stdout: str) -> Path | None:
    for line in str(stdout or "").splitlines():
        match = REPORT_LINE_RE.match(line.strip())
        if not match:
            continue
        path = Path(match.group("path"))
        return path if path.is_absolute() else REPO / path
    return None


def _select_gate_report(stdout: str, started_at: float) -> tuple[Path | None, str]:
    gate_path = _gate_report_from_stdout(stdout)
    if gate_path is not None:
        return gate_path, "stdout_report_line"
    return _latest_gate_report(started_at), "latest_mtime_fallback"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _write_report(report: dict[str, Any]) -> Path:
    timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"shear_fail_governs_repair_regression_{timestamp}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _scenario_result(gate_report: dict[str, Any]) -> dict[str, Any]:
    for result in gate_report.get("results") or []:
        if isinstance(result, dict) and result.get("name") == SCENARIO:
            return dict(result)
    return {}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    port = "9320"
    if "--port" in argv:
        index = argv.index("--port")
        if index + 1 < len(argv):
            port = argv[index + 1]
    env = dict(os.environ)
    env.pop("CODEX_BROWSER_TEST_MODE", None)
    env["DESIGN_BRAIN_SHEAR_FAIL_FAMILY_ROUTING"] = "1"
    started_at = time.time()
    command = [
        sys.executable,
        "tools/verification/design_guide_product_path_gate.py",
        "--port",
        port,
        "--scenario",
        SCENARIO,
    ]
    completed = subprocess.run(command, cwd=REPO, env=env, text=True, capture_output=True)
    gate_path, gate_report_source = _select_gate_report(completed.stdout, started_at)
    gate_report = _load_json(gate_path) if gate_path is not None else {}
    scenario = _scenario_result(gate_report)
    evidence = dict(scenario.get("evidence") or {})
    failures = list(scenario.get("failures") or [])
    final_snapshot = dict(evidence.get("final_snapshot") or {})
    first_card_text = str(final_snapshot.get("first_card_text") or final_snapshot.get("body_text") or "")
    lower_text = first_card_text.lower()
    ctas = list(evidence.get("visible_cta_buttons") or [])
    design_guide_shear_ctas = [
        str(value)
        for value in ctas
        if "shear capacity is low" in str(value).lower()
        or "one-click auto design" in str(value).lower()
    ]
    render_cta_payload_id = str(evidence.get("render_cta_payload_id") or "")
    render_cta_payload_id_lower = render_cta_payload_id.lower()
    selected_family_id = str(evidence.get("selected_family_id") or "")
    published_family_id = str(evidence.get("published_family_id") or "")
    cta_family_id = str(evidence.get("cta_family_id") or "")
    apply_payload_family_id = str(evidence.get("apply_payload_family_id") or "")
    candidate_family_id = str(evidence.get("candidate_family_id") or "")
    family_route_owner = str(evidence.get("family_route_owner") or "")
    positive_checks = {
        "normal_mode": env.get("CODEX_BROWSER_TEST_MODE") in (None, "", "0", "false", "False"),
        "scenario_passed": scenario.get("status") == "PASS",
        "selected_family_is_shear_fail_or_wrapper": selected_family_id in ACCEPTED_PUBLICATION_FAMILIES,
        "published_family_is_shear_fail_or_wrapper": published_family_id in ACCEPTED_PUBLICATION_FAMILIES,
        "cta_family_is_shear_fail_or_wrapper": cta_family_id in ACCEPTED_PUBLICATION_FAMILIES,
        "apply_payload_family_is_shear_fail_or_wrapper": apply_payload_family_id in ACCEPTED_PUBLICATION_FAMILIES,
        "candidate_source_family_is_shear_fail": candidate_family_id == "SHEAR_FAIL_GOVERNS",
        "shear_underdesign_identified": bool(evidence.get("visible_shear_fail_summary")),
        "bending_fail_absent": not bool(evidence.get("visible_bending_fail_summary")),
        "family_owner_visible": "design_brain.families.shear_fail.ShearFailFamily"
        in family_route_owner
        or "design_brain.families.shear_fail_bending_overdesign.ShearFailBendingOverdesignFamily"
        in family_route_owner,
        "repair_action_or_no_repair_evidence": bool(
            evidence.get("has_repair_action") or evidence.get("has_no_repair_evidence")
        ),
        "apply_payload_exists": bool(evidence.get("has_apply_payload") or evidence.get("has_repair_action")),
        "payload_id_is_shear_fail_repair": (
            any(family in render_cta_payload_id for family in ACCEPTED_PUBLICATION_FAMILIES)
            and "shear_fail" in render_cta_payload_id_lower
            and "repair" in render_cta_payload_id_lower
        ),
        "single_design_guide_shear_cta_if_actionable": len(design_guide_shear_ctas) == 1,
    }
    negative_checks = {
        "no_design_is_efficient": "design is efficient" not in lower_text,
        "no_pass_terminal": not ("pass" in lower_text and "fail" not in lower_text),
        "no_blocked_cleanup": "blocked cleanup" not in lower_text and "cleanup blocked" not in lower_text,
        "no_cleanup": "cleanup" not in lower_text,
        "no_cleanup_payload_identity": "cleanup" not in render_cta_payload_id_lower,
        "no_combined_payload_identity": "combined" not in render_cta_payload_id_lower,
        "no_combined_family_final": evidence.get("selected_family_id") != "COMBINED_BENDING_SHEAR_FAIL",
        "no_family_mismatch_blocked": "family mismatch blocked" not in lower_text,
        "no_blank_or_frozen": bool(first_card_text.strip()) and not any(
            token in lower_text for token in ("loading", "preparing", "checking design guidance")
        ),
        "no_duplicate_cta": len(ctas) == len(set(ctas)),
        "no_debug_probe_output": not evidence.get("debug_tokens"),
    }
    failed_checks = [
        f"positive:{name}"
        for name, ok in positive_checks.items()
        if not ok
    ] + [
        f"negative:{name}"
        for name, ok in negative_checks.items()
        if not ok
    ]
    status = "PASS" if completed.returncode == 0 and not failures and not failed_checks else "FAIL"
    report = {
        "schema": "shear_fail_governs_repair_regression.v1",
        "regression_id": "shear_fail_governs_repair_regression",
        "status": status,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr_tail": completed.stderr[-4000:],
        "normal_mode": True,
        "browser_test_mode": env.get("CODEX_BROWSER_TEST_MODE") or "unset",
        "routing_flag": "DESIGN_BRAIN_SHEAR_FAIL_FAMILY_ROUTING=1",
        "gate_report": str(gate_path) if gate_path else None,
        "gate_report_source": gate_report_source,
        "scenario": scenario,
        "positive_checks": positive_checks,
        "negative_checks": negative_checks,
        "failures": failures + failed_checks,
    }
    output = _write_report(report)
    print(f"{status}: {output}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
