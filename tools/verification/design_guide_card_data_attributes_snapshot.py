"""Snapshot resolved Design Guide card data-attribute fields for product scenarios."""

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


def _read_rows(path: Path) -> list[dict[str, Any]]:
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


def _selected_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in reversed(rows):
        if str(row.get("source") or "") == "build_design_guide_card_data_attributes":
            return row
    return rows[-1] if rows else {}


def _run_scenario(label: str, *, base_port: int, index: int, timestamp: str) -> dict[str, Any]:
    spec = SCENARIOS[label]
    scenario_name = str(spec["name"])
    expected_family = str(spec["expected_family"])
    runtime_path = ARTIFACT_DIR / f"design_guide_card_data_attributes_runtime_{timestamp}_{label.lower()}.jsonl"
    if runtime_path.exists():
        runtime_path.unlink()
    env = dict(os.environ)
    env.pop("CODEX_BROWSER_TEST_MODE", None)
    env.update(dict(spec.get("env") or {}))
    env["DESIGN_GUIDE_CARD_DATA_ATTRIBUTES_SNAPSHOT_PATH"] = str(runtime_path)
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
    rows = _read_rows(runtime_path)
    selected = _selected_row(rows)
    fields = dict(selected.get("fields") or {})
    data_attributes = dict(selected.get("data_attributes") or {})
    failures: list[str] = []
    if completed.returncode != 0:
        failures.append(f"gate_returncode:{completed.returncode}")
    if scenario.get("status") != "PASS":
        failures.append("scenario_not_pass")
    if not selected:
        failures.append("data_attribute_snapshot_missing")
    if str(fields.get("selected_family_id") or "") != expected_family:
        failures.append("fields_family_mismatch")
    if str(data_attributes.get("selected_family_id") or "") != expected_family:
        failures.append("data_attrs_family_mismatch")
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
        "selected_runtime_source": selected.get("source"),
        "fields": fields,
        "data_attributes": data_attributes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=10301)
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
        "schema": "design_guide_card_data_attributes_snapshot.v1",
        "status": status,
        "results": results,
    }
    output = ARTIFACT_DIR / f"design_guide_card_data_attributes_snapshot_{timestamp}.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{status}: {output}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
