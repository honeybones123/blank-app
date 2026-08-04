"""Verify run-scoped candidate evaluation deduplication."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.candidate_registry import CandidateEvaluationRegistry


def main() -> int:
    calls = {"count": 0}

    def compute() -> dict[str, str]:
        calls["count"] += 1
        return {"identity": "candidate-A"}

    first_run = CandidateEvaluationRegistry()
    first = first_run.get_or_compute("state-hash-A", compute)
    second = first_run.get_or_compute("state-hash-A", compute)
    first_run["state-hash-B"] = {"identity": "candidate-B"}
    second_run = CandidateEvaluationRegistry()
    third = second_run.get_or_compute("state-hash-A", compute)

    failures: list[str] = []
    if calls["count"] != 2:
        failures.append(f"same_key_computed_more_than_once:{calls['count']}")
    if first is not second:
        failures.append("same_key_result_identity_not_reused")
    if first is third:
        failures.append("cross_run_result_reused")
    if len(first_run) != 2 or first_run.compute_count != 2:
        failures.append("first_run_registry_counts_invalid")
    if second_run.compute_count != 1:
        failures.append("second_run_registry_counts_invalid")
    snapshot = first_run.snapshot()
    if set(snapshot) != {"unique_evaluations", "compute_count", "cache_hit_count"}:
        failures.append("snapshot_exposes_non_scalar_surface")

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    verification_dir = ROOT / "artifacts" / "verification"
    audit_dir = ROOT / "artifacts" / "audits"
    verification_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "candidate_evaluation_registry_lock.v1",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "same_key_compute_count": calls["count"] - second_run.compute_count,
        "first_run": snapshot,
        "second_run": second_run.snapshot(),
        "run_scoped": not failures,
    }
    json_path = verification_dir / f"candidate_evaluation_registry_lock_{timestamp}.json"
    md_path = audit_dir / f"candidate_evaluation_registry_lock_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(
        "# Candidate Evaluation Registry Lock\n\n"
        f"Status: **{payload['status']}**\n\n"
        "The registry deduplicates one candidate key within a run and does not "
        "reuse results across a fresh run.\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": payload["status"], "json": str(json_path), "audit": str(md_path)}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
