"""Aggregate current per-family live evidence into one universal proof artifact.

This verifier consumes only completed child audit JSON files. It does not run
the app, render UI, apply updates, or alter family routing.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.source_fingerprint import compute_source_fingerprint  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
FAMILIES = (
    "BENDING_FAIL_GOVERNS",
    "SHEAR_FAIL_GOVERNS",
    "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    "BENDING_OVERDESIGN_GOVERNS",
    "SHEAR_OVERDESIGN_GOVERNS",
    "COMBINED_OVERDESIGN_GOVERNS",
    "SERVICEABILITY_GOVERNS",
)


def _latest_child_by_family() -> dict[str, Path]:
    minimum_mtime = (ROOT / "app.py").stat().st_mtime
    latest: dict[str, Path] = {}
    for path in sorted(ARTIFACT_DIR.glob("family_10_fuzz_audit_*.json"), key=lambda p: p.stat().st_mtime):
        if path.stat().st_mtime < minimum_mtime:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            family_rows = list(payload.get("families") or [])
            family = str(family_rows[0].get("family") or "").strip().upper() if family_rows else ""
        except (OSError, json.JSONDecodeError, IndexError, AttributeError):
            continue
        if family in FAMILIES:
            latest[family] = path
    return latest


def _child_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    family_payload = dict((payload.get("families") or [{}])[0])
    live = dict(family_payload.get("live_execution") or {})
    failures = list(family_payload.get("failures_found") or [])
    return {
        "family": str(family_payload.get("family") or "").strip().upper(),
        "artifact": str(path.resolve()),
        "runner_result": str(payload.get("result") or "").strip(),
        "live_status": str(live.get("status") or "").strip(),
        "final_lock_status": str(family_payload.get("final_lock_status") or "").strip(),
        "seed": payload.get("seed"),
        "scenario_count": int(live.get("scenario_count") or 0),
        "passed_count": int(live.get("passed_count") or 0),
        "failed_count": int(live.get("failed_count") or 0),
        "failure_count": len(failures),
        "failures": failures,
    }


def _run(explicit: dict[str, Path] | None = None) -> dict[str, Any]:
    selected = explicit or _latest_child_by_family()
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for family in FAMILIES:
        path = selected.get(family)
        if path is None:
            failures.append({"family": family, "reason": "current_child_artifact_missing"})
            continue
        row = _child_summary(path)
        rows.append(row)
        if row["runner_result"] != "LIVE_EXECUTION_PASS":
            failures.append({"family": family, "reason": "runner_result_not_live_execution_pass", "value": row["runner_result"]})
        if row["live_status"] != "PASS":
            failures.append({"family": family, "reason": "live_status_not_pass", "value": row["live_status"]})
        if row["final_lock_status"] != "LOCKED_PASS":
            failures.append({"family": family, "reason": "family_lock_not_pass", "value": row["final_lock_status"]})
        if row["scenario_count"] != 10 or row["passed_count"] != 10 or row["failed_count"] != 0 or row["failure_count"] != 0:
            failures.append({"family": family, "reason": "scenario_count_or_failures_not_clean", "row": row})
        if row["seed"] != 1007:
            failures.append({"family": family, "reason": "seed_mismatch", "value": row["seed"]})

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    result = {
        "schema": "design_brain.current_universal_family_evidence.v1",
        "status": "PASS" if len(rows) == len(FAMILIES) and not failures else "FAIL",
        "generated_at": stamp,
        "source_fingerprint": compute_source_fingerprint(repo=ROOT),
        "family_count": len(rows),
        "expected_family_count": len(FAMILIES),
        "scenario_count": sum(row["scenario_count"] for row in rows),
        "expected_scenario_count": 90,
        "families": rows,
        "failures": failures,
        "checks": {
            "all_expected_families_present": len(rows) == len(FAMILIES),
            "all_live_execution_pass": not any(f["reason"] == "runner_result_not_live_execution_pass" for f in failures),
            "all_family_locks_pass": not any(f["reason"] == "family_lock_not_pass" for f in failures),
            "all_ninety_scenarios_clean": not any(f["reason"] == "scenario_count_or_failures_not_clean" for f in failures),
            "product_behaviour_changed": False,
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_brain_current_universal_family_evidence_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_current_universal_family_evidence_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Current Universal Design Brain Family Evidence",
        "",
        f"Status: **{result['status']}**",
        f"Families: **{len(rows)}/{len(FAMILIES)}**",
        f"Scenarios: **{result['scenario_count']}/90**",
        "",
        "| Family | Live result | Lock | Scenarios | Failures | Child artifact |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['family']}` | `{row['runner_result']}` | `{row['final_lock_status']}` | {row['scenario_count']} | {row['failure_count']} | `{row['artifact']}` |"
        )
    if failures:
        lines.extend(["", "## Failures", ""])
        for failure in failures:
            lines.append(f"- `{failure['family']}`: `{failure['reason']}`")
    lines.extend(
        [
            "",
            "This is an aggregate proof artifact over completed family live audits. It does not run, render, apply, mutate, or change product routing.",
            f"\nMachine-readable artifact: `{json_path}`",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "json": str(json_path), "report": str(md_path), "failures": failures}, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", action="append", default=[], help="Explicit FAMILY=PATH child artifact; repeat as needed")
    args = parser.parse_args()
    explicit: dict[str, Path] = {}
    for value in args.artifact:
        family, separator, path = str(value).partition("=")
        if not separator or family.strip().upper() not in FAMILIES:
            raise SystemExit(f"Expected FAMILY=PATH for one of: {', '.join(FAMILIES)}")
        explicit[family.strip().upper()] = Path(path).resolve()
    result = _run(explicit or None)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
