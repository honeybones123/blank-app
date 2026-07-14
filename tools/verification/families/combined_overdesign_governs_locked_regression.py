"""Family-scoped locked regression suite for COMBINED_OVERDESIGN.

This is the v2 regression owner for known error COG-001.
"""

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
        "zero_shear_cleanup_publication",
        "tools/verification/design_guide_combined_zero_shear_cleanup_publication_snapshot.py",
    ),
    (
        "shear_low_util_candidate_accumulator_cutover",
        "tools/verification/design_guide_shear_low_util_candidate_accumulator_cutover_snapshot.py",
    ),
)


def _run(script: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    return {
        "script": script,
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "stdout_tail": stdout[-3000:],
        "stderr_tail": stderr[-3000:],
    }


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_overdesign_governs_locked_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_overdesign_governs_locked_regression_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# COMBINED_OVERDESIGN Locked Regression",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Known Errors Covered",
                "",
                "- `COG-001`: stale family-contract violation shell hid available zero-shear cleanup",
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
        "family": "COMBINED_OVERDESIGN",
        "result": "PASS" if not failures else "FAIL",
        "known_errors": ["COG-001"],
        "regressions": rows,
        "scope": {
            "runtime_behaviour_changed": False,
            "visible_wording_changed": False,
            "cta_apply_semantics_changed": False,
            "family_runtime_changed": False,
        },
    }
    json_path, report_path = _write_artifacts(snapshot)
    print(f"combined overdesign locked regression {snapshot['result']}")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    if failures:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
