"""Family-scoped locked regression suite for SERVICEABILITY_GOVERNS."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

REGRESSION_CHAIN = (
    (
        "candidate_evaluation_boundary",
        "tools/verification/serviceability_candidate_evaluation_boundary_snapshot.py",
    ),
    (
        "lane_snapshot",
        "tools/verification/families/serviceability_governs_lane_snapshot.py",
    ),
    (
        "ladder_runtime",
        "tools/verification/families/serviceability_governs_ladder_runtime_snapshot.py",
    ),
    (
        "replacement_audit",
        "tools/verification/families/serviceability_governs_replacement_audit.py",
    ),
    (
        "live_surface_contract",
        "tools/verification/families/serviceability_governs_live_surface_contract.py",
    ),
)


def _run(script: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    return {
        "script": script,
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "stdout_tail": str(completed.stdout or "")[-3000:],
        "stderr_tail": str(completed.stderr or "")[-3000:],
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"serviceability_governs_locked_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"serviceability_governs_locked_regression_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SERVICEABILITY_GOVERNS Locked Regression",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Known Errors Covered",
                "",
                "- `SG-001`: serviceability candidate evaluation must stay behind the family/service boundary",
                "- `SG-002`: serviceability ladder ordering and exact-stop/exhausted proof must remain contract-owned",
                "- `SG-003`: live browser fuzz must prove the rendered serviceability family and no family-owned Apply CTA",
                "",
                "## Regression Chain",
                "",
                *[
                    f"- `{row['name']}`: `{'PASS' if row['result']['passed'] else 'FAIL'}`"
                    for row in snapshot["regressions"]
                ],
                "",
                "## Scope",
                "",
                "- engineering behaviour changed: `False`",
                "- visible wording changed: `False`",
                "- CTA/apply semantics changed: `False`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    rows = [{"name": name, "result": _run(script)} for name, script in REGRESSION_CHAIN]
    failures = [row for row in rows if not row["result"]["passed"]]
    snapshot = {
        "schema": "design_brain.family_locked_regression.v2",
        "family": "SERVICEABILITY_GOVERNS",
        "result": "PASS" if not failures else "FAIL",
        "known_errors": ["SG-001", "SG-002"],
        "regressions": rows,
        "scope": {
            "runtime_behaviour_changed": False,
            "visible_wording_changed": False,
            "cta_apply_semantics_changed": False,
            "family_runtime_changed": False,
        },
    }
    json_path, report_path = _write(snapshot)
    print(f"serviceability governs locked regression {snapshot['result']}")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    if failures:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
