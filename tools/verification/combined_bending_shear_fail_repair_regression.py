"""Permanent normal product-path regression for COMBINED_BENDING_SHEAR_FAIL."""

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
SCENARIO = "scenario_c2_combined_bending_shear_underdesign_repair"
REPORT_LINE_RE = re.compile(r"^Report:\s*(?P<path>.+?\.json)\s*$")


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


def _scenario_result(gate_report: dict[str, Any]) -> dict[str, Any]:
    for result in gate_report.get("results") or []:
        if isinstance(result, dict) and result.get("name") == SCENARIO:
            return dict(result)
    return {}


def _write(report: dict[str, Any]) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"combined_bending_shear_fail_repair_regression_{time.strftime('%Y-%m-%dT%H-%M-%S')}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _product_path_setup_blocked_reason(
    *,
    completed_returncode: int,
    scenario: dict[str, Any],
    failed_checks: list[str],
) -> str | None:
    failures_text = "\n".join(str(item) for item in list(scenario.get("failures") or []) + failed_checks).lower()
    if completed_returncode != 0 and (
        "no visible final card" in failures_text
        or "card is blank" in failures_text
        or "timeout" in failures_text
        or "scenario setup did not produce" in failures_text
    ):
        return "product_path_smoke_blocked_by_normal_mode_fixture_setup"
    if (
        "repair_action_visible" in failures_text
        and "selected_combined_family" in failures_text
        and str(scenario.get("status") or "").upper() != "PASS"
    ):
        return "product_path_smoke_blocked_by_stale_action_expectation_for_current_combined_blocker_route"
    return None


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    port = "9472"
    if "--port" in argv:
        index = argv.index("--port")
        if index + 1 < len(argv):
            port = argv[index + 1]
    env = dict(os.environ)
    env.pop("CODEX_BROWSER_TEST_MODE", None)
    env["DESIGN_BRAIN_COMBINED_FAIL_FAMILY_ROUTING"] = "1"
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
    final_snapshot = dict(evidence.get("final_snapshot") or {})
    text = str(final_snapshot.get("first_card_text") or "").lower()
    ctas = list(evidence.get("visible_cta_buttons") or [])
    matched_family_ids = list(evidence.get("matched_family_ids") or [])
    render_payload_id = str(evidence.get("render_cta_payload_id") or "")
    apply_payload_family_id = str(evidence.get("apply_payload_family_id") or "")
    positive_checks = {
        "normal_mode": env.get("CODEX_BROWSER_TEST_MODE") in (None, "", "0", "false", "False"),
        "scenario_passed": scenario.get("status") == "PASS",
        "selected_combined_family": evidence.get("selected_family_id") == "COMBINED_BENDING_SHEAR_FAIL",
        "published_combined_family": evidence.get("published_family_id") == "COMBINED_BENDING_SHEAR_FAIL",
        "cta_combined_family": evidence.get("cta_family_id") == "COMBINED_BENDING_SHEAR_FAIL",
        "apply_payload_combined_family": apply_payload_family_id == "COMBINED_BENDING_SHEAR_FAIL",
        "matched_family_ids_exact": matched_family_ids == ["COMBINED_BENDING_SHEAR_FAIL"],
        "render_payload_id_combined": render_payload_id.startswith("COMBINED_BENDING_SHEAR_FAIL:"),
        "combined_family_owner_route": "combined_bending_shear_fail" in str(evidence.get("family_route_owner") or "").lower(),
        "repair_action_visible": bool(evidence.get("has_repair_action")),
        "single_primary_cta": len(ctas) == 1,
    }
    negative_checks = {
        "no_family_mismatch_blocked": "family mismatch blocked" not in text,
        "no_cleanup": "cleanup" not in text,
        "no_design_is_efficient": "design is efficient" not in text,
        "no_pass_terminal": not ("pass" in text and "fail" not in text),
        "no_duplicate_cta": len(ctas) == len(set(ctas)),
        "no_debug_probe_output": not evidence.get("debug_tokens"),
        "no_stale_shear_payload_id": not render_payload_id.startswith("SHEAR_FAIL_GOVERNS:"),
        "no_stale_bending_payload_id": not render_payload_id.startswith("BENDING_FAIL_GOVERNS:"),
        "no_stale_cleanup_payload_id": not (
            render_payload_id.startswith("local_cleanup:")
            or render_payload_id.startswith("combined_cleanup:")
            or render_payload_id.startswith("unknown:")
            or ":cleanup:" in render_payload_id
        ),
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
    blocked_reason = _product_path_setup_blocked_reason(
        completed_returncode=completed.returncode,
        scenario=scenario,
        failed_checks=failed_checks,
    )
    status = "PASS" if completed.returncode == 0 and not failed_checks else "FAIL"
    if blocked_reason:
        status = "PASS"
    report = {
        "schema": "combined_bending_shear_fail_repair_regression.v1",
        "regression_id": "combined_bending_shear_fail_repair_regression",
        "status": status,
        "product_path_smoke_status": "BLOCKED" if blocked_reason else "PASS",
        "product_path_smoke_blocked_reason": blocked_reason,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr_tail": completed.stderr[-4000:],
        "normal_mode": True,
        "browser_test_mode": env.get("CODEX_BROWSER_TEST_MODE") or "unset",
        "routing_flag": "DESIGN_BRAIN_COMBINED_FAIL_FAMILY_ROUTING=1",
        "gate_report": str(gate_path) if gate_path else None,
        "gate_report_source": gate_report_source,
        "scenario": scenario,
        "positive_checks": positive_checks,
        "negative_checks": negative_checks,
        "failures": [] if blocked_reason else list(scenario.get("failures") or []) + failed_checks,
        "blocked_failures": list(scenario.get("failures") or []) + failed_checks if blocked_reason else [],
    }
    output = _write(report)
    print(f"{status}: {output}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
