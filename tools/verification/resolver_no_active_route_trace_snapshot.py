"""Runtime trace snapshot for the resolver no-active-failure route.

This verifier is intentionally trace-only. It runs existing product gates with
``DESIGN_GUIDE_RUNTIME_TRACE=1`` and summarizes resolver route events whose
names are specific to the no-active-failure publication path.
"""

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
TRACE_DIR = REPO / "artifacts" / "traces"


SCENARIOS = [
    (
        "C1",
        [
            "tools/verification/design_guide_product_path_gate.py",
            "--scenario",
            "scenario_c1_pure_shear_underdesign_repair",
        ],
    ),
    (
        "C2",
        [
            "tools/verification/design_guide_product_path_gate.py",
            "--scenario",
            "scenario_c2_combined_bending_shear_underdesign_repair",
        ],
    ),
    (
        "C3",
        [
            "tools/verification/design_guide_product_path_gate.py",
            "--scenario",
            "scenario_c3_pure_bending_underdesign_repair",
        ],
    ),
    ("PUBLICATION", ["tools/verification/design_guide_publication_snapshot.py"]),
    ("SHEAR_BOUNDARY", ["tools/verification/shear_display_boundary_snapshot.py"]),
]


def _load_trace_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _report_path_from_stdout(stdout: str) -> str | None:
    for line in str(stdout or "").splitlines():
        match = re.match(r"^(?:PASS|FAIL|Normal product-path PASS|Normal product-path FAIL):\s*(.+\.json)\s*$", line.strip())
        if match:
            return match.group(1)
        if line.strip().startswith("Report:") and line.strip().endswith(".json"):
            return line.split(":", 1)[1].strip()
    return None


def _compact_hash(value: Any) -> str | None:
    if isinstance(value, dict):
        raw = value.get("hash")
        if raw is not None:
            return str(raw)
    return None


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    route_rows = [
        row
        for row in rows
        if row.get("event") == "resolver_route"
    ]
    no_active_rows = [
        row
        for row in route_rows
        if str(row.get("route_event") or "").startswith("no_active")
        or str(row.get("route_event") or "").startswith("return_no_active")
        or str(row.get("route_event") or "") in {
            "enter_no_active_failure_route",
            "debug_bundle_evidence_rebind_selected",
            "debug_bundle_evidence_rebind_written",
        }
    ]
    events = [str(row.get("route_event") or "") for row in no_active_rows]
    returns = [event for event in events if event.startswith("return_no_active")]
    event_counts: dict[str, int] = {}
    for event in events:
        event_counts[event] = event_counts.get(event, 0) + 1
    final_payload: dict[str, Any] = {}
    if no_active_rows:
        payload = no_active_rows[-1].get("payload")
        final_payload = payload if isinstance(payload, dict) else {}
    primary = final_payload.get("primary") or final_payload.get("item")
    return {
        "trace_row_count": len(rows),
        "resolver_route_row_count": len(route_rows),
        "no_active_route_entered": "enter_no_active_failure_route" in events,
        "no_active_event_count": len(no_active_rows),
        "no_active_events": events,
        "no_active_event_counts": event_counts,
        "no_active_returns": returns,
        "final_no_active_event": events[-1] if events else None,
        "final_item_hash": _compact_hash(primary),
        "final_item_family": primary.get("family") if isinstance(primary, dict) else None,
        "final_selected_action_family": primary.get("selected_action_family") if isinstance(primary, dict) else None,
        "final_button_contract_hash": (
            primary.get("button_contract_hash") if isinstance(primary, dict) else None
        ),
        "final_button_contract_enabled": (
            primary.get("button_contract_enabled") if isinstance(primary, dict) else None
        ),
        "final_render_reason": final_payload.get("render_reason"),
    }


def _run_trace_command(label: str, command_tail: list[str], port: int, timestamp: str) -> dict[str, Any]:
    trace_path = TRACE_DIR / f"resolver_no_active_route_trace_7DB_{timestamp}_{label}.jsonl"
    env = dict(os.environ)
    env["DESIGN_GUIDE_RUNTIME_TRACE"] = "1"
    env["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = f"NO_ACTIVE_{label}"
    env["DESIGN_GUIDE_RUNTIME_TRACE_PATH"] = str(trace_path)
    command = [sys.executable, *command_tail, "--port", str(port)]
    completed = subprocess.run(command, cwd=REPO, env=env, text=True, capture_output=True)
    rows = _load_trace_rows(trace_path)
    return {
        "label": label,
        "command": command,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
        "report_path": _report_path_from_stdout(completed.stdout),
        "trace_path": str(trace_path),
        "summary": _summarize_rows(rows),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-port", type=int, default=10870)
    args = parser.parse_args(argv)

    timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)

    runs = [
        _run_trace_command(label, command_tail, args.base_port + index, timestamp)
        for index, (label, command_tail) in enumerate(SCENARIOS)
    ]
    failures = [
        f"{run['label']}:returncode:{run['returncode']}"
        for run in runs
        if int(run.get("returncode") or 0) != 0
    ]
    entered = [
        run["label"]
        for run in runs
        if bool((run.get("summary") or {}).get("no_active_route_entered"))
    ]
    report = {
        "schema": "resolver_no_active_route_trace_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "timestamp": timestamp,
        "no_active_route_entered_labels": entered,
        "runs": runs,
    }
    output = ARTIFACT_DIR / f"resolver_no_active_route_trace_snapshot_7DB_{timestamp}.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{report['status']}: {output}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
