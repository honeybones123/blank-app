"""Focused snapshot for the terminal active-failure publication fallback tail.

This verifier runs the existing publication snapshot with runtime tracing
enabled, then extracts the terminal active-failure fallback events emitted by
``resolve_final_visible_design_guide_item``.

It is intentionally focused on the full publication-snapshot route rather than
standalone C1/C2/C3 product gates, because 7CX showed this fallback tail is
exercised by the publication snapshot and not by the standalone product gates.
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

REQUIRED_SEQUENCE = [
    "terminal_active_failure_blocker_source_before_filter",
    "terminal_active_failure_blocker_source_after_filter",
    "terminal_active_failure_blocker_suppress_cta_before",
    "terminal_active_failure_blocker_suppress_cta_after",
    "terminal_active_failure_publication_finalizer_before",
    "terminal_active_failure_publication_finalizer_after",
    "terminal_active_failure_blocker_finalized",
    "return_terminal_active_failure_blocker",
]


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _report_path_from_stdout(stdout: str) -> Path | None:
    for line in str(stdout or "").splitlines():
        match = re.match(r"^(?:PASS|FAIL):\s*(.+\.json)\s*$", line.strip())
        if match:
            return Path(match.group(1))
    return None


def _read_trace_rows(path: Path) -> list[dict[str, Any]]:
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


def _route_payload(rows: list[dict[str, Any]], route_event: str) -> dict[str, Any]:
    for row in rows:
        if row.get("event") == "resolver_route" and row.get("route_event") == route_event:
            payload = row.get("payload")
            return payload if isinstance(payload, dict) else {}
    return {}


def _compact_hash(value: Any) -> str | None:
    if isinstance(value, dict):
        raw = value.get("hash")
        if raw is not None:
            return str(raw)
    return None


def _compact_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        keys = value.get("keys")
        if isinstance(keys, list):
            return sorted(str(key) for key in keys)
    if isinstance(value, dict):
        return sorted(str(key) for key in value.keys())
    return []


def _summarise_tail(rows: list[dict[str, Any]]) -> dict[str, Any]:
    terminal_rows = [
        row
        for row in rows
        if row.get("event") == "resolver_route"
        and str(row.get("route_event") or "").startswith("terminal_active_failure")
        or row.get("route_event") == "return_terminal_active_failure_blocker"
    ]
    route_events = [str(row.get("route_event") or "") for row in terminal_rows]
    by_event = {event: _route_payload(rows, event) for event in REQUIRED_SEQUENCE}

    before_filter = by_event["terminal_active_failure_blocker_source_before_filter"]
    after_filter = by_event["terminal_active_failure_blocker_source_after_filter"]
    suppress_before = by_event["terminal_active_failure_blocker_suppress_cta_before"]
    suppress_after = by_event["terminal_active_failure_blocker_suppress_cta_after"]
    finalizer_before = by_event["terminal_active_failure_publication_finalizer_before"]
    finalizer_after = by_event["terminal_active_failure_publication_finalizer_after"]
    finalized = by_event["terminal_active_failure_blocker_finalized"]
    returned = by_event["return_terminal_active_failure_blocker"]

    source_before = before_filter.get("active_blocker_source")
    source_after = after_filter.get("active_blocker_source")
    suppress_blocker = suppress_after.get("blocker")
    suppress_contract = suppress_after.get("button_contract")
    finalizer_blocker = finalizer_before.get("blocker")
    final_item = finalizer_after.get("result_item")
    final_contract = finalized.get("button_contract")
    exact = finalized.get("exact_blockers_by_family")

    return {
        "terminal_route_entered": bool(terminal_rows),
        "terminal_event_count": len(terminal_rows),
        "route_events": route_events,
        "required_sequence_present": all(event in route_events for event in REQUIRED_SEQUENCE),
        "missing_required_events": [event for event in REQUIRED_SEQUENCE if event not in route_events],
        "active_family": before_filter.get("active_family") or finalized.get("active_family"),
        "active_scope": before_filter.get("active_scope") or after_filter.get("active_scope"),
        "active_blocker_source_kept": after_filter.get("active_blocker_source_kept"),
        "active_blocker_source_hash_before": _compact_hash(source_before),
        "active_blocker_source_hash_after": _compact_hash(source_after),
        "active_blocker_source_evidence_hash": before_filter.get("active_blocker_evidence_hash"),
        "blocker_source_hash": suppress_before.get("blocker_source_hash"),
        "fallback_item_hash": suppress_before.get("fallback_item_hash")
        or finalizer_before.get("fallback_item_hash"),
        "suppress_cta_blocker_hash": _compact_hash(suppress_blocker)
        or suppress_after.get("blocker_hash"),
        "suppress_cta_button_contract_hash": _compact_hash(suppress_contract),
        "finalizer_input_blocker_hash": _compact_hash(finalizer_blocker),
        "finalizer_final_overview_hash": finalizer_before.get("final_overview_hash"),
        "finalizer_debug_probe_hash": finalizer_before.get("debug_probe_hash"),
        "finalizer_elapsed_ms": finalizer_after.get("elapsed_ms"),
        "finalizer_result_render_reason": finalizer_after.get("result_render_reason"),
        "finalizer_result_state_fingerprint": finalizer_after.get("result_state_fingerprint"),
        "final_item_hash": finalizer_after.get("result_item_hash") or _compact_hash(final_item),
        "final_item_family": final_item.get("family") if isinstance(final_item, dict) else None,
        "final_item_status": final_item.get("status") if isinstance(final_item, dict) else None,
        "final_button_contract_hash": _compact_hash(final_contract),
        "final_button_contract_enabled": final_contract.get("enabled") if isinstance(final_contract, dict) else None,
        "final_exact_blocker_families": _compact_keys(exact),
        "return_item_hash": _compact_hash(returned.get("item")),
        "return_render_reason": returned.get("render_reason"),
    }


def _validate(summary: dict[str, Any], publication_status: str, returncode: int) -> list[str]:
    failures: list[str] = []
    if returncode != 0:
        failures.append(f"publication_snapshot_returncode:{returncode}")
    if publication_status != "PASS":
        failures.append("publication_snapshot_not_pass")
    if not summary.get("terminal_route_entered"):
        failures.append("terminal_tail_not_entered")
    if not summary.get("required_sequence_present"):
        failures.append("terminal_tail_required_sequence_missing")
    if summary.get("active_blocker_source_kept") is not True:
        failures.append("active_blocker_source_not_kept")
    if summary.get("active_family") != "bending":
        failures.append("active_family_not_bending")
    if "bending" not in set(summary.get("final_exact_blocker_families") or []):
        failures.append("final_exact_blocker_missing_bending")
    if summary.get("finalizer_result_render_reason") != "final_visible_active_strength_blocker":
        failures.append("unexpected_finalizer_render_reason")
    if summary.get("return_render_reason") != "final_visible_active_strength_blocker":
        failures.append("unexpected_return_render_reason")
    if not summary.get("final_button_contract_hash"):
        failures.append("final_button_contract_hash_missing")
    if not summary.get("final_item_hash"):
        failures.append("final_item_hash_missing")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=10820)
    args = parser.parse_args(argv)

    timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    trace_path = TRACE_DIR / f"resolver_terminal_active_failure_publication_tail_{timestamp}.jsonl"

    env = dict(os.environ)
    env["DESIGN_GUIDE_RUNTIME_TRACE"] = "1"
    env["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = "PUBLICATION_TAIL"
    env["DESIGN_GUIDE_RUNTIME_TRACE_PATH"] = str(trace_path)

    command = [
        sys.executable,
        "tools/verification/design_guide_publication_snapshot.py",
        "--port",
        str(args.port),
    ]
    completed = subprocess.run(command, cwd=REPO, env=env, text=True, capture_output=True)
    publication_report_path = _report_path_from_stdout(completed.stdout)
    publication_report = _load_json(publication_report_path)
    rows = _read_trace_rows(trace_path)
    summary = _summarise_tail(rows)
    failures = _validate(summary, str(publication_report.get("status") or ""), completed.returncode)
    status = "PASS" if not failures else "FAIL"
    report = {
        "schema": "resolver_terminal_active_failure_publication_tail_snapshot.v1",
        "status": status,
        "failures": failures,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr_tail": completed.stderr[-4000:],
        "publication_report": str(publication_report_path) if publication_report_path else None,
        "trace_path": str(trace_path),
        "trace_row_count": len(rows),
        "tail": summary,
    }
    output = ARTIFACT_DIR / f"resolver_terminal_active_failure_publication_tail_snapshot_{timestamp}.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{status}: {output}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
