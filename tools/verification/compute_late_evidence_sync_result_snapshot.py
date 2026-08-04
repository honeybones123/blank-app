"""Verify compute late-evidence sync typed-result parity from runtime trace."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO / "artifacts" / "verification"
TRACE_DIR = REPO / "artifacts" / "traces"


BRANCH_SPECIFIC_EVENTS = {
    "late_evidence_built_missing_candidate_search_evidence",
    "late_evidence_coherence_active_repair_republished",
    "late_evidence_active_under_capacity_blocker_materialized",
    "late_evidence_safe_cleanup_rehydrated",
    "late_evidence_shear_final_threshold_blocker_materialized",
    "late_evidence_contract_rebound_applied",
}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _latest_trace() -> Path:
    candidates = sorted(
        TRACE_DIR.glob("compute_late_evidence_sync_trace_8E_*.jsonl"),
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        candidates = sorted(
            TRACE_DIR.glob("compute_late_evidence_proof_trace_8D_*.jsonl"),
            key=lambda path: path.stat().st_mtime,
        )
    if not candidates:
        raise FileNotFoundError("No compute late-evidence trace artifact found")
    return candidates[-1]


def _latest_record() -> Path:
    candidates = sorted(
        TRACE_DIR.glob("compute_late_evidence_sync_result_8E_*.jsonl"),
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        raise FileNotFoundError("No compute late-evidence typed-result artifact found")
    return candidates[-1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, default=None)
    parser.add_argument("--record", type=Path, default=None)
    args = parser.parse_args()

    trace_path = (args.trace or _latest_trace()).resolve()
    record_path = (args.record or _latest_record()).resolve()
    rows = _load_jsonl(trace_path)
    record_rows = _load_jsonl(record_path)
    compute_rows = [
        row
        for row in rows
        if row.get("event") == "compute_guidance_route"
        and str(row.get("route_event") or "").startswith("late_evidence")
    ]
    typed_rows = [
        row
        for row in record_rows
        if row.get("event") == "compute_late_evidence_sync_typed_result"
    ]
    failures: list[str] = []
    if not typed_rows:
        failures.append("typed_result_rows_missing")

    records: list[dict[str, Any]] = []
    for index, row in enumerate(typed_rows):
        typed = row.get("typed_result") if isinstance(row.get("typed_result"), dict) else {}
        if not isinstance(typed, dict):
            failures.append(f"typed_result_{index}_not_dict")
            continue
        parity = typed.get("parity_checks")
        if not isinstance(parity, dict) or not parity:
            failures.append(f"typed_result_{index}_parity_checks_missing")
            parity = {}
        failed_keys = [str(key) for key, value in parity.items() if value is not True]
        if failed_keys:
            failures.append(f"typed_result_{index}_parity_failed:{','.join(failed_keys)}")
        if not typed.get("evidence_hash"):
            failures.append(f"typed_result_{index}_evidence_hash_missing")
        if not isinstance(typed.get("changed_fields"), list):
            failures.append(f"typed_result_{index}_changed_fields_not_list")
        if not typed.get("item_hash_after"):
            failures.append(f"typed_result_{index}_item_hash_after_missing")
        if not typed.get("action_payload_hash_after"):
            failures.append(f"typed_result_{index}_action_payload_hash_after_missing")
        if not typed.get("resolved_candidate_hash_after"):
            failures.append(f"typed_result_{index}_resolved_candidate_hash_after_missing")
        if not typed.get("button_contract_hash_after"):
            failures.append(f"typed_result_{index}_button_contract_hash_after_missing")
        records.append(
            {
                "scenario": row.get("scenario"),
                "evidence_hash": typed.get("evidence_hash"),
                "item_hash_before": typed.get("item_hash_before"),
                "item_hash_after": typed.get("item_hash_after"),
                "action_payload_hash_before": typed.get("action_payload_hash_before"),
                "action_payload_hash_after": typed.get("action_payload_hash_after"),
                "resolved_candidate_hash_before": typed.get("resolved_candidate_hash_before"),
                "resolved_candidate_hash_after": typed.get("resolved_candidate_hash_after"),
                "button_contract_hash_before": typed.get("button_contract_hash_before"),
                "button_contract_hash_after": typed.get("button_contract_hash_after"),
                "changed_fields": list(typed.get("changed_fields") or []),
                "parity_checks": dict(parity),
                "active_under_capacity_blocker": bool(typed.get("active_under_capacity_blocker")),
                "exact_blockers_present": bool(typed.get("exact_blockers_present")),
            }
        )

    branch_counts: dict[str, int] = {}
    for row in compute_rows:
        event = str(row.get("route_event") or "")
        if event in BRANCH_SPECIFIC_EVENTS:
            branch_counts[event] = branch_counts.get(event, 0) + 1

    status = "PASS" if not failures else "FAIL"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    output_path = ARTIFACT_DIR / f"compute_late_evidence_sync_result_snapshot_{stamp}.json"
    output = {
        "schema": "compute_late_evidence_sync_result_snapshot.v1",
        "status": status,
        "failures": failures,
        "trace_path": str(trace_path),
        "record_path": str(record_path),
        "late_evidence_event_count": len(compute_rows),
        "typed_result_count": len(typed_rows),
        "branch_specific_event_counts": branch_counts,
        "typed_results": records,
    }
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    print(f"{status}: {output_path}")
    if failures:
        for failure in failures:
            print(f"- {failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
