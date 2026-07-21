"""Verify BENDING_FAIL_GOVERNS rejects wide longitudinal bar spacing candidates.

The live fuzz failure that motivated this check published a bending repair
candidate whose preview later tripped the shared apply guard:
``maximum_longitudinal_bar_spacing_exceeded``. This verifier proves the family
candidate ladder consumes that same Design Brain rule before publication.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.candidate_evaluation import resolve_longitudinal_bar_spacing_rule  # noqa: E402
from design_brain.families.bending_fail import BendingFailFamily  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _fixture_state() -> dict[str, Any]:
    return {
        "b": 450.0,
        "bw": 450.0,
        "D": 500.0,
        "cover_side": 40.0,
        "lig_d": 24,
        "bot_row_1_bars": 4,
        "bot1_count": 4,
        "bot_row_1_dia": 16,
        "db_bot_1": 16,
        "bot_row_2_bars": 0,
        "bot2_count": 0,
        "top_row_1_bars": 2,
        "top1_count": 2,
        "top_row_1_dia": 24,
        "db_top_1": 24,
        "top_row_2_bars": 0,
        "top2_count": 0,
    }


def build_snapshot() -> dict[str, Any]:
    state = _fixture_state()
    ladder = BendingFailFamily().contracted_repair_ladder_specs(state, width_key="b")
    specs = [dict(row or {}) for row in list(ladder.get("specs") or []) if isinstance(row, dict)]
    known_bad = [
        dict(row or {})
        for row in list(ladder.get("known_bad_candidates_skipped") or [])
        if isinstance(row, dict)
    ]

    spec_checks: list[dict[str, Any]] = []
    invalid_specs: list[dict[str, Any]] = []
    for spec in specs:
        updates = dict(spec.get("updates") or {})
        rule = resolve_longitudinal_bar_spacing_rule(state, updates)
        row = {
            "lane_id": spec.get("contract_runtime_lane_id") or spec.get("lane_id"),
            "strategy": spec.get("strategy"),
            "updates": updates,
            "valid_longitudinal_spacing": bool(rule.get("valid")),
            "violations": list(rule.get("violations") or []),
            "maximum_longitudinal_bar_cc_spacing_mm": rule.get("maximum_longitudinal_bar_cc_spacing_mm"),
            "rows": list(rule.get("rows") or []),
        }
        spec_checks.append(row)
        if not bool(rule.get("valid")):
            invalid_specs.append(row)

    blocked_records = [
        {
            "stage_name": row.get("stage_name"),
            "strategy": row.get("strategy"),
            "reason": row.get("reason"),
            "longitudinal_bar_spacing_rule": dict(row.get("longitudinal_bar_spacing_rule") or {}),
        }
        for row in known_bad
        if row.get("reason") == "maximum_longitudinal_bar_spacing_exceeded"
    ]

    failures: list[str] = []
    if invalid_specs:
        failures.append("published_spec_violates_maximum_longitudinal_bar_spacing")
    if not blocked_records:
        failures.append("no_known_bad_record_for_maximum_longitudinal_bar_spacing")
    for record in blocked_records:
        if not dict(record.get("longitudinal_bar_spacing_rule") or {}).get("violations"):
            failures.append("blocked_record_missing_spacing_rule_evidence")
            break

    return {
        "schema": "bending_fail_governs_longitudinal_spacing_candidate_filter.v1",
        "result": "PASS" if not failures else "FAIL",
        "family_id": "BENDING_FAIL_GOVERNS",
        "rule": "No BENDING_FAIL_GOVERNS repair spec may publish a longitudinal top/bottom row above 300 mm c/c spacing.",
        "failures": failures,
        "spec_count": len(specs),
        "known_bad_count": len(known_bad),
        "spec_checks": spec_checks,
        "spacing_blocked_known_bad_records": blocked_records,
    }


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat().replace(":", "-")
    artifact = ARTIFACT_DIR / f"bending_fail_governs_longitudinal_spacing_candidate_filter_{timestamp}.json"
    report = AUDIT_DIR / f"bending_fail_governs_longitudinal_spacing_candidate_filter_{timestamp}.md"
    artifact.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    report.write_text(
        "\n".join(
            [
                "# BENDING_FAIL_GOVERNS Longitudinal Spacing Candidate Filter",
                "",
                f"Result: **{snapshot['result']}**",
                "",
                f"Family: `{snapshot['family_id']}`",
                "",
                f"Rule: {snapshot['rule']}",
                "",
                "## Counts",
                f"- Published specs checked: `{snapshot['spec_count']}`",
                f"- Known-bad candidates checked: `{snapshot['known_bad_count']}`",
                f"- Spacing blocked known-bad records: `{len(snapshot['spacing_blocked_known_bad_records'])}`",
                "",
                "## Failures",
                *(f"- {failure}" for failure in snapshot.get("failures") or ["None"]),
            ]
        ),
        encoding="utf-8",
    )
    return artifact, report


def main() -> int:
    snapshot = build_snapshot()
    artifact, report = _write_artifacts(snapshot)
    print(f"bending_fail_governs_longitudinal_spacing_candidate_filter {snapshot['result']}")
    print(f"artifact: {artifact}")
    print(f"report: {report}")
    return 0 if snapshot["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
