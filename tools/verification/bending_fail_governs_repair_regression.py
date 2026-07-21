"""Permanent normal product-path regression for BENDING_FAIL_GOVERNS."""

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
SCENARIO = "scenario_c3_pure_bending_underdesign_repair"
REPORT_LINE_RE = re.compile(r"^Report:\s*(?P<path>.+?\.json)\s*$")
BENDING_FAIL_FAMILY_ALIASES = {"BENDING_FAIL_GOVERNS", "bending"}


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


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _is_bending_fail_family(value: Any) -> bool:
    raw = str(value or "").strip()
    return raw in BENDING_FAIL_FAMILY_ALIASES or raw.lower() in BENDING_FAIL_FAMILY_ALIASES


def _scenario_result(gate_report: dict[str, Any]) -> dict[str, Any]:
    for result in gate_report.get("results") or []:
        if isinstance(result, dict) and result.get("name") == SCENARIO:
            return dict(result)
    return {}


def _write_report(report: dict[str, Any]) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"bending_fail_governs_repair_regression_{time.strftime('%Y-%m-%dT%H-%M-%S')}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    port = "9502"
    if "--port" in argv:
        index = argv.index("--port")
        if index + 1 < len(argv):
            port = argv[index + 1]
    env = dict(os.environ)
    env.pop("CODEX_BROWSER_TEST_MODE", None)
    env.pop("DESIGN_BRAIN_BENDING_FAIL_FAMILY_ROUTING", None)
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
    gate_report = _load_json(gate_path)
    scenario = _scenario_result(gate_report)
    evidence = dict(scenario.get("evidence") or {})
    final_snapshot = dict(evidence.get("final_snapshot") or {})
    first_card_text = str(final_snapshot.get("first_card_text") or final_snapshot.get("body_text") or "")
    lower_text = first_card_text.lower()
    blocked_no_repair_visible = bool(
        "bending repair blocked" in lower_text
        and (
            "exhaustive" in lower_text
            or "no executor-backed one-click arrangement" in lower_text
            or "checked repair routes" in lower_text
        )
    )
    ctas = list(evidence.get("visible_cta_buttons") or [])
    design_guide_apply_ctas = [
        label
        for label in ctas
        if str(label or "").strip().lower().startswith("apply")
    ]
    matched_family_ids = list(evidence.get("matched_family_ids") or [])
    render_cta_payload_id = str(evidence.get("render_cta_payload_id") or "")
    render_cta_payload_id_lower = render_cta_payload_id.lower()
    repair_action_visible = bool(evidence.get("has_repair_action"))
    acceptable_bending_fail_publication = bool(repair_action_visible or blocked_no_repair_visible)
    positive_checks = {
        "normal_mode": env.get("CODEX_BROWSER_TEST_MODE") in (None, "", "0", "false", "False"),
        "bending_fail_family_routing_live_default": "DESIGN_BRAIN_BENDING_FAIL_FAMILY_ROUTING" not in env,
        "scenario_passed": scenario.get("status") == "PASS",
        "selected_family_is_bending_fail": _is_bending_fail_family(evidence.get("selected_family_id")),
        "published_family_is_bending_fail": _is_bending_fail_family(evidence.get("published_family_id")),
        "cta_family_is_bending_fail_or_blocked": (
            _is_bending_fail_family(evidence.get("cta_family_id")) or blocked_no_repair_visible
        ),
        "apply_payload_family_is_bending_fail_or_blocked": (
            _is_bending_fail_family(evidence.get("apply_payload_family_id")) or blocked_no_repair_visible
        ),
        "matched_family_ids_exact": len(matched_family_ids) == 1 and _is_bending_fail_family(matched_family_ids[0]),
        "bending_underdesign_identified": bool(evidence.get("visible_bending_fail_summary")),
        "shear_fail_absent": not bool(evidence.get("visible_shear_fail_summary")),
        "family_owner_visible": "design_brain.families.bending_fail.BendingFailFamily"
        in str(evidence.get("family_route_owner") or ""),
        "repair_action_or_blocker_proof_visible": acceptable_bending_fail_publication,
        "apply_payload_exists_or_blocker_proof_visible": acceptable_bending_fail_publication,
        "payload_id_is_bending_fail_or_blocked": (
            render_cta_payload_id.startswith("BENDING_FAIL_GOVERNS:")
            or render_cta_payload_id.lower().startswith("bending:")
            or blocked_no_repair_visible
        ),
        "single_primary_cta_or_blocked": (
            (len(ctas) == 1 and (len(design_guide_apply_ctas) == 1 or "one-click" in " ".join(ctas).lower()))
            or (blocked_no_repair_visible and not design_guide_apply_ctas)
        ),
    }
    negative_checks = {
        "no_design_is_efficient": "design is efficient" not in lower_text,
        "no_pass_terminal": not ("pass" in lower_text and "fail" not in lower_text),
        "no_cleanup": "cleanup" not in lower_text,
        "no_cleanup_payload_identity": "cleanup" not in render_cta_payload_id_lower,
        "no_shear_payload_identity": "shear_fail_governs" not in render_cta_payload_id_lower,
        "no_combined_payload_identity": "combined_bending_shear_fail" not in render_cta_payload_id_lower,
        "no_unknown_payload_identity": not render_cta_payload_id_lower.startswith("unknown:"),
        "no_family_mismatch_blocked": "family mismatch blocked" not in lower_text,
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
    status = "PASS" if completed.returncode == 0 and not failed_checks else "FAIL"
    report = {
        "schema": "bending_fail_governs_repair_regression.v1",
        "status": status,
        "scenario": SCENARIO,
        "command": command,
        "returncode": completed.returncode,
        "gate_report": str(gate_path) if gate_path else None,
        "gate_report_source": gate_report_source,
        "positive_checks": positive_checks,
        "negative_checks": negative_checks,
        "failed_checks": failed_checks,
        "selected_family_id": evidence.get("selected_family_id"),
        "published_family_id": evidence.get("published_family_id"),
        "cta_family_id": evidence.get("cta_family_id"),
        "apply_payload_family_id": evidence.get("apply_payload_family_id"),
        "matched_family_ids": matched_family_ids,
        "render_cta_payload_id": render_cta_payload_id,
        "blocked_no_repair_visible": blocked_no_repair_visible,
        "visible_cta_buttons": ctas,
        "visible_design_guide_apply_cta_buttons": design_guide_apply_ctas,
        "stdout": completed.stdout,
        "stderr_tail": completed.stderr[-4000:],
    }
    path = _write_report(report)
    print(f"{status}: {path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
