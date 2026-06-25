"""Snapshot resolved Design Guide card render models for product scenarios."""

from __future__ import annotations

import argparse
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

SCENARIOS = {
    "SHEAR": {
        "name": "scenario_c1_pure_shear_underdesign_repair",
        "expected_family": "SHEAR_FAIL_GOVERNS",
        "env": {"DESIGN_BRAIN_SHEAR_FAIL_FAMILY_ROUTING": "1"},
    },
    "COMBINED": {
        "name": "scenario_c2_combined_bending_shear_underdesign_repair",
        "expected_family": "COMBINED_BENDING_SHEAR_FAIL",
        "env": {"DESIGN_BRAIN_COMBINED_FAIL_FAMILY_ROUTING": "1"},
    },
    "BENDING": {
        "name": "scenario_c3_pure_bending_underdesign_repair",
        "expected_family": "BENDING_FAIL_GOVERNS",
        "env": {"DESIGN_BRAIN_BENDING_FAIL_FAMILY_ROUTING": "1"},
    },
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _report_path_from_stdout(stdout: str) -> Path | None:
    for line in str(stdout or "").splitlines():
        match = re.match(r"^Report:\s*(.+\.json)\s*$", line.strip())
        if match:
            return Path(match.group(1))
    return None


def _scenario_result(gate_report: dict[str, Any], scenario_name: str) -> dict[str, Any]:
    for result in gate_report.get("results") or []:
        if isinstance(result, dict) and result.get("name") == scenario_name:
            return dict(result)
    return {}


def _read_model_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _selected_model_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in reversed(rows):
        if str(row.get("source") or "") == "fast_guidance_panel_final":
            return row
    return rows[-1] if rows else {}


def _model_snapshot(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "family": model.get("family"),
        "family_label": model.get("family_label"),
        "terminal_status": model.get("terminal_status"),
        "title": model.get("title"),
        "main_text": model.get("main_text"),
        "why_body": model.get("why_body"),
        "cta_label": model.get("cta_label"),
        "cta_enabled": model.get("cta_enabled"),
        "cta_reason": model.get("cta_reason"),
        "card_tone": model.get("card_tone"),
        "card_class": model.get("card_class"),
        "repair_identity": model.get("repair_identity"),
        "apply_identity": model.get("apply_identity"),
        "blocker_reason": model.get("blocker_reason"),
        "verifier_fields": model.get("verifier_fields"),
    }


def _run_scenario(label: str, *, base_port: int, index: int, timestamp: str) -> dict[str, Any]:
    spec = SCENARIOS[label]
    scenario_name = str(spec["name"])
    expected_family = str(spec["expected_family"])
    runtime_path = ARTIFACT_DIR / f"design_guide_card_render_model_runtime_{timestamp}_{label.lower()}.jsonl"
    if runtime_path.exists():
        runtime_path.unlink()
    env = dict(os.environ)
    env.pop("CODEX_BROWSER_TEST_MODE", None)
    env.update(dict(spec.get("env") or {}))
    env["DESIGN_GUIDE_CARD_RENDER_MODEL_SNAPSHOT_PATH"] = str(runtime_path)
    command = [
        sys.executable,
        "tools/verification/design_guide_product_path_gate.py",
        "--port",
        str(base_port + index),
        "--scenario",
        scenario_name,
    ]
    completed = subprocess.run(command, cwd=REPO, env=env, text=True, capture_output=True)
    gate_path = _report_path_from_stdout(completed.stdout)
    gate_report = _load_json(gate_path) if gate_path is not None else {}
    scenario = _scenario_result(gate_report, scenario_name)
    evidence = dict(scenario.get("evidence") or {})
    rows = _read_model_rows(runtime_path)
    selected_row = _selected_model_row(rows)
    model = dict(selected_row.get("model") or {})
    snapshot = _model_snapshot(model)
    failures = []
    if completed.returncode != 0:
        failures.append(f"gate_returncode:{completed.returncode}")
    if scenario.get("status") != "PASS":
        failures.append("scenario_not_pass")
    if not model:
        failures.append("render_model_missing")
    if str(model.get("family") or "") != expected_family:
        failures.append("model_family_mismatch")
    evidence_family = str(evidence.get("selected_family_id") or "")
    if evidence_family and str(model.get("family") or "") != evidence_family:
        failures.append("model_evidence_family_mismatch")
    return {
        "label": label,
        "scenario": scenario_name,
        "expected_family": expected_family,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr_tail": completed.stderr[-4000:],
        "gate_report": str(gate_path) if gate_path else None,
        "runtime_snapshot_path": str(runtime_path),
        "runtime_row_count": len(rows),
        "selected_runtime_source": selected_row.get("source"),
        "model": snapshot,
        "evidence": {
            "selected_family_id": evidence.get("selected_family_id"),
            "published_family_id": evidence.get("published_family_id"),
            "cta_family_id": evidence.get("cta_family_id"),
            "apply_payload_family_id": evidence.get("apply_payload_family_id"),
            "render_cta_payload_id": evidence.get("render_cta_payload_id"),
            "visible_cta_buttons": evidence.get("visible_cta_buttons"),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9861)
    parser.add_argument(
        "--scenario",
        action="append",
        choices=sorted(SCENARIOS),
        help="Scenario label to run. May be repeated. Defaults to SHEAR, BENDING, COMBINED.",
    )
    args = parser.parse_args(argv)

    timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    labels = args.scenario or ["SHEAR", "BENDING", "COMBINED"]
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    results = [
        _run_scenario(label, base_port=args.port, index=index, timestamp=timestamp)
        for index, label in enumerate(labels)
    ]
    status = "PASS" if results and all(result.get("status") == "PASS" for result in results) else "FAIL"
    report = {
        "schema": "design_guide_card_render_model_snapshot.v1",
        "status": status,
        "results": results,
    }
    output = ARTIFACT_DIR / f"design_guide_card_render_model_snapshot_{timestamp}.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{status}: {output}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
